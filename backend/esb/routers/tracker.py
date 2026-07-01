"""Coach Progress Tracker router — practitioner certification competency checklist.

Ported natively from coach-devon's standalone /tracker/* module. Access:
lead_senior_practitioner and practitioner_manager only.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.tracker import TrackerCoach, TrackerCompetencyCatalog, TrackerCompetencyCompletion
from esb.models.user import RoleType

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

TRACKER_ROLES = {
    RoleType.lead_senior_practitioner,
    RoleType.practitioner_manager,
    RoleType.superuser,
}


def _require_tracker_access(auth: AuthContext) -> None:
    if not auth.has_role(*TRACKER_ROLES):
        raise HTTPException(status_code=403, detail="Tracker access required.")


# ── Schemas ──────────────────────────────────────────────────────────────────

class CompetencyOut(BaseModel):
    key: str
    category: str
    description: str
    is_legacy: bool
    sort_order: int


class CompetencyCreate(BaseModel):
    key: str
    category: str
    description: str
    is_legacy: bool = False
    sort_order: int = 0


class CompetencyPatch(BaseModel):
    category: str | None = None
    description: str | None = None
    is_legacy: bool | None = None
    sort_order: int | None = None


class CoachOut(BaseModel):
    code: str
    name: str
    email: str | None
    phone: str | None
    org: str | None
    state: str | None
    cert_status: int
    cert_date: str | None
    competencies: dict[str, bool]


class CoachCreate(BaseModel):
    code: str
    name: str
    email: str | None = None
    phone: str | None = None
    org: str | None = None
    state: str | None = None
    cert_status: int = 0
    cert_date: str | None = None


class CoachPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    org: str | None = None
    state: str | None = None
    cert_status: int | None = None
    cert_date: str | None = None


class CompletionUpdate(BaseModel):
    completed: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _competency_map(db: AsyncSession, coach_code: str) -> dict[str, bool]:
    rows = await db.execute(
        select(TrackerCompetencyCompletion.competency_key, TrackerCompetencyCompletion.completed)
        .where(TrackerCompetencyCompletion.coach_code == coach_code)
    )
    return {key: completed for key, completed in rows.all()}


# ── Competency catalog ───────────────────────────────────────────────────────

@router.get("/competencies", response_model=list[CompetencyOut])
async def list_competencies(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> list[CompetencyOut]:
    _require_tracker_access(auth)
    rows = await db.scalars(
        select(TrackerCompetencyCatalog).order_by(
            TrackerCompetencyCatalog.sort_order, TrackerCompetencyCatalog.key
        )
    )
    return [CompetencyOut.model_validate(r, from_attributes=True) for r in rows.all()]


@router.post("/competencies", response_model=CompetencyOut, status_code=201)
async def create_competency(
    body: CompetencyCreate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> CompetencyOut:
    _require_tracker_access(auth)
    existing = await db.get(TrackerCompetencyCatalog, body.key)
    if existing:
        raise HTTPException(status_code=409, detail=f"Competency key '{body.key}' already exists.")
    row = TrackerCompetencyCatalog(**body.model_dump())
    db.add(row)
    await db.commit()
    return CompetencyOut.model_validate(row, from_attributes=True)


@router.put("/competencies/{key}", response_model=CompetencyOut)
async def update_competency(
    key: str,
    body: CompetencyPatch,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> CompetencyOut:
    _require_tracker_access(auth)
    row = await db.get(TrackerCompetencyCatalog, key)
    if not row:
        raise HTTPException(status_code=404, detail=f"Competency '{key}' not found.")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    for field, value in updates.items():
        setattr(row, field, value)
    await db.commit()
    return CompetencyOut.model_validate(row, from_attributes=True)


@router.delete("/competencies/{key}", status_code=204, response_model=None)
async def delete_competency(
    key: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_tracker_access(auth)
    row = await db.get(TrackerCompetencyCatalog, key)
    if not row:
        raise HTTPException(status_code=404, detail=f"Competency '{key}' not found.")
    await db.delete(row)
    await db.commit()


# ── Coaches ──────────────────────────────────────────────────────────────────

@router.get("/coaches", response_model=list[CoachOut])
async def list_coaches(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> list[CoachOut]:
    _require_tracker_access(auth)
    rows = await db.scalars(select(TrackerCoach).order_by(TrackerCoach.code))
    result = []
    for coach in rows.all():
        competencies = await _competency_map(db, coach.code)
        result.append(CoachOut(
            code=coach.code, name=coach.name, email=coach.email, phone=coach.phone,
            org=coach.org, state=coach.state, cert_status=coach.cert_status,
            cert_date=coach.cert_date, competencies=competencies,
        ))
    return result


@router.post("/coaches", response_model=CoachOut, status_code=201)
async def create_coach(
    body: CoachCreate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> CoachOut:
    _require_tracker_access(auth)
    existing = await db.get(TrackerCoach, body.code)
    if existing:
        raise HTTPException(status_code=409, detail="Coach with this code already exists.")
    coach = TrackerCoach(**body.model_dump())
    db.add(coach)

    catalog_keys = (await db.scalars(select(TrackerCompetencyCatalog.key))).all()
    for key in catalog_keys:
        db.add(TrackerCompetencyCompletion(coach_code=coach.code, competency_key=key, completed=False))
    await db.commit()

    return CoachOut(
        code=coach.code, name=coach.name, email=coach.email, phone=coach.phone,
        org=coach.org, state=coach.state, cert_status=coach.cert_status,
        cert_date=coach.cert_date, competencies=dict.fromkeys(catalog_keys, False),
    )


@router.put("/coaches/{code}", response_model=CoachOut)
async def update_coach(
    code: str,
    body: CoachPatch,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> CoachOut:
    _require_tracker_access(auth)
    coach = await db.get(TrackerCoach, code)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    for field, value in updates.items():
        setattr(coach, field, value)
    await db.commit()
    competencies = await _competency_map(db, code)
    return CoachOut(
        code=coach.code, name=coach.name, email=coach.email, phone=coach.phone,
        org=coach.org, state=coach.state, cert_status=coach.cert_status,
        cert_date=coach.cert_date, competencies=competencies,
    )


@router.delete("/coaches/{code}", status_code=204, response_model=None)
async def delete_coach(
    code: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_tracker_access(auth)
    coach = await db.get(TrackerCoach, code)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    await db.delete(coach)
    await db.commit()


@router.put("/coaches/{code}/competencies/{key}")
async def update_coach_competency(
    code: str,
    key: str,
    body: CompletionUpdate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> CompletionUpdate:
    _require_tracker_access(auth)
    coach = await db.get(TrackerCoach, code)
    if not coach:
        raise HTTPException(status_code=404, detail="Coach not found.")
    catalog_entry = await db.get(TrackerCompetencyCatalog, key)
    if not catalog_entry:
        raise HTTPException(status_code=400, detail=f"Unknown competency key: {key}")

    completion = await db.scalar(
        select(TrackerCompetencyCompletion).where(
            TrackerCompetencyCompletion.coach_code == code,
            TrackerCompetencyCompletion.competency_key == key,
        )
    )
    if completion:
        completion.completed = body.completed
    else:
        db.add(TrackerCompetencyCompletion(coach_code=code, competency_key=key, completed=body.completed))
    await db.commit()
    return body
