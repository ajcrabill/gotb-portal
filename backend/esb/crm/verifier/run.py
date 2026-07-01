"""EmailVerifier orchestration — ported from coach-devon's verifier/run.py.

Uses a sync SQLAlchemy Session against esb-portal's Postgres DB (see
esb/crm/sync_db.py) — the router calls process_district via
asyncio.to_thread() since this pipeline's relationship-traversal logic
is not async.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.crm.verifier import accuracy, validate
from esb.crm.verifier.crawl import discover_emails
from esb.crm.verifier.roster import extract_roster
from esb.models.crm import CrmDistrict, CrmEmail, CrmPerson


def now() -> datetime:
    return datetime.now(timezone.utc)


def norm_name(name: str) -> str:
    n = (name or "").lower().strip()
    n = re.sub(r"\(\s*\d+\s*\)", "", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _match(target_norm: str, candidates: list[CrmPerson]) -> CrmPerson | None:
    t = target_norm.split()
    if not t:
        return None
    for p in candidates:
        if p.normalized_name == target_norm:
            return p
    tlast, tfirst = t[-1], t[0]
    for p in candidates:
        c = p.normalized_name.split()
        if c and c[-1] == tlast and c[0][:1] == tfirst[:1]:
            return p
    return None


def reconcile_roster(session: Session, d: CrmDistrict, roster: dict) -> dict:
    """Mark who's still current vs former, and catch superintendent changes."""
    ts = now()
    stats = {"confirmed": 0, "departed": 0, "added": 0, "supt_change": 0}
    people = session.execute(select(CrmPerson).where(CrmPerson.district_id == d.id)).scalars().all()
    board = [p for p in people if p.role == "board_member" and p.status == "current"]
    supts = [p for p in people if p.role == "superintendent" and p.status == "current"]

    sup_name = roster.get("superintendent")
    if sup_name:
        sup_norm = norm_name(sup_name)
        match = _match(sup_norm, supts)
        if match:
            match.last_seen_at = ts
            stats["confirmed"] += 1
        else:
            for old in supts:
                old.status, old.departed_at = "former", ts
            session.add(CrmPerson(district_id=d.id, role="superintendent", name=sup_name,
                                   normalized_name=sup_norm, status="current",
                                   first_seen_at=ts, last_seen_at=ts))
            stats["supt_change"] += 1

    member_norms = {norm_name(m): m for m in roster.get("board_members", [])}
    matched_ids: set = set()
    for mnorm, mname in member_norms.items():
        match = _match(mnorm, [p for p in board if p.id not in matched_ids])
        if match:
            match.last_seen_at = ts
            matched_ids.add(match.id)
            stats["confirmed"] += 1
        else:
            session.add(CrmPerson(district_id=d.id, role="board_member", name=mname,
                                   normalized_name=mnorm, status="current",
                                   first_seen_at=ts, last_seen_at=ts))
            stats["added"] += 1
    for p in board:
        if p.id not in matched_ids:
            p.status, p.departed_at = "former", ts
            stats["departed"] += 1
    return stats


def verify_district_emails(session: Session, d: CrmDistrict, found_on_site: set) -> dict:
    ts = now()
    stats = {"checked": 0, "site_verified": 0}
    people = session.execute(select(CrmPerson).where(CrmPerson.district_id == d.id)).scalars().all()
    for p in people:
        emails = session.execute(select(CrmEmail).where(CrmEmail.person_id == p.id)).scalars().all()
        for e in emails:
            if e.email in found_on_site:
                e.status, e.confidence, e.source = "verified", 0.95, "district_site"
                stats["site_verified"] += 1
            else:
                status, conf = validate.classify(e.email)
                e.status, e.confidence = status, conf
            e.last_checked = ts
            stats["checked"] += 1
    return stats


def _has_accurate(session: Session, p: CrmPerson) -> bool:
    emails = session.execute(select(CrmEmail).where(CrmEmail.person_id == p.id)).scalars().all()
    return any(e.status in accuracy.ACCURATE for e in emails)


def improve_accuracy(session: Session, d: CrmDistrict, domain: str | None) -> dict:
    people = session.execute(select(CrmPerson).where(CrmPerson.district_id == d.id)).scalars().all()
    if not domain:
        for p in people:
            emails = session.execute(select(CrmEmail).where(CrmEmail.person_id == p.id)).scalars().all()
            for e in emails:
                if "@" in e.email:
                    domain = e.email.split("@", 1)[1]
                    break
            if domain:
                break
    if not domain:
        return {"confirmed": 0, "pattern": 0}

    fresh, stale = [], []
    for p in people:
        emails = session.execute(select(CrmEmail).where(CrmEmail.person_id == p.id)).scalars().all()
        for e in emails:
            if e.status in accuracy.ACCURATE:
                fresh.append((p.name, e.email))
            elif e.status in ("valid_mx", "imported"):
                stale.append((p.name, e.email))
    fmt = accuracy.detect_format(fresh) or accuracy.detect_format(stale)

    stats = {"confirmed": 0, "pattern": 0}
    for p in people:
        if p.status != "current" or _has_accurate(session, p):
            continue
        existing = session.execute(select(CrmEmail).where(CrmEmail.person_id == p.id)).scalars().all()
        existing_addrs = {e.email for e in existing}
        cand = accuracy.candidate(p.name, fmt[0], fmt[1]) if fmt else None
        hit = accuracy.find_or_confirm(p.name, domain, cand)
        if hit:
            email, tier = hit
            if email not in existing_addrs:
                session.add(CrmEmail(person_id=p.id, email=email, source="web",
                                      status=tier, confidence=0.85, last_checked=now()))
            stats["confirmed"] += 1
        elif cand and cand not in existing_addrs:
            session.add(CrmEmail(person_id=p.id, email=cand, source="pattern",
                                  status="pattern", confidence=0.4, last_checked=now()))
            stats["pattern"] += 1
    session.commit()
    return stats


def process_district(session: Session, d: CrmDistrict, render: bool = False) -> dict:
    res = discover_emails(d.website, render=render)
    found = set(res["emails"])
    if res.get("platform"):
        d.cms_platform = res["platform"]
    if res.get("board_pages") and not d.board_url:
        d.board_url = res["board_pages"][0]

    emails = verify_district_emails(session, d, found)
    roster = extract_roster(res.get("board_text", ""))
    rstats = reconcile_roster(session, d, roster) if roster else {}
    acc = improve_accuracy(session, d, res.get("domain"))

    people = session.execute(select(CrmPerson).where(CrmPerson.district_id == d.id)).scalars().all()
    contactable = sum(1 for p in people if p.status == "current" and _has_accurate(session, p))
    d.last_crawled_at = now()
    d.last_crawl_note = (f"site={emails['site_verified']} web_confirmed={acc['confirmed']} "
                         f"contactable={contactable} roster={'yes' if roster else 'n/a'}")
    session.commit()
    return {"district": d.name, "state": d.state, **emails, "roster": bool(roster),
            "contactable": contactable, **acc, **rstats}
