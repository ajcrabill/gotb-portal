"""Wayback Machine / archive.org — recover removed or edited pages.

Free, no key, no meaningful rate limit at our volume. Used to check
official bio/staff/board pages for content that's since been quietly
edited or removed — one of the highest-value techniques in modern
investigative research (see RESEARCH_PLAN.md §3 for citations).
"""
from __future__ import annotations

from datetime import datetime

import httpx

UA = "ESB-Portal-Sync/1.0 (+https://effectiveschoolboards.com; contact: aj@effectiveschoolboards.com)"
CDX_URL = "http://web.archive.org/cdx/search/cdx"


def find_snapshots(url: str, limit: int = 10) -> list[dict]:
    """Query the CDX API for available snapshots of a URL.
    Returns [{"timestamp": "20200101120000", "status": "200"}, ...],
    oldest first."""
    try:
        with httpx.Client(headers={"User-Agent": UA}, timeout=15) as c:
            r = c.get(CDX_URL, params={
                "url": url, "output": "json", "limit": limit,
                "filter": "statuscode:200", "collapse": "timestamp:8",  # one per day
            })
            if r.status_code != 200:
                return []
            rows = r.json()
    except Exception:
        return []

    if not rows or len(rows) < 2:
        return []
    header = rows[0]
    ts_idx = header.index("timestamp")
    status_idx = header.index("statuscode")
    return [{"timestamp": row[ts_idx], "status": row[status_idx]} for row in rows[1:]]


def snapshot_url(url: str, timestamp: str) -> str:
    return f"https://web.archive.org/web/{timestamp}/{url}"


def earliest_and_latest_snapshot_text(url: str, max_chars: int = 4000) -> dict | None:
    """Fetch the earliest and latest available snapshot's text for a URL,
    for the pipeline to hand to the LLM and ask "did anything meaningful
    change between these two." Returns None if fewer than 2 snapshots
    exist (nothing to diff)."""
    snapshots = find_snapshots(url, limit=30)
    if len(snapshots) < 2:
        return None

    from esb.crm.connectors import fetch_text

    earliest, latest = snapshots[0], snapshots[-1]
    earliest_text = fetch_text(snapshot_url(url, earliest["timestamp"]), max_chars=max_chars)
    latest_text = fetch_text(snapshot_url(url, latest["timestamp"]), max_chars=max_chars)
    if not earliest_text and not latest_text:
        return None

    def _fmt(ts: str) -> str:
        try:
            return datetime.strptime(ts[:8], "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return ts

    return {
        "earliest_date": _fmt(earliest["timestamp"]), "earliest_text": earliest_text,
        "latest_date": _fmt(latest["timestamp"]), "latest_text": latest_text,
        "snapshot_count": len(snapshots),
    }
