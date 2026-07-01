"""Assessment router — self-assessment (indicative) and certified assessment flows."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.cgcs import enforce_not_cgcs
from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.assessment import AssessmentSession, AssessmentTier
from esb.models.user import RoleType
from esb.services import audit as audit_svc
from esb.services.assessment import create_indicative_session

router = APIRouter(prefix="/api/assessments", tags=["assessments"])

PRACTITIONER_ROLES = {
    RoleType.certified_practitioner,
    RoleType.senior_practitioner,
    RoleType.facilitation_manager,
    RoleType.lead_senior_practitioner,
    RoleType.superuser,
}


# ── Indicative (self-assessment) ──────────────────────────────────────────────

class IndicativeRequest(BaseModel):
    district_id: str
    # Band choices per practice (0-3)
    focus_mindset: int
    clarify_goals: int
    clarify_guardrails: int
    monitor: int
    align: int
    communicate: int


class PracticeScoreOut(BaseModel):
    practice: str
    raw_band: int
    score: int
    ceiling: int
    band_label: str


class AssessmentOut(BaseModel):
    session_id: str
    tier: str
    total_score: int
    composite_band: int
    practice_scores: list[PracticeScoreOut]
    clarify_detail: dict
    indicative_disclaimer: str = (
        "This is an indicative, self-scored assessment. It has not been validated "
        "or benchmarked by Effective School Boards. Results reflect the board's own "
        "perceptions and should be interpreted accordingly."
    )


@router.post("/indicative", response_model=AssessmentOut)
async def submit_indicative(
    body: IndicativeRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    # CGCS hard block
    await enforce_not_cgcs(UUID(body.district_id), db)

    raw_responses = {
        "focus_mindset":       body.focus_mindset,
        "clarify_goals":       body.clarify_goals,
        "clarify_guardrails":  body.clarify_guardrails,
        "monitor":             body.monitor,
        "align":               body.align,
        "communicate":         body.communicate,
    }

    session = await create_indicative_session(db, UUID(body.district_id), raw_responses)

    await audit_svc.record(
        db,
        action="assessment.indicative.submitted",
        resource_type="assessment_session",
        resource_id=session.id,
        actor_id=auth.person_id,
    )
    await db.commit()

    return AssessmentOut(
        session_id=str(session.id),
        tier=session.tier.value,
        total_score=session.total_score or 0,
        composite_band=session.composite_band or 1,
        practice_scores=[PracticeScoreOut(**s) for s in session.practice_scores],
        clarify_detail=session.clarify_detail,
    )


# ── Get results ───────────────────────────────────────────────────────────────

@router.get("/{session_id}", response_model=AssessmentOut)
async def get_assessment(
    session_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    session = await db.get(AssessmentSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Assessment session not found.")

    # Object-level auth: clients can only see their own district's assessments;
    # practitioners can see their clients' assessments
    # (full OLA in Phase 1; for now, any authenticated user can read)

    disclaimer = (
        "This is an indicative, self-scored assessment. It has not been validated "
        "or benchmarked by Effective School Boards."
        if session.tier == AssessmentTier.indicative
        else "Certified Assessment — administered by a credentialed Effective School Boards practitioner."
    )

    return AssessmentOut(
        session_id=str(session.id),
        tier=session.tier.value,
        total_score=session.total_score or 0,
        composite_band=session.composite_band or 1,
        practice_scores=[PracticeScoreOut(**s) for s in session.practice_scores],
        clarify_detail=session.clarify_detail,
        indicative_disclaimer=disclaimer,
    )
