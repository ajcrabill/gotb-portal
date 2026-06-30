"""IRR Simulator router — M20."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.irr import IRRAttempt, IRRAttemptStatus, IRRProgress, IRRScenario, IRRScenarioType
from esb.models.user import RoleType
from esb.services import audit as audit_svc
from esb.services.irr import (
    generate_scenario,
    system_score_scenario,
    submit_attempt as svc_submit_attempt,
    KAPPA_PASS_THRESHOLD,
)

router = APIRouter(prefix="/api/irr", tags=["irr"])

PRACTITIONER_ROLES = {
    RoleType.certified_facilitator,
    RoleType.senior_facilitator,
    RoleType.coaching_manager,
    RoleType.lead_senior_practitioner,
    RoleType.superuser,
    RoleType.facilitator_in_training,
}


def require_practitioner(auth: AuthContext) -> None:
    if not auth.has_role(*PRACTITIONER_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IRR Simulator requires a practitioner role.",
        )


# ── Generate scenario ─────────────────────────────────────────────────────────

class ScenarioOut(BaseModel):
    scenario_id: str
    scenario_data: dict
    item_count: int


@router.post("/scenarios/generate", response_model=ScenarioOut)
async def generate(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> ScenarioOut:
    require_practitioner(auth)

    seed = secrets.token_hex(8)
    scenario_data = generate_scenario(seed=seed)
    system_scores = system_score_scenario(scenario_data)

    scenario = IRRScenario(
        scenario_type=IRRScenarioType.time_use_eval,
        generation_seed=seed,
        scenario_data=scenario_data,
        system_scores=system_scores,
        focus_areas=list(system_scores.keys()),
        is_active=True,
    )
    db.add(scenario)
    await db.flush()
    await db.commit()

    return ScenarioOut(
        scenario_id=str(scenario.id),
        scenario_data=scenario_data,
        item_count=len(system_scores),
    )


# ── Get scenario (without system scores) ─────────────────────────────────────

@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> ScenarioOut:
    require_practitioner(auth)
    scenario = await db.get(IRRScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    return ScenarioOut(
        scenario_id=str(scenario.id),
        scenario_data=scenario.scenario_data,
        item_count=len(scenario.system_scores),
    )


# ── Submit attempt ────────────────────────────────────────────────────────────

class AttemptSubmit(BaseModel):
    scenario_id: str
    practitioner_scores: dict  # {"item_id": {"score": int, "notes": str}}


class AttemptResult(BaseModel):
    attempt_id: str
    kappa: float
    passed: bool
    item_kappas: dict
    item_feedback: dict
    system_scores: dict
    kappa_threshold: float
    message: str


@router.post("/attempts", response_model=AttemptResult)
async def submit_attempt(
    body: AttemptSubmit,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> AttemptResult:
    require_practitioner(auth)

    scenario = await db.get(IRRScenario, UUID(body.scenario_id))
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found.")

    attempt = IRRAttempt(
        scenario_id=scenario.id,
        practitioner_id=auth.person_id,
        status=IRRAttemptStatus.in_progress,
        practitioner_scores=body.practitioner_scores,
    )
    db.add(attempt)
    await db.flush()

    attempt = await svc_submit_attempt(db, attempt, scenario)
    await db.commit()

    if attempt.passed:
        msg = f"Excellent! κ = {attempt.kappa:.3f} — you've reached reliable agreement on this scenario."
    elif attempt.kappa and attempt.kappa >= 0.40:
        msg = f"Moderate agreement (κ = {attempt.kappa:.3f}). Review the feedback below and try again."
    else:
        msg = f"Poor agreement (κ = {attempt.kappa:.3f}). Study the rationales carefully before retrying."

    return AttemptResult(
        attempt_id=str(attempt.id),
        kappa=round(attempt.kappa or 0.0, 4),
        passed=attempt.passed or False,
        item_kappas=attempt.item_kappas,
        item_feedback=attempt.item_feedback,
        system_scores=scenario.system_scores,
        kappa_threshold=KAPPA_PASS_THRESHOLD,
        message=msg,
    )


# ── Progress ──────────────────────────────────────────────────────────────────

class ProgressOut(BaseModel):
    attempts_total: int
    attempts_passed: int
    rolling_kappa: float | None
    certified_at: str | None
    last_attempt_at: str | None


@router.get("/progress", response_model=ProgressOut)
async def get_progress(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> ProgressOut:
    require_practitioner(auth)

    progress = await db.scalar(
        select(IRRProgress).where(IRRProgress.practitioner_id == auth.person_id)
    )
    if not progress:
        return ProgressOut(
            attempts_total=0, attempts_passed=0,
            rolling_kappa=None, certified_at=None, last_attempt_at=None,
        )

    return ProgressOut(
        attempts_total=progress.attempts_total,
        attempts_passed=progress.attempts_passed,
        rolling_kappa=round(progress.rolling_kappa, 4) if progress.rolling_kappa is not None else None,
        certified_at=progress.certified_at.isoformat() if progress.certified_at else None,
        last_attempt_at=progress.last_attempt_at.isoformat() if progress.last_attempt_at else None,
    )
