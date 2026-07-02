"""NCES Common Core of Data (CCD) — direct district-detail lookup by LEA ID.

No formal query API for ad-hoc name search, but the district detail page
is directly addressable by NCES LEA ID (`nces_lea_id`, already captured
on both crm_districts and districts from the Devon CRM import), and is
plain server-rendered HTML — no headless rendering needed. Confirmed
working 2026-07-01: https://nces.ed.gov/ccd/districtsearch/district_detail.asp?ID2=4835700
"""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

UA = "ESB-Portal-Sync/1.0 (+https://effectiveschoolboards.com; contact: aj@effectiveschoolboards.com)"
DISTRICT_DETAIL_URL = "https://nces.ed.gov/ccd/districtsearch/district_detail.asp"


def fetch_district_detail_text(nces_lea_id: str, max_chars: int = 6000) -> str:
    """Fetch the NCES CCD district detail page and return cleaned visible
    text — handed to the LLM extraction seam same as any other document,
    since NCES doesn't publish a stable field-level schema for this page."""
    if not nces_lea_id:
        return ""
    try:
        with httpx.Client(headers={"User-Agent": UA}, timeout=15, follow_redirects=True) as c:
            r = c.get(DISTRICT_DETAIL_URL, params={"ID2": nces_lea_id})
            if r.status_code != 200:
                return ""
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(" ", strip=True)[:max_chars]
    except Exception:
        return ""
