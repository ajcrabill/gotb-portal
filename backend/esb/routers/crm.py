"""CRM core — national district/superintendent/board-member database.

Ported natively from coach-devon's /crm/* module. Access: lead_senior_practitioner
only.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.database import get_db
from esb.models.crm import CrmDistrict, CrmEmail, CrmPerson, CrmSubscriber
from esb.models.user import RoleType

router = APIRouter(prefix="/api/crm", tags=["crm"])

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

    districts = await db.scalar(select(func.count()).select_from(CrmDistrict))
    people = await db.scalar(select(func.count()).select_from(CrmPerson))
    emails = await db.scalar(select(func.count()).select_from(CrmEmail))
    supts = await db.scalar(select(func.count()).select_from(CrmPerson).where(CrmPerson.role == "superintendent"))
    board = await db.scalar(select(func.count()).select_from(CrmPerson).where(CrmPerson.role == "board_member"))
    former = await db.scalar(select(func.count()).select_from(CrmPerson).where(CrmPerson.status == "former"))
    crawled = await db.scalar(select(func.count()).select_from(CrmDistrict).where(CrmDistrict.last_crawled_at.is_not(None)))

    by_band_rows = (await db.execute(
        select(CrmDistrict.enrollment_band, func.count()).group_by(CrmDistrict.enrollment_band).order_by(func.count().desc())
    )).all()
    by_state_rows = (await db.execute(
        select(CrmDistrict.state, func.count()).group_by(CrmDistrict.state).order_by(CrmDistrict.state)
    )).all()
    emails_by_status_rows = (await db.execute(
        select(CrmEmail.status, func.count()).group_by(CrmEmail.status)
    )).all()

    by_state = dict(by_state_rows)
    emails_by_status = dict(emails_by_status_rows)

    return {
        "districts": districts, "people": people, "superintendents": supts,
        "board_members": board, "former_members": former, "emails": emails,
        "by_band": dict(by_band_rows),
        "states": len([s for s in by_state if s]),
        "by_state": by_state,
        "verification": {
            "emails_by_status": emails_by_status,
            "site_verified": emails_by_status.get("verified", 0),
            "districts_crawled": crawled,
            "districts_total": districts,
        },
    }


class DistrictListItem(BaseModel):
    id: str
    name: str
    state: str
    city: str
    enrollment: int | None
    band: str
    cgcs_member: bool | None
    website: str
    people_count: int


_SORT_COLUMNS = {
    "name": CrmDistrict.name,
    "state": CrmDistrict.state,
    "city": CrmDistrict.city,
    "enrollment": CrmDistrict.enrollment,
    "band": CrmDistrict.enrollment_band,
    "cgcs_member": CrmDistrict.cgcs_member,
}


@router.get("/districts")
async def list_districts(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(None),
    state: str | None = None,
    band: str | None = None,
    cgcs: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort: str = Query("enrollment"),
    dir: str = Query("desc"),
) -> dict:
    _require_crm_access(auth)

    stmt = select(CrmDistrict)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(CrmDistrict.name).like(like), func.lower(CrmDistrict.city).like(like)))
    if state:
        stmt = stmt.where(CrmDistrict.state == state.upper()[:2])
    if band:
        stmt = stmt.where(CrmDistrict.enrollment_band == band)
    if cgcs is not None:
        stmt = stmt.where(CrmDistrict.cgcs_member.is_(cgcs))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

    sort_col = _SORT_COLUMNS.get(sort, CrmDistrict.enrollment)
    ordered = sort_col.desc().nullslast() if dir == "desc" else sort_col.asc().nullsfirst()
    rows = (await db.scalars(
        stmt.order_by(ordered, CrmDistrict.name)
        .offset((page - 1) * page_size).limit(page_size)
    )).all()

    districts = []
    for d in rows:
        people_count = await db.scalar(select(func.count()).select_from(CrmPerson).where(CrmPerson.district_id == d.id))
        districts.append(DistrictListItem(
            id=str(d.id), name=d.name, state=d.state, city=d.city, enrollment=d.enrollment,
            band=d.enrollment_band, cgcs_member=d.cgcs_member, website=d.website, people_count=people_count,
        ))

    return {"total": total, "page": page, "page_size": page_size, "districts": districts}


@router.get("/districts/{district_id}")
async def district_detail(
    district_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_crm_access(auth)

    d = await db.get(CrmDistrict, district_id)
    if not d:
        raise HTTPException(status_code=404, detail="Not found.")

    people = (await db.scalars(select(CrmPerson).where(CrmPerson.district_id == d.id))).all()

    all_emails: list[str] = []
    person_emails: dict[UUID, list[CrmEmail]] = {}
    for p in people:
        rows = (await db.scalars(select(CrmEmail).where(CrmEmail.person_id == p.id))).all()
        person_emails[p.id] = list(rows)
        all_emails.extend(e.email for e in rows)

    sub_emails = set()
    if all_emails:
        sub_rows = (await db.scalars(select(CrmSubscriber.email).where(CrmSubscriber.email.in_(all_emails)))).all()
        sub_emails = set(sub_rows)

    people_sorted = sorted(people, key=lambda p: (p.status == "former", p.role != "superintendent", p.name))

    def person_dict(p: CrmPerson) -> dict:
        emails = person_emails.get(p.id, [])
        return {
            "id": str(p.id), "role": p.role, "name": p.name, "title": p.title, "status": p.status,
            "subscriber": any(e.email in sub_emails for e in emails),
            "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
            "departed_at": p.departed_at.isoformat() if p.departed_at else None,
            "emails": [
                {"email": e.email, "status": e.status, "source": e.source,
                 "last_checked": e.last_checked.isoformat() if e.last_checked else None}
                for e in emails
            ],
        }

    return {
        "id": str(d.id), "name": d.name, "nces_lea_id": d.nces_lea_id, "city": d.city, "state": d.state,
        "zip": d.zip, "street": d.street, "phone": d.phone, "website": d.website, "county": d.county,
        "enrollment": d.enrollment, "band": d.enrollment_band, "locale": d.locale,
        "district_type": d.district_type, "cgcs_member": d.cgcs_member,
        "operational_schools": d.operational_schools, "source": d.source,
        "last_crawled_at": d.last_crawled_at.isoformat() if d.last_crawled_at else None,
        "last_crawl_note": d.last_crawl_note,
        "people": [person_dict(p) for p in people_sorted],
    }
