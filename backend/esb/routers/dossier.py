"""Dossier Builder — research and understand a person or district for tailored
outreach.

Ported natively from coach-devon's /dossier/* module. Access:
lead_senior_practitioner only.
"""
from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from esb.auth.rbac import AuthContext, get_auth_context
from esb.crm import llm
from esb.crm.dossier.pipeline import create_dossier, run_pipeline
from esb.crm.dossier.stats import technique_effectiveness
from esb.crm.sync_db import sync_session
from esb.models.crm import CrmClaim, CrmDistrict, CrmDossier, CrmPerson, CrmSearch
from esb.models.user import Person, RoleType

log = structlog.get_logger()

router = APIRouter(prefix="/api/crm/dossier", tags=["crm-dossier"])

CRM_ROLES = {RoleType.lead_senior_practitioner, RoleType.superuser}


def _require_crm_access(auth: AuthContext) -> None:
    if not auth.has_role(*CRM_ROLES):
        raise HTTPException(status_code=403, detail="CRM access required.")


def _dossier_dict(session, dossier: CrmDossier) -> dict:
    claims = session.query(CrmClaim).filter(CrmClaim.dossier_id == dossier.id).all()
    searches = session.query(CrmSearch).filter(CrmSearch.dossier_id == dossier.id).all()
    return {
        "id": str(dossier.id), "subject": dossier.subject_name, "status": dossier.status,
        "summary": dossier.summary, "voice_flags": dossier.voice_flags or [],
        "markdown": dossier.markdown or "",
        "claims_count": len(claims), "confirmed_count": sum(1 for c in claims if c.confidence >= 0.9),
        "searches_count": len(searches),
        "claims": [
            {"field": c.field, "value": c.value, "confidence": c.confidence,
             "source_url": c.source_url, "source_tier": c.source_tier, "verdict": c.verdict}
            for c in claims
        ],
        "searches": [
            {"method": s.method, "source": s.source, "query": s.query, "url": s.url, "found": s.found}
            for s in searches
        ],
    }


