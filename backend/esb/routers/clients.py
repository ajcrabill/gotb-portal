"""Clients router — practitioner's district engagement list."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.billing import DistrictEngagement, DistrictReferral, ReferralStatus
from esb.models.district import District
from esb.models.user import RoleType

router = APIRouter(prefix="/api/clients", tags=["clients"])

PRACTITIONER_ROLES = {
    RoleType.certified_facilitator,
    RoleType.senior_facilitator,
    RoleType.coaching_manager,
    RoleType.lead_senior_practitioner,
    RoleType.superuser,
}


class ClientOut(BaseModel):
    engagement_id: str
    district_id: str
    district_name: str
    district_state: str
    is_esb_referral: bool
    started_at: str | None
    ended_at: str | None


class ReferralOut(BaseModel):
    referral_id: str
    district_id: str
    district_name: str
    district_state: str
    status: str
    recommendation_rationale: str | None


@router.get("/", response_model=list[ClientOut])
async def list_clients(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> list[ClientOut]:
    if not auth.has_role(*PRACTITIONER_ROLES):
        raise HTTPException(status_code=403, detail="Practitioner role required.")

    engagements = await db.scalars(
        select(DistrictEngagement).where(
            DistrictEngagement.facilitator_id == auth.person_id,
            DistrictEngagement.ended_at.is_(None),
        ).order_by(DistrictEngagement.created_at.desc())
    )

    results = []
    for e in engagements.all():
        d = await db.get(District, e.district_id)
        if d:
            results.append(ClientOut(
                engagement_id=str(e.id),
                district_id=str(e.district_id),
                district_name=d.name,
                district_state=d.state,
                is_esb_referral=e.is_esb_referral,
                started_at=e.started_at.isoformat() if e.started_at else None,
                ended_at=e.ended_at.isoformat() if e.ended_at else None,
            ))
    return results


@router.get("/referrals", response_model=list[ReferralOut])
async def list_referrals(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> list[ReferralOut]:
    if not auth.has_role(*PRACTITIONER_ROLES):
        raise HTTPException(status_code=403, detail="Practitioner role required.")

    referrals = await db.scalars(
        select(DistrictReferral).where(
            DistrictReferral.recommended_to_id == auth.person_id,
            DistrictReferral.status.in_([ReferralStatus.pending, ReferralStatus.assigned]),
        ).order_by(DistrictReferral.created_at.desc())
    )

    results = []
    for r in referrals.all():
        d = await db.get(District, r.district_id)
        if d:
            results.append(ReferralOut(
                referral_id=str(r.id),
                district_id=str(r.district_id),
                district_name=d.name,
                district_state=d.state,
                status=r.status.value,
                recommendation_rationale=r.recommendation_rationale,
            ))
    return results
