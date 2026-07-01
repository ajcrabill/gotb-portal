"""Turn a CRM segment filter into a concrete recipient list.

Ported from coach-devon's leadgen/segment.py. Recipients are (person, email)
pairs. By default only verified/valid emails are eligible — we do not blast
unverified addresses.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.models.crm import CrmDistrict, CrmEmail, CrmPerson


def resolve(session: Session, seg: dict) -> list[tuple[CrmPerson, str]]:
    """seg keys: state, band, role, cgcs, min_situation, has_signal, limit,
    email_statuses (defaults to verified/valid_mx/imported)."""
    statuses = seg.get("email_statuses") or ["verified", "valid_mx", "imported"]
    stmt = (
        select(CrmPerson, CrmEmail, CrmDistrict)
        .join(CrmEmail, CrmEmail.person_id == CrmPerson.id)
        .join(CrmDistrict, CrmDistrict.id == CrmPerson.district_id)
        .where(CrmEmail.status.in_(statuses))
    )
    if seg.get("role"):
        stmt = stmt.where(CrmPerson.role == seg["role"])
    if seg.get("state"):
        stmt = stmt.where(CrmDistrict.state == seg["state"].upper()[:2])
    if seg.get("band"):
        stmt = stmt.where(CrmDistrict.enrollment_band == seg["band"])
    if seg.get("cgcs") is not None:
        stmt = stmt.where(CrmDistrict.cgcs_member.is_(seg["cgcs"]))
    if seg.get("min_situation"):
        stmt = stmt.where(CrmDistrict.situation_score >= int(seg["min_situation"]))

    stmt = stmt.order_by(CrmDistrict.situation_score.desc(), CrmDistrict.enrollment.desc().nullslast())
    if seg.get("limit"):
        stmt = stmt.limit(int(seg["limit"]))

    seen: set[str] = set()
    out: list[tuple[CrmPerson, str]] = []
    for person, email, _ in session.execute(stmt).all():
        if email.email in seen:
            continue
        seen.add(email.email)
        out.append((person, email.email))
    return out
