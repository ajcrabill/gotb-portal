"""Newsworthy Scraper — detect school boards in trouble in real time as outreach
triggers.

Ported natively from coach-devon's /newsworthy/* module. Access:
lead_senior_practitioner only. The scout/harvest background tick job (which
needs Playwright for JS-rendered board pages) is deferred — this covers the
three HTTP-facing endpoints.
"""
from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.crm.newsworthy import scan_district
from esb.crm.sync_db import sync_session
from esb.models.crm import CrmDistrict, CrmSignal
from esb.models.user import RoleType

router = APIRouter(prefix="/api/crm/newsworthy", tags=["crm-newsworthy"])

CRM_ROLES = {RoleType.lead_senior_practitioner, RoleType.superuser}


def _require_crm_access(auth: AuthContext) -> None:
    if not auth.has_role(*CRM_ROLES):
        raise HTTPException(status_code=403, detail="CRM access required.")


@router.get("/signals")
async def list_signals(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
    severity: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    _require_crm_access(auth)
    limit = max(1, min(limit, 200))

    stmt = select(CrmSignal, CrmDistrict).join(CrmDistrict, CrmDistrict.id == CrmSignal.district_id)
    if severity:
        stmt = stmt.where(CrmSignal.severity == severity)
    if status:
        stmt = stmt.where(CrmSignal.outreach_status == status)
    rows = (await db.execute(stmt.order_by(CrmSignal.detected_at.desc()).limit(limit))).all()

    return {"signals": [
        {"id": str(s.id), "district": d.name, "state": d.state, "district_id": str(d.id),
         "kind": s.kind, "severity": s.severity, "headline": s.headline, "snippet": s.snippet,
         "url": s.url, "matched_terms": s.matched_terms, "status": s.outreach_status}
        for s, d in rows
    ]}


@router.get("/stats")
async def stats(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    by_sev_rows = (await db.execute(select(CrmSignal.severity, func.count()).group_by(CrmSignal.severity))).all()
    total = await db.scalar(select(func.count()).select_from(CrmSignal))
    flagged = await db.scalar(select(func.count()).select_from(CrmDistrict).where(CrmDistrict.situation_score > 0))
    return {"by_severity": dict(by_sev_rows), "total": total, "districts_flagged": flagged}


def _run_scan(district_id: str) -> dict:
    session = sync_session()
    try:
        d = session.get(CrmDistrict, UUID(district_id))
        if not d:
            return {"error": "not found"}
        new_signals = scan_district(session, d)
        return {"district": d.name, "new_signals": new_signals, "situation_score": d.situation_score}
    finally:
        session.close()


@router.post("/scan/{district_id}")
async def scan(
    district_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    result = await asyncio.to_thread(_run_scan, str(district_id))
    if result.get("error") == "not found":
        raise HTTPException(status_code=404, detail="Not found.")
    return result
