"""NewsworthyScraper — detect school boards in trouble as outreach triggers.

Ported from coach-devon's newsworthy/scan.py. Per-district news queries;
a news item becomes a Signal only if it carries a governance-trouble term.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.crm import connectors as C
from esb.models.crm import CrmDistrict, CrmSignal

HIGH = ["state takeover", "takeover", "no confidence", "no-confidence", "recall",
        "resign", "resigns", "resignation", "stepping down", "fired", "ousted",
        "lawsuit", "sued", "investigation", "indicted", "misconduct", "censure",
        "removed from office", "forced out"]
MEDIUM = ["budget deficit", "deficit", "layoffs", "school closure", "closing schools",
          "superintendent search", "interim superintendent", "controversy", "protest",
          "walkout", "book ban", "audit", "split board", "board fight", "turmoil"]

_TERMS = [(t, "high") for t in HIGH] + [(t, "medium") for t in MEDIUM]
_SEV_RANK = {"": 0, "low": 1, "medium": 2, "high": 3}


def assess(text: str) -> tuple[str, list[str]]:
    """Return (severity, matched_terms). severity '' means not newsworthy-trouble."""
    low = text.lower()
    matched = [t for t, _ in _TERMS if re.search(r"\b" + re.escape(t) + r"\b", low)]
    if not matched:
        return "", []
    sev = "high" if any(s == "high" for t, s in _TERMS if t in matched) else "medium"
    return sev, matched


def scan_district(session: Session, d: CrmDistrict) -> int:
    query = f'"{d.name}" {d.state} school board'
    found = 0
    best = 0
    for item in C.news(query, limit=8):
        blob = f"{item.title} {item.snippet}"
        sev, terms = assess(blob)
        if not sev:
            continue
        exists = session.execute(
            select(CrmSignal).where(CrmSignal.district_id == d.id, CrmSignal.url == item.url)
        ).scalar_one_or_none()
        if exists:
            continue
        session.add(CrmSignal(
            district_id=d.id, kind=terms[0], severity=sev,
            headline=item.title[:500], snippet=item.snippet[:600],
            url=item.url[:800], matched_terms=", ".join(terms)[:300],
        ))
        found += 1
        best = max(best, _SEV_RANK[sev])
    if best:
        d.situation_score = max(d.situation_score, best)
    session.commit()
    return found
