"""Dossier Builder — research and understand a person or district for tailored
outreach.

Ported natively from coach-devon's /dossier/* module. Access:
lead_senior_practitioner only.
"""
from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from esb.auth.rbac import AuthContext, get_auth_context
from esb.crm import llm
from esb.crm.dossier.pipeline import build as build_dossier
from esb.crm.sync_db import sync_session
from esb.models.crm import CrmClaim, CrmDistrict, CrmDossier, CrmPerson, CrmSearch
from esb.models.user import RoleType

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
        "summary": dossier.summary,
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


class BuildRequest(BaseModel):
    person_id: str | None = None
    district_id: str | None = None
    subject_name: str | None = None


def _run_build(person_id: str | None, district_id: str | None, subject_name: str | None) -> dict:
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
        role = person.role if person else ""
        dossier = build_dossier(session, subject, person, district, role)
        return _dossier_dict(session, dossier)
    finally:
        session.close()


@router.post("/build")
async def build(
    body: BuildRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    if not (body.person_id or body.district_id or body.subject_name):
        raise HTTPException(status_code=400, detail="Provide person_id, district_id, or subject_name.")

    result = await asyncio.to_thread(_run_build, body.person_id, body.district_id, body.subject_name)
    if "error" in result:
        if "not found" in result["error"]:
            raise HTTPException(status_code=404, detail=result["error"])
        raise HTTPException(status_code=400, detail=result["error"])
    return result


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
