"""CGCS (Council of the Great City Schools) membership sync.

Scrapes the public member districts list at cgcs.org and flags matching
districts as CGCS members in both crm_districts (prospecting universe) and
districts (actual ESB clients). CGCS membership is a hard block — ESB never
engages, assesses, or routes leads to a CGCS member district — so this list
must be kept current.

robots.txt for www.cgcs.org allows crawling this page for User-agent: *
(Crawl-delay: 5, respected below via a single fetch — no multi-page crawl).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.models.crm import CrmDistrict
from esb.models.district import District

CGCS_URL = "https://www.cgcs.org/member-services/member-districts-list"
_USER_AGENT = "ESB-Portal-Sync/1.0 (+https://effectiveschoolboards.com; contact: aj@effectiveschoolboards.com)"

_LI_RE = re.compile(r'<li id="siteshortcut-\d+"><a[^>]*>([^<]+)</a></li>')
_FUZZY_THRESHOLD = 0.90


def normalize_name(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


async def fetch_cgcs_member_names() -> list[str]:
    """Fetch and parse the CGCS member districts list. Returns raw display names."""
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": _USER_AGENT}) as client:
        resp = await client.get(CGCS_URL)
        resp.raise_for_status()
        html = resp.text

    names = _LI_RE.findall(html)
    # de-dup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        n = n.strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _best_match(target_norm: str, candidates: list[tuple[str, str]]) -> tuple[str, float] | None:
    """candidates: list of (id, normalized_name). Returns (id, score) for the best match above threshold."""
    best_id, best_score = None, 0.0
    for cid, cnorm in candidates:
        if cnorm == target_norm:
            return cid, 1.0
        score = SequenceMatcher(None, target_norm, cnorm).ratio()
        if score > best_score:
            best_id, best_score = cid, score
    if best_id is not None and best_score >= _FUZZY_THRESHOLD:
        return best_id, best_score
    return None


class SyncResult:
    def __init__(self) -> None:
        self.total_cgcs_names = 0
        self.crm_matched: list[dict] = []
        self.crm_unmatched: list[str] = []
        self.portal_matched: list[dict] = []
        self.portal_unmatched: list[str] = []


async def sync_cgcs_membership(db: AsyncSession, apply: bool = True) -> SyncResult:
    """Fetch the CGCS list and match+flag against crm_districts and districts.

    apply=False runs a dry-run (match only, no writes) — useful for preview.
    """
    result = SyncResult()
    names = await fetch_cgcs_member_names()
    result.total_cgcs_names = len(names)

    crm_rows = (await db.execute(select(CrmDistrict.id, CrmDistrict.normalized_name))).all()
    crm_candidates = [(str(r[0]), r[1]) for r in crm_rows]

    portal_rows = (await db.execute(select(District.id, District.name))).all()
    portal_candidates = [(str(r[0]), normalize_name(r[1])) for r in portal_rows]

    crm_matched_ids: list[str] = []
    portal_matched_ids: list[str] = []

    for raw_name in names:
        target_norm = normalize_name(raw_name)

        crm_hit = _best_match(target_norm, crm_candidates)
        if crm_hit:
            crm_matched_ids.append(crm_hit[0])
            result.crm_matched.append({"cgcs_name": raw_name, "district_id": crm_hit[0], "score": round(crm_hit[1], 3)})
        else:
            result.crm_unmatched.append(raw_name)

        portal_hit = _best_match(target_norm, portal_candidates)
        if portal_hit:
            portal_matched_ids.append(portal_hit[0])
            result.portal_matched.append({"cgcs_name": raw_name, "district_id": portal_hit[0], "score": round(portal_hit[1], 3)})
        else:
            result.portal_unmatched.append(raw_name)

    if apply:
        if crm_matched_ids:
            await db.execute(
                CrmDistrict.__table__.update()
                .where(CrmDistrict.id.in_(crm_matched_ids))
                .values(cgcs_member=True)
            )
        if portal_matched_ids:
            await db.execute(
                District.__table__.update()
                .where(District.id.in_(portal_matched_ids))
                .values(is_cgcs_member=True)
            )
        await db.commit()

    return result
