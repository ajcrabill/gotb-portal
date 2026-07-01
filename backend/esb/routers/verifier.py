"""Email Verifier — live district crawl + verification.

Ported natively from coach-devon's /verifier/* module. Access:
lead_senior_practitioner only.
"""
from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.crm.sync_db import sync_session
from esb.crm.verifier.run import process_district
from esb.models.crm import CrmDistrict, CrmEmail, CrmVerifyJob
from esb.models.user import RoleType

log = structlog.get_logger()

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


def _run_verify_bg(job_id: str, district_id: str) -> None:
    """Runs in the background — measured 200s+ for a real district (website
    crawl + per-email verification), too long for a synchronous
    request/response with no way to keep the connection alive. The frontend
    polls GET /jobs/{job_id} for status, same pattern as Dossier Builder
    and Time Use Eval jobs."""
    session = sync_session()
    try:
        job = session.get(CrmVerifyJob, UUID(job_id))
        d = session.get(CrmDistrict, UUID(district_id))
        if not job or not d:
            return
        if not d.website:
            job.status, job.error = "failed", "No website on file for this district."
            session.commit()
            return
        result = {"district": d.name, **process_district(session, d)}
        job.status, job.result = "complete", result
        session.commit()
    except Exception as exc:
        log.exception("verifier.run_failed", job_id=job_id, district_id=district_id)
        try:
            job = session.get(CrmVerifyJob, UUID(job_id))
            if job:
                job.status, job.error = "failed", str(exc)[:500]
                session.commit()
        except Exception:
            pass
    finally:
        session.close()


def _create_job(district_id: str) -> dict:
    session = sync_session()
    try:
        d = session.get(CrmDistrict, UUID(district_id))
        if not d:
            return {"error": "not found"}
        job = CrmVerifyJob(district_id=d.id, status="running")
        session.add(job)
        session.commit()
        return {"id": str(job.id), "status": job.status}
    finally:
        session.close()


@router.post("/district/{district_id}", status_code=202)
async def verify_district(
    district_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Kicks off a district verification crawl in the background and returns
    immediately. Poll GET /api/crm/verifier/jobs/{job_id} for status/result."""
    _require_crm_access(auth)
    d = await db.get(CrmDistrict, district_id)
    if not d:
        raise HTTPException(status_code=404, detail="Not found.")

    created = await asyncio.to_thread(_create_job, str(district_id))
    if "error" in created:
        raise HTTPException(status_code=404, detail="Not found.")

    asyncio.get_event_loop().create_task(
        asyncio.to_thread(_run_verify_bg, created["id"], str(district_id))
    )
    return created


def _get_job(job_id: str) -> dict | None:
    session = sync_session()
    try:
        job = session.get(CrmVerifyJob, UUID(job_id))
        if not job:
            return None
        return {"id": str(job.id), "status": job.status, "result": job.result, "error": job.error}
    finally:
        session.close()


@router.get("/jobs/{job_id}")
async def get_verify_job(
    job_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    result = await asyncio.to_thread(_get_job, str(job_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return result
