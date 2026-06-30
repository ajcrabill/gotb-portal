"""Admin router — people management, audit log, pipeline queue, scoring config."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.audit import AuditLog
from esb.models.scoring import ScoringConfig
from esb.models.user import Person, RoleMembership, RoleType
from esb.services import audit as audit_svc

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_ROLES = {RoleType.lead_senior_practitioner, RoleType.superuser}


def require_admin(auth: AuthContext) -> None:
    if not auth.has_role(*ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin role required.")


# ── People ────────────────────────────────────────────────────────────────────

class PersonOut(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]
    created_at: str


class RoleGrantRequest(BaseModel):
    person_id: str
    role: str
    scoped_district_id: str | None = None


@router.get("/people", response_model=list[PersonOut])
async def list_people(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
    q: str | None = None,
    limit: int = Query(50, le=200),
) -> list[PersonOut]:
    require_admin(auth)
    stmt = select(Person).order_by(Person.created_at.desc()).limit(limit)
    if q:
        stmt = stmt.where(Person.email.ilike(f"%{q}%") | Person.name.ilike(f"%{q}%"))
    people = await db.scalars(stmt)

    results = []
    now = datetime.now(timezone.utc)
    for p in people.all():
        roles_q = await db.scalars(
            select(RoleMembership.role).where(
                RoleMembership.person_id == p.id,
                RoleMembership.effective_from <= now,
                RoleMembership.effective_until.is_(None),
            )
        )
        results.append(PersonOut(
            id=str(p.id),
            email=p.email,
            name=p.name,
            roles=[r.value for r in roles_q.all()],
            created_at=p.created_at.isoformat() if p.created_at else "",
        ))
    return results


@router.post("/people/roles", status_code=201)
async def grant_role(
    body: RoleGrantRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_admin(auth)
    auth.require_step_up()

    try:
        role = RoleType(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role: {body.role}")

    now = datetime.now(timezone.utc)
    rm = RoleMembership(
        person_id=UUID(body.person_id),
        role=role,
        effective_from=now,
        scoped_district_id=UUID(body.scoped_district_id) if body.scoped_district_id else None,
    )
    db.add(rm)
    await db.flush()

    await audit_svc.record_role_change(
        db, actor_id=auth.person_id,
        target_person_id=UUID(body.person_id),
        role=body.role, change="granted",
    )
    await db.commit()
    return {"granted": body.role, "to": body.person_id}


@router.delete("/people/{person_id}/roles/{role}", status_code=204)
async def revoke_role(
    person_id: UUID,
    role: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> None:
    require_admin(auth)
    auth.require_step_up()

    now = datetime.now(timezone.utc)
    try:
        role_enum = RoleType(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")

    rm = await db.scalar(
        select(RoleMembership).where(
            RoleMembership.person_id == person_id,
            RoleMembership.role == role_enum,
            RoleMembership.effective_until.is_(None),
        )
    )
    if not rm:
        raise HTTPException(status_code=404, detail="Active role not found.")

    rm.effective_until = now
    await audit_svc.record_role_change(
        db, actor_id=auth.person_id,
        target_person_id=person_id,
        role=role, change="revoked",
    )
    await db.commit()


# ── Audit log ─────────────────────────────────────────────────────────────────

class AuditEntryOut(BaseModel):
    id: str
    actor_id: str | None
    actor_role: str | None
    actor_ip: str | None
    action: str
    resource_type: str
    resource_id: str | None
    payload_hash: str | None
    pipeline_verdict: str | None
    entry_hash: str
    prev_hash: str | None
    occurred_at: str


@router.get("/audit", response_model=list[AuditEntryOut])
async def get_audit_log(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
    action_prefix: str | None = None,
    resource_type: str | None = None,
    limit: int = Query(100, le=500),
) -> list[AuditEntryOut]:
    require_admin(auth)

    stmt = select(AuditLog).order_by(desc(AuditLog.occurred_at)).limit(limit)
    if action_prefix:
        stmt = stmt.where(AuditLog.action.ilike(f"{action_prefix}%"))
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)

    entries = await db.scalars(stmt)

    # Reading the audit log is itself audited
    await audit_svc.record(
        db, action="admin.audit_log.read", resource_type="audit_log",
        actor_id=auth.person_id, actor_role=next(iter(auth.roles)).value if auth.roles else None,
    )
    await db.commit()

    return [
        AuditEntryOut(
            id=str(e.id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            actor_role=e.actor_role,
            actor_ip=e.actor_ip,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=str(e.resource_id) if e.resource_id else None,
            payload_hash=e.payload_hash,
            pipeline_verdict=e.pipeline_verdict,
            entry_hash=e.entry_hash,
            prev_hash=e.prev_hash,
            occurred_at=e.occurred_at.isoformat(),
        )
        for e in entries.all()
    ]


# ── Scoring config ────────────────────────────────────────────────────────────

class ScoringConfigOut(BaseModel):
    id: str
    content_hash: str
    is_active: bool
    config: dict
    created_at: str


@router.get("/scoring", response_model=list[ScoringConfigOut])
async def list_scoring_configs(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> list[ScoringConfigOut]:
    require_admin(auth)
    configs = await db.scalars(
        select(ScoringConfig).order_by(ScoringConfig.created_at.desc())
    )
    return [
        ScoringConfigOut(
            id=str(c.id),
            content_hash=c.content_hash_value,
            is_active=c.is_active,
            config=c.config,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in configs.all()
    ]
