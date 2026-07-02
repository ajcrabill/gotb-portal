"""Per-technique effectiveness stats — the learning loop AJ asked for
(2026-07-02): track every individual search technique (including each
specific matrix pivot, e.g. matrix:education vs matrix:career) across
every dossier ever built, so unproductive ones can be identified and
phased out of pivot_plan()/static_plan() over time.
"""
from __future__ import annotations

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from esb.models.crm import CrmClaim, CrmSearch


def technique_effectiveness(session: Session) -> list[dict]:
    """One row per technique, across ALL dossiers. confirmation_rate is the
    fraction of that technique's searches that produced at least one claim
    which reached the 0.9 confidence threshold — the single number to
    watch when deciding whether a technique is earning its keep."""
    search_rows = session.execute(
        select(
            CrmSearch.technique,
            func.count(CrmSearch.id),
            func.sum(cast(CrmSearch.found, Integer)),
        ).group_by(CrmSearch.technique)
    ).all()
    searches_by_technique = {t: (total, found or 0) for t, total, found in search_rows}

    claim_rows = session.execute(
        select(
            CrmClaim.technique,
            func.count(CrmClaim.id),
            func.sum(cast(CrmClaim.confidence >= 0.9, Integer)),
        ).group_by(CrmClaim.technique)
    ).all()
    claims_by_technique = {t: (total, confirmed or 0) for t, total, confirmed in claim_rows}

    all_techniques = set(searches_by_technique) | set(claims_by_technique)
    out = []
    for t in all_techniques:
        if not t:
            continue
        searches_run, results_found = searches_by_technique.get(t, (0, 0))
        claims_extracted, claims_confirmed = claims_by_technique.get(t, (0, 0))
        out.append({
            "technique": t,
            "searches_run": searches_run,
            "results_found": results_found,
            "claims_extracted": claims_extracted,
            "claims_confirmed": claims_confirmed,
            "confirmation_rate": round(claims_confirmed / searches_run, 3) if searches_run else 0.0,
        })

    out.sort(key=lambda r: r["confirmation_rate"], reverse=True)
    return out
