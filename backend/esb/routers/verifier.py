"""Email Verifier — live district crawl + verification.

Ported natively from coach-devon's /verifier/* module. Access:
lead_senior_practitioner only.
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
from esb.crm.sync_db import sync_session
from esb.crm.verifier.run import process_district
from esb.models.crm import CrmDistrict, CrmEmail
from esb.models.user import RoleType

router = APIRouter(prefix="/api/crm/verifier", tags=["crm-verifier"])

CRM_ROLES = {RoleType.lead_senior_practitioner, RoleType.superuser}


def _require_crm_access(auth: AuthContext) -> None:
    if not auth.has_role(*CRM_ROLES):
        raise HTTPException(status_code=403, detail="CRM access required.")


@router.get("/stats")
async def stats(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    rows = (await db.execute(select(CrmEmail.status, func.count()).group_by(CrmEmail.status))).all()
    by_status = dict(rows)
    return {"emails_by_status": by_status, "total": sum(by_status.values())}


def _run_verify(district_id: str) -> dict:
    session = sync_session()
    try:
        d = session.get(CrmDistrict, UUID(district_id))
        if not d:
            return {"error": "not found"}
        if not d.website:
            return {"district": d.name, "error": "no website on file"}
        return {"district": d.name, **process_district(session, d)}
    finally:
        session.close()


@router.post("/district/{district_id}")
async def verify_district(
    district_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)
    d = await db.get(CrmDistrict, district_id)
    if not d:
        raise HTTPException(status_code=404, detail="Not found.")

    result = await asyncio.to_thread(_run_verify, str(district_id))
    if result.get("error") == "not found":
        raise HTTPException(status_code=404, detail="Not found.")
    return result
