"""Certified assessment flow — practitioner-administered, validated tier."""
from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.cgcs import enforce_not_cgcs
from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.assessment import AssessmentSession, AssessmentStatus, AssessmentTier
from esb.models.billing import Certification, CertificationStatus
from esb.models.district import District
from esb.models.user import RoleType
from esb.services import audit as audit_svc
from esb.services.assessment import score_assessment
from esb.services.scoring import get_active_config

router = APIRouter(prefix="/api/assessments/certified", tags=["assessment"])

CERTIFIED_ROLES = {
    RoleType.certified_practitioner,
    RoleType.senior_practitioner,
    RoleType.facilitation_manager,
    RoleType.lead_senior_practitioner,
    RoleType.superuser,
}

CERTIFIED_DISCLAIMER = (
    "This is a Certified Assessment administered by a credentialed "
    "Effective School Boards practitioner. Results are validated and may "
    "be used in official reporting and communications."
)


class CertifiedSessionCreate(BaseModel):
    district_id: str
    period_start: date
    period_end: date
    focus_mindset: int          # 0-3
    clarify_goals: int          # 0-3
    clarify_guardrails: int     # 0-3
    monitor: int                # 0-3
    align: int                  # 0-3
    communicate: int            # 0-3
    practitioner_notes: str = ""


class PracticeScoreOut(BaseModel):
    practice: str
    raw_band: int
    score: float
    ceiling: int
    band_label: str


class ClarifyDetailOut(BaseModel):
    goals_band: int
    guardrails_band: int
    conjunctive_band: int


class CertifiedSessionOut(BaseModel):
    session_id: str
    district_id: str
    district_name: str
    tier: str
    status: str
    period_start: str
    period_end: str
    total_score: float
    composite_band: int
    practice_scores: list[PracticeScoreOut]
    clarify_detail: ClarifyDetailOut | None
    practitioner_id: str
    certified_disclaimer: str


@router.post("/", response_model=CertifiedSessionOut, status_code=201)
async def create_certified_session(
    body: CertifiedSessionCreate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> CertifiedSessionOut:
    """
    Administer a Certified Assessment.

    Requires:
    - Practitioner role (certified_practitioner or above)
    - Active Certification record for the practitioner
    - District must not be a CGCS member
    """
    if not auth.has_role(*CERTIFIED_ROLES):
        raise HTTPException(status_code=403, detail="Certified practitioner role required.")

    # Verify active certification (superuser/LSP exempt for testing)
    if not auth.has_role(RoleType.superuser, RoleType.lead_senior_practitioner):
        cert = await db.scalar(
            select(Certification).where(
                Certification.person_id == auth.person_id,
                Certification.status == CertificationStatus.active,
            )
        )
        if not cert:
            raise HTTPException(
                status_code=403,
                detail="Active certification required to administer Certified Assessments.",
            )

    district_id = UUID(body.district_id)
    await enforce_not_cgcs(district_id, db)

    district = await db.get(District, district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found.")

    if body.period_start > body.period_end:
        raise HTTPException(status_code=400, detail="period_start must be before period_end.")

    config = await get_active_config(db)
    if not config:
        raise HTTPException(status_code=503, detail="No active scoring configuration.")

    raw_responses = {
        "focus_mindset": body.focus_mindset,
        "clarify_goals": body.clarify_goals,
        "clarify_guardrails": body.clarify_guardrails,
        "monitor": body.monitor,
        "align": body.align,
        "communicate": body.communicate,
    }

    session = AssessmentSession(
        district_id=district_id,
        scored_by_id=auth.person_id,
        tier=AssessmentTier.certified,
        status=AssessmentStatus.draft,
        scoring_config_id=config.id,
        period_start=body.period_start,
        period_end=body.period_end,
        raw_responses=raw_responses,
    )
    db.add(session)
    await db.flush()

    await score_assessment(db, session)
    session.status = AssessmentStatus.scored

    await audit_svc.record(
        db, action="assessment.certified.created", resource_type="assessment_session",
        resource_id=session.id, actor_id=auth.person_id,
        payload={
            "district_id": str(district_id),
            "total_score": session.total_score,
            "composite_band": session.composite_band,
            "tier": "certified",
        },
    )
    await db.commit()

    practice_scores = [
        PracticeScoreOut(**ps) for ps in (session.practice_scores or [])
    ]
    clarify_detail = None
    if session.clarify_detail:
        clarify_detail = ClarifyDetailOut(**session.clarify_detail)

    return CertifiedSessionOut(
        session_id=str(session.id),
        district_id=str(district_id),
        district_name=district.name,
        tier="certified",
        status=session.status.value,
        period_start=body.period_start.isoformat(),
        period_end=body.period_end.isoformat(),
        total_score=session.total_score or 0,
        composite_band=session.composite_band or 1,
        practice_scores=practice_scores,
        clarify_detail=clarify_detail,
        practitioner_id=str(auth.person_id),
        certified_disclaimer=CERTIFIED_DISCLAIMER,
    )


@router.get("/{session_id}", response_model=CertifiedSessionOut)
async def get_certified_session(
    session_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> CertifiedSessionOut:
    if not auth.has_role(*CERTIFIED_ROLES):
        raise HTTPException(status_code=403, detail="Practitioner role required.")

    session = await db.get(AssessmentSession, session_id)
    if not session or session.tier != AssessmentTier.certified:
        raise HTTPException(status_code=404, detail="Certified assessment not found.")

    # Practitioners can only read their own sessions (LSP/superuser see all)
    if (
        session.scored_by_id != auth.person_id
        and not auth.has_role(RoleType.lead_senior_practitioner, RoleType.superuser)
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    district = await db.get(District, session.district_id)

    practice_scores = [PracticeScoreOut(**ps) for ps in (session.practice_scores or [])]
    clarify_detail = ClarifyDetailOut(**session.clarify_detail) if session.clarify_detail else None

    return CertifiedSessionOut(
        session_id=str(session.id),
        district_id=str(session.district_id),
        district_name=district.name if district else "Unknown",
        tier="certified",
        status=session.status.value,
        period_start=session.period_start.isoformat() if session.period_start else "",
        period_end=session.period_end.isoformat() if session.period_end else "",
        total_score=session.total_score or 0,
        composite_band=session.composite_band or 1,
        practice_scores=practice_scores,
        clarify_detail=clarify_detail,
        practitioner_id=str(session.scored_by_id) if session.scored_by_id else "",
        certified_disclaimer=CERTIFIED_DISCLAIMER,
    )
