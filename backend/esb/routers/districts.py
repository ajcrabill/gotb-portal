"""Districts router — intake, CGCS check, search."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.cgcs import enforce_not_cgcs
from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.district import District
from esb.models.user import RoleType
from esb.services import audit as audit_svc

router = APIRouter(prefix="/api/districts", tags=["districts"])

STAFF_ROLES = {
    RoleType.practitioner_manager,
    RoleType.lead_senior_practitioner,
    RoleType.superuser,
}


# ── Search ────────────────────────────────────────────────────────────────────

class DistrictOut(BaseModel):
    id: str
    name: str
    state: str
    nces_lea_id: str | None
    is_cgcs_member: bool


@router.get("/search", response_model=list[DistrictOut])
async def search_districts(
    q: str,
    state: str | None = None,
    auth: Annotated[AuthContext | None, Depends(get_auth_context)] = None,
    db: AsyncSession = Depends(get_db),
) -> list[DistrictOut]:
    stmt = select(District).where(District.name.ilike(f"%{q}%"))
    if state:
        stmt = stmt.where(District.state == state.upper())
    stmt = stmt.limit(20)
    results = await db.scalars(stmt)
    return [
        DistrictOut(
            id=str(d.id),
            name=d.name,
            state=d.state,
            nces_lea_id=d.nces_lea_id,
            is_cgcs_member=d.is_cgcs_member,
        )
        for d in results.all()
        if not d.is_cgcs_member  # never surface CGCS districts to regular users
    ]


# ── Create ────────────────────────────────────────────────────────────────────

class DistrictCreate(BaseModel):
    name: str
    state: str
    nces_lea_id: str | None = None


@router.post("/", response_model=DistrictOut, status_code=status.HTTP_201_CREATED)
async def create_district(
    body: DistrictCreate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> DistrictOut:
    if not auth.has_role(*STAFF_ROLES):
        raise HTTPException(status_code=403, detail="Staff role required to create districts.")

    existing = None
    if body.nces_lea_id:
        existing = await db.scalar(
            select(District).where(District.nces_lea_id == body.nces_lea_id)
        )
    if existing:
        return DistrictOut(
            id=str(existing.id), name=existing.name, state=existing.state,
            nces_lea_id=existing.nces_lea_id, is_cgcs_member=existing.is_cgcs_member,
        )

    d = District(
        name=body.name.strip(),
        state=body.state.upper().strip(),
        nces_lea_id=body.nces_lea_id,
        is_cgcs_member=False,
    )
    db.add(d)
    await db.flush()

    await audit_svc.record(
        db, action="district.created", resource_type="district",
        resource_id=d.id, actor_id=auth.person_id,
    )
    await db.commit()

    return DistrictOut(id=str(d.id), name=d.name, state=d.state,
                       nces_lea_id=d.nces_lea_id, is_cgcs_member=d.is_cgcs_member)


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{district_id}", response_model=DistrictOut)
async def get_district(
    district_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> DistrictOut:
    d = await db.get(District, district_id)
    if not d:
        raise HTTPException(status_code=404, detail="District not found.")
    await enforce_not_cgcs(district_id, db)
    return DistrictOut(id=str(d.id), name=d.name, state=d.state,
                       nces_lea_id=d.nces_lea_id, is_cgcs_member=d.is_cgcs_member)


# ── Set CGCS flag (LSP / Superuser only, step-up required) ───────────────────

@router.patch("/{district_id}/cgcs", status_code=200)
async def set_cgcs_flag(
    district_id: UUID,
    is_cgcs: bool,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not auth.has_role(RoleType.lead_senior_practitioner, RoleType.superuser):
        raise HTTPException(status_code=403, detail="LSP or Superuser required.")
    auth.require_step_up()

    d = await db.get(District, district_id)
    if not d:
        raise HTTPException(status_code=404, detail="District not found.")

    old = d.is_cgcs_member
    d.is_cgcs_member = is_cgcs
    await audit_svc.record(
        db, action="district.cgcs_flag_changed", resource_type="district",
        resource_id=d.id, actor_id=auth.person_id,
        payload={"from": old, "to": is_cgcs},
    )
    await db.commit()
    return {"id": str(d.id), "is_cgcs_member": d.is_cgcs_member}
