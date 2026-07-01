"""Lead Generator — CRM segments to personalized, compliant outreach campaigns.

Ported natively from coach-devon's /leadgen/* module. Access:
lead_senior_practitioner only (except the public unsubscribe link, which
must stay unauthenticated — email recipients click it with no session).

Both send paths (per-message approve + bulk campaign send) are wired through
the portal's existing Postmark email service rather than Devon's own
Gmail-based sender, which never actually worked upstream (gmail.send()
unconditionally raises NotConfigured — real OAuth was never wired).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.config import settings
from esb.core.database import get_db
from esb.crm.leadgen import cadence, compose
from esb.crm.leadgen.run import build_campaign, generate_drafts
from esb.crm.sync_db import sync_session
from esb.models.crm import (
    CrmCampaign, CrmDistrict, CrmGlobalDirective, CrmMessage, CrmPerson, CrmSequence, CrmSuppression,
)
from esb.models.user import RoleType
from esb.services.email import send_email

router = APIRouter(prefix="/api/crm/leadgen", tags=["crm-leadgen"])
public_router = APIRouter(prefix="/api/crm/leadgen", tags=["crm-leadgen-public"])

CRM_ROLES = {RoleType.lead_senior_practitioner, RoleType.superuser}


def _require_crm_access(auth: AuthContext) -> None:
    if not auth.has_role(*CRM_ROLES):
        raise HTTPException(status_code=403, detail="CRM access required.")


# ── Public: unsubscribe ─────────────────────────────────────────────────────

def _run_unsubscribe(token: str) -> str | None:
    session = sync_session()
    try:
        email = compose.email_from_token(token)
        if not email:
            return None
        exists = session.execute(select(CrmSuppression).where(CrmSuppression.email == email)).scalar_one_or_none()
        if not exists:
            session.add(CrmSuppression(email=email, reason="unsubscribe"))
            session.query(CrmMessage).filter(CrmMessage.email == email, CrmMessage.status == "queued").update(
                {CrmMessage.status: "unsubscribed"})
            session.commit()
        return email
    finally:
        session.close()


@public_router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(token: str) -> str:
    email = await asyncio.to_thread(_run_unsubscribe, token)
    if not email:
        return "<h3>Invalid unsubscribe link.</h3>"
    return f"<h3>You're unsubscribed.</h3><p>{email} will receive no further emails from Effective School Boards.</p>"


# ── Campaigns ────────────────────────────────────────────────────────────────

class CampaignReq(BaseModel):
    name: str
    segment: dict = {}
    subject: str = ""
    template: str = ""
    daily_cap: int = 40


@router.post("/campaigns")
async def create_campaign(
    req: CampaignReq,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    c = CrmCampaign(name=req.name, segment=req.segment, subject=req.subject,
                     template=req.template, daily_cap=req.daily_cap)
    db.add(c)
    await db.commit()
    return {"id": str(c.id), "name": c.name, "status": c.status}


@router.get("/campaigns")
async def list_campaigns(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    rows = (await db.scalars(select(CrmCampaign).order_by(CrmCampaign.created_at.desc()))).all()
    out = []
    for c in rows:
        msg_count = await db.scalar(select(func.count()).select_from(CrmMessage).where(CrmMessage.campaign_id == c.id))
        out.append({"id": str(c.id), "name": c.name, "status": c.status, "messages": msg_count, "daily_cap": c.daily_cap})
    return {"campaigns": out}


def _run_build(campaign_id: str) -> dict | None:
    session = sync_session()
    try:
        c = session.get(CrmCampaign, UUID(campaign_id))
        if not c:
            return None
        result = build_campaign(session, c)
        return {"campaign": c.name, **result}
    finally:
        session.close()


@router.post("/campaigns/{cid}/build")
async def build(
    cid: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    result = await asyncio.to_thread(_run_build, str(cid))
    if result is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return result


@router.get("/campaigns/{cid}/preview")
async def preview(
    cid: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
    n: int = 3,
) -> dict:
    _require_crm_access(auth)
    c = await db.get(CrmCampaign, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Not found.")
    msgs = (await db.scalars(
        select(CrmMessage).where(CrmMessage.campaign_id == c.id, CrmMessage.status == "queued").limit(n)
    )).all()
    return {"campaign": c.name, "samples": [{"to": m.email, "subject": m.subject, "body": m.body} for m in msgs]}


class SendReq(BaseModel):
    confirm: bool = False


@router.post("/campaigns/{cid}/send")
async def send(
    cid: UUID,
    req: SendReq,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    c = await db.get(CrmCampaign, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Not found.")

    gates = {
        "postal_address_set": bool(settings.esb_postal_address),
        "explicit_confirm": req.confirm,
    }
    if not all(gates.values()):
        return {"sent": 0, "blocked": True, "gates": gates, "message": "Send blocked: all gates must be true. Nothing was sent."}

    sent_today = await db.scalar(
        select(func.count()).select_from(CrmMessage).where(
            CrmMessage.status == "sent",
            CrmMessage.sent_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
        )
    )
    budget = max(0, min(c.daily_cap, 40) - sent_today)
    queued = (await db.scalars(
        select(CrmMessage).where(CrmMessage.campaign_id == c.id, CrmMessage.status == "queued").limit(budget)
    )).all()

    sent = 0
    for m in queued:
        suppressed = await db.scalar(select(CrmSuppression).where(CrmSuppression.email == m.email))
        if suppressed:
            m.status = "skipped_suppressed"
            continue
        ok = await send_email(m.email, m.subject, m.body)
        if ok:
            m.status, m.sent_at = "sent", datetime.now(timezone.utc)
            sent += 1
    await db.commit()
    return {"sent": sent, "blocked": False, "daily_budget": budget, "gates": gates}


@router.get("/suppression")
async def suppression(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    total = await db.scalar(select(func.count()).select_from(CrmSuppression))
    return {"suppressed": total, "send_ready": bool(settings.esb_postal_address)}


# ── Approval workflow (the daily review loop) ───────────────────────────────

@router.get("/queue")
async def queue(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
    limit: int = 25,
) -> dict:
    _require_crm_access(auth)
    drafts = (await db.scalars(
        select(CrmMessage).where(CrmMessage.status == "draft").order_by(CrmMessage.created_at).limit(limit)
    )).all()
    pending = await db.scalar(select(func.count()).select_from(CrmMessage).where(CrmMessage.status == "draft"))

    out = []
    for m in drafts:
        p = await db.get(CrmPerson, m.person_id) if m.person_id else None
        d = await db.get(CrmDistrict, p.district_id) if p and p.district_id else None
        out.append({
            "id": str(m.id), "to": m.email,
            "name": p.name if p else "", "role": p.role if p else "",
            "district": d.name if d else "", "state": d.state if d else "",
            "subject": m.subject, "body": m.body, "rationale": m.rationale,
            "touch": m.touch_number, "sequence_id": str(m.sequence_id) if m.sequence_id else None,
        })
    return {
        "pending": pending, "drafts": out,
        "send_ready": bool(settings.esb_postal_address),
        "postal_address_set": bool(settings.esb_postal_address),
    }


@router.post("/{mid}/approve")
async def approve(
    mid: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    m = await db.get(CrmMessage, mid)
    if not m or m.status != "draft":
        raise HTTPException(status_code=404, detail="No such draft.")

    if not settings.esb_postal_address:
        return {"sent": False, "blocked": True, "reason": "Set ESB_POSTAL_ADDRESS first (legally required in every email)."}

    suppressed = await db.scalar(select(CrmSuppression).where(CrmSuppression.email == m.email))
    if suppressed:
        m.status = "skipped_suppressed"
        await db.commit()
        return {"sent": False, "blocked": True, "reason": "Recipient is on the suppression list."}

    unsub = compose.unsub_url(m.unsubscribe_token)
    plain, _html = compose.to_parts(m.body, unsub)
    ok = await send_email(m.email, m.subject, plain)
    if not ok:
        return {"sent": False, "error": "SendFailed"}

    sent_at = datetime.now(timezone.utc)
    m.status, m.sent_at = "sent", sent_at

    nxt = None
    if m.sequence_id:
        seq = await db.get(CrmSequence, m.sequence_id)
        if seq:
            cadence.advance_after_send(seq, m.touch_number, sent_at)
            nxt = seq.next_due_at.isoformat() if seq.next_due_at else None
    await db.commit()
    return {"sent": True, "to": m.email, "touch": m.touch_number, "next_touch_due": nxt}


class DeclineReq(BaseModel):
    reason: str = ""
    intent: str = "training"  # training | instruction


@router.post("/{mid}/decline")
async def decline(
    mid: UUID,
    req: DeclineReq,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    m = await db.get(CrmMessage, mid)
    if not m or m.status != "draft":
        raise HTTPException(status_code=404, detail="No such draft.")

    m.status, m.decline_reason, m.decline_intent = "declined", req.reason, req.intent
    if req.intent == "instruction" and req.reason.strip():
        db.add(CrmGlobalDirective(text=req.reason.strip()))

    if m.sequence_id:
        seq = await db.get(CrmSequence, m.sequence_id)
        if seq:
            seq.next_due_at = datetime.now(timezone.utc) + timedelta(days=1)
            if req.intent == "instruction":
                p = await db.get(CrmPerson, seq.person_id)
                if p:
                    district = await db.get(CrmDistrict, p.district_id) if p.district_id else None
                    seq.vars = await asyncio.to_thread(_run_extract_vars, str(p.id), str(district.id) if district else None)
    await db.commit()
    return {"declined": True, "intent": req.intent,
            "directive_added": req.intent == "instruction" and bool(req.reason.strip())}


def _run_extract_vars(person_id: str, district_id: str | None) -> dict:
    session = sync_session()
    try:
        p = session.get(CrmPerson, UUID(person_id))
        d = session.get(CrmDistrict, UUID(district_id)) if district_id else None
        return cadence.extract_vars(session, p, d)
    finally:
        session.close()


class StatusReq(BaseModel):
    status: str  # doc_provided | no_interest | neutral | bounced | stopped


@router.post("/sequence/{sid}/status")
async def set_status(
    sid: UUID,
    req: StatusReq,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Stop rules: any status other than not_contacted/email_sent terminates the cadence."""
    _require_crm_access(auth)
    seq = await db.get(CrmSequence, sid)
    if not seq:
        raise HTTPException(status_code=404, detail="No such sequence.")
    seq.status, seq.next_due_at = req.status, None
    if req.status == "bounced":
        exists = await db.scalar(select(CrmSuppression).where(CrmSuppression.email == seq.email))
        if not exists:
            db.add(CrmSuppression(email=seq.email, reason="bounce"))
    await db.commit()
    return {"ok": True, "status": seq.status}


def _run_generate(count: int) -> int:
    session = sync_session()
    try:
        return generate_drafts(session, count)
    finally:
        session.close()


@router.post("/generate")
async def generate(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    count: int = 5,
) -> dict:
    _require_crm_access(auth)
    created = await asyncio.to_thread(_run_generate, count)
    return {"created": created}
