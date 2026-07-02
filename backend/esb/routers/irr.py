"""Time Use Evaluation IRR Simulator router — M20."""
from __future__ import annotations

import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.eval.classification_guide import render_with_rules
from esb.models.irr import IRRAttempt, IRRAttemptStatus, IRRProgress, IRRScenario, IRRScenarioType, TimeUseLearningRule
from esb.models.user import RoleType
from esb.services.irr import (
    KAPPA_PASS_THRESHOLD,
    TIME_USE_ITEMS,
    generate_scenario,
    system_score_scenario,
)
from esb.services.irr import (
    submit_attempt as svc_submit_attempt,
)

router = APIRouter(prefix="/api/irr", tags=["irr"])

ADMIN_ROLES = {RoleType.lead_senior_practitioner, RoleType.superuser}


def _require_admin(auth: AuthContext) -> None:
    if not auth.has_role(*ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")

PRACTITIONER_ROLES = {
    RoleType.certified_practitioner,
    RoleType.senior_practitioner,
    RoleType.practitioner_manager,
    RoleType.lead_senior_practitioner,
    RoleType.superuser,
    RoleType.practitioner_in_training,
}


def require_practitioner(auth: AuthContext) -> None:
    if not auth.has_role(*PRACTITIONER_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Time Use Evaluation IRR Simulator requires a practitioner role.",
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
    # The ground-truth activity_id per minute-block is the answer key —
    # never persist or return it alongside the practitioner-facing data.
    scenario_data.pop("_minute_items_truth", None)

    scenario = IRRScenario(
        scenario_type=IRRScenarioType.time_use_eval,
        generation_seed=seed,
        scenario_data=scenario_data,
        system_scores=system_scores,
        focus_areas=[k for k in system_scores if not k.startswith("_")],
        is_active=True,
    )
    db.add(scenario)
    await db.flush()
    await db.commit()

    return ScenarioOut(
        scenario_id=str(scenario.id),
        scenario_data=scenario_data,
        item_count=len(scenario.focus_areas),
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
        item_count=len(scenario.focus_areas or []),
    )


# ── Submit attempt ────────────────────────────────────────────────────────────

class AttemptSubmit(BaseModel):
    scenario_id: str
    practitioner_scores: dict  # {"item_id": {"minutes": int}}


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


# ── Admin: scenario review ────────────────────────────────────────────────────

class AdminScenarioOut(BaseModel):
    id: str
    scenario_type: str
    template_version: str
    difficulty: str
    is_active: bool
    focus_areas: list[str]
    attempts: int
    attempts_passed: int
    avg_kappa: float | None
    created_at: str


class AdminScenarioStats(BaseModel):
    total_scenarios: int
    total_attempts: int
    total_passed: int
    overall_pass_rate: float | None
    avg_kappa: float | None


@router.get("/admin/scenarios/stats", response_model=AdminScenarioStats)
async def admin_scenario_stats(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> AdminScenarioStats:
    _require_admin(auth)

    total_scenarios = await db.scalar(select(func.count()).select_from(IRRScenario))
    total_attempts = await db.scalar(
        select(func.count()).select_from(IRRAttempt).where(IRRAttempt.status == IRRAttemptStatus.scored)
    )
    total_passed = await db.scalar(
        select(func.count()).select_from(IRRAttempt).where(IRRAttempt.passed.is_(True))
    )
    avg_kappa = await db.scalar(
        select(func.avg(IRRAttempt.kappa)).where(IRRAttempt.kappa.is_not(None))
    )

    return AdminScenarioStats(
        total_scenarios=total_scenarios or 0,
        total_attempts=total_attempts or 0,
        total_passed=total_passed or 0,
        overall_pass_rate=(total_passed / total_attempts) if total_attempts else None,
        avg_kappa=round(avg_kappa, 4) if avg_kappa is not None else None,
    )


@router.get("/admin/scenarios", response_model=list[AdminScenarioOut])
async def admin_list_scenarios(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> list[AdminScenarioOut]:
    _require_admin(auth)
    limit = max(1, min(limit, 200))

    scenarios = (await db.scalars(
        select(IRRScenario).order_by(IRRScenario.created_at.desc()).limit(limit)
    )).all()

    out = []
    for s in scenarios:
        attempts = (await db.scalars(
            select(IRRAttempt).where(IRRAttempt.scenario_id == s.id, IRRAttempt.status == IRRAttemptStatus.scored)
        )).all()
        kappas = [a.kappa for a in attempts if a.kappa is not None]
        out.append(AdminScenarioOut(
            id=str(s.id),
            scenario_type=s.scenario_type.value,
            template_version=s.template_version,
            difficulty=s.difficulty,
            is_active=s.is_active,
            focus_areas=s.focus_areas or [],
            attempts=len(attempts),
            attempts_passed=sum(1 for a in attempts if a.passed),
            avg_kappa=round(sum(kappas) / len(kappas), 4) if kappas else None,
            created_at=s.created_at.isoformat(),
        ))
    return out


# ── Time Use classification guide + learning rules ────────────────────────────

class LearningRuleOut(BaseModel):
    id: str
    activity_id: str
    context_snapshot: str
    note: str
    created_at: str


class GuideOut(BaseModel):
    guide_text: str
    rules: list[LearningRuleOut]


async def _get_rules(db: AsyncSession) -> list[TimeUseLearningRule]:
    return list((await db.scalars(
        select(TimeUseLearningRule).order_by(TimeUseLearningRule.created_at)
    )).all())


@router.get("/guide", response_model=GuideOut)
async def get_guide(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> GuideOut:
    """The compiled Time Use classification guide (base doc + every
    practitioner-submitted learning rule) — visible to any practitioner as
    reference material while training in the simulator."""
    require_practitioner(auth)
    rules = await _get_rules(db)
    return GuideOut(
        guide_text=render_with_rules(rules),
        rules=[
            LearningRuleOut(
                id=str(r.id), activity_id=r.activity_id,
                context_snapshot=r.context_snapshot, note=r.note,
                created_at=r.created_at.isoformat(),
            )
            for r in rules
        ],
    )


class CorrectionSubmit(BaseModel):
    activity_id: str
    note: str


@router.post("/attempts/{attempt_id}/corrections", status_code=status.HTTP_201_CREATED)
async def submit_correction(
    attempt_id: UUID,
    body: CorrectionSubmit,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """File a correction against the system's scoring on a specific
    Activity within a scored IRR attempt. Gated to superuser/lead_senior_practitioner
    — the same authority that reviews any other AI-assisted output in the
    portal. The correction is compiled into the classification guide
    immediately (get_guide reflects it on the next call) and feeds the
    real Time Use Evaluation tool's classification prompt too."""
    _require_admin(auth)
    if not body.note.strip():
        raise HTTPException(status_code=400, detail="A note explaining the correction is required.")

    item_def = next((i for i in TIME_USE_ITEMS if i["id"] == body.activity_id), None)
    if not item_def:
        raise HTTPException(status_code=400, detail=f"Unknown activity_id: {body.activity_id}")

    attempt = await db.get(IRRAttempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    scenario = await db.get(IRRScenario, attempt.scenario_id)

    sys_item = (scenario.system_scores or {}).get(body.activity_id, {}) if scenario else {}
    prac_item = (attempt.practitioner_scores or {}).get(body.activity_id, {})
    context = (
        f"System scored {sys_item.get('minutes', 0)} min; practitioner entered "
        f"{prac_item.get('minutes', 0)} min. Activity: {item_def['label']} ({item_def['framework']})."
    )

    rule = TimeUseLearningRule(
        created_by_id=auth.person_id,
        attempt_id=attempt_id,
        activity_id=body.activity_id,
        context_snapshot=context[:2000],
        note=body.note.strip()[:2000],
    )
    db.add(rule)
    await db.commit()

    return {"id": str(rule.id), "activity_id": rule.activity_id}