@router.get("/status")
async def status(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict:
    _require_crm_access(auth)
    return {"llm_configured": llm.configured(), "model": "deepseek/deepseek-v4-flash"}


def _list_summary_dict(session, dossier: CrmDossier) -> dict:
    requester = session.get(Person, dossier.requested_by_id) if dossier.requested_by_id else None
    district = session.get(CrmDistrict, dossier.district_id) if dossier.district_id else None
    return {
        "id": str(dossier.id), "subject": dossier.subject_name, "status": dossier.status,
        "created_at": dossier.created_at.isoformat() if dossier.created_at else "",
        "district": district.name if district else "",
        "requested_by_name": requester.name if requester else "",
        "requested_by_email": requester.email if requester else "",
    }


def _run_list(requested_by_id: str | None, limit: int) -> list[dict]:
    session = sync_session()
    try:
        stmt = select(CrmDossier).order_by(CrmDossier.created_at.desc()).limit(limit)
        if requested_by_id:
            stmt = stmt.where(CrmDossier.requested_by_id == UUID(requested_by_id))
        dossiers = session.execute(stmt).scalars().all()
        return [_list_summary_dict(session, d) for d in dossiers]
    finally:
        session.close()


@router.get("/list/mine")
async def list_my_dossiers(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = 100,
) -> list[dict]:
    _require_crm_access(auth)
    return await asyncio.to_thread(_run_list, str(auth.person_id), limit)


@router.get("/list/all")
async def list_all_dossiers(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = 200,
) -> list[dict]:
    _require_crm_access(auth)
    return await asyncio.to_thread(_run_list, None, limit)


def _run_technique_stats() -> list[dict]:
    session = sync_session()
    try:
        return technique_effectiveness(session)
    finally:
        session.close()


@router.get("/technique-stats")
async def get_technique_stats(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[dict]:
    """Per-technique effectiveness across every dossier ever built — the
    learning-loop data for deciding which search techniques (including
    each individual matrix pivot) are worth keeping."""
    _require_crm_access(auth)
    return await asyncio.to_thread(_run_technique_stats)


class BuildRequest(BaseModel):
    person_id: str | None = None
    district_id: str | None = None
    subject_name: str | None = None


def _create(person_id: str | None, district_id: str | None, subject_name: str | None, requested_by_id: str) -> dict:
    """Fast, synchronous — resolves the target and inserts the initial
    "gathering" row so the caller gets a pollable id back immediately."""
    session = sync_session()
    try:
        person = None
        district = None
        if person_id:
            person = session.get(CrmPerson, UUID(person_id))
            if not person:
                return {"error": "person not found"}
        if district_id:
            district = session.get(CrmDistrict, UUID(district_id))
            if not district:
                return {"error": "district not found"}
        subject = subject_name or (person.name if person else "") or (district.name if district else "")
        if not subject:
            return {"error": "provide person_id, district_id, or subject_name"}

        dossier = create_dossier(session, subject, person, district, requested_by_id=UUID(requested_by_id))
        return {"id": str(dossier.id), "status": dossier.status}
    finally:
        session.close()


def _run_pipeline_bg(dossier_id: str, person_id: str | None, district_id: str | None) -> None:
    """Runs in the background — a full research pass can take well over a
    minute (multiple web searches + page fetches, sequential), too long for
    a synchronous request/response with no way to keep the connection alive.
    The frontend polls GET /{dossier_id} for status, same pattern already
    used for Time Use Eval jobs."""
    session = sync_session()
    try:
        dossier = session.get(CrmDossier, UUID(dossier_id))
        if not dossier:
            return
        person = session.get(CrmPerson, UUID(person_id)) if person_id else None
        district = session.get(CrmDistrict, UUID(district_id)) if district_id else None
        role = person.role if person else ""
        run_pipeline(session, dossier, dossier.subject_name, person, district, role)
    except Exception:
        log.exception("dossier.build_failed", dossier_id=dossier_id, person_id=person_id, district_id=district_id)
        try:
            dossier = session.get(CrmDossier, UUID(dossier_id))
            if dossier:
                dossier.status = "failed"
                session.commit()
        except Exception:
            pass
    finally:
        session.close()


@router.post("/build", status_code=202)
async def build(
    body: BuildRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    """Kicks off a dossier build in the background and returns immediately.

    Poll GET /api/crm/dossier/{dossier_id} — status starts at "gathering" and
    becomes "complete", "needs_llm" (no OpenRouter key configured), or
    "failed" when done.
    """
    _require_crm_access(auth)
    if not (body.person_id or body.district_id or body.subject_name):
        raise HTTPException(status_code=400, detail="Provide person_id, district_id, or subject_name.")

    created = await asyncio.to_thread(_create, body.person_id, body.district_id, body.subject_name, str(auth.person_id))
    if "error" in created:
        if "not found" in created["error"]:
            raise HTTPException(status_code=404, detail=created["error"])
        raise HTTPException(status_code=400, detail=created["error"])

    asyncio.get_event_loop().create_task(
        asyncio.to_thread(_run_pipeline_bg, created["id"], body.person_id, body.district_id)
    )
    return created


def _run_get(dossier_id: str) -> dict | None:
    session = sync_session()
    try:
        dossier = session.get(CrmDossier, UUID(dossier_id))
        if not dossier:
            return None
        return _dossier_dict(session, dossier)
    finally:
        session.close()


@router.get("/{dossier_id}")
async def get_dossier(
    dossier_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    result = await asyncio.to_thread(_run_get, str(dossier_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return result


def _run_get_markdown(dossier_id: str) -> tuple[str, str] | None:
    session = sync_session()
    try:
        dossier = session.get(CrmDossier, UUID(dossier_id))
        if not dossier or not dossier.markdown:
            return None
        return dossier.markdown, dossier.subject_name
    finally:
        session.close()


@router.get("/{dossier_id}/download")
async def download_dossier(
    dossier_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Response:
    _require_crm_access(auth)
    result = await asyncio.to_thread(_run_get_markdown, str(dossier_id))
    if result is None:
        raise HTTPException(status_code=404, detail="No markdown available for this dossier yet.")
    markdown, subject_name = result
    safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in subject_name).strip().replace(" ", "_") or "dossier"
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.md"'},
    )
