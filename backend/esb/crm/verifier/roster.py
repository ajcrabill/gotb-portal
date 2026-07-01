"""Extract the CURRENT board roster + superintendent from board-page text.

Ported from coach-devon's verifier/roster.py. Fixed a real bug found in the
source: it called llm.call_json(), which doesn't exist on services/llm.py
(only complete_json() does) — roster extraction was silently broken there
(AttributeError swallowed by a blanket except).
"""
from __future__ import annotations

from esb.crm import llm

SYS = ("You extract the CURRENT school board roster and CURRENT superintendent from a "
       "school district's official web page text. Ignore former/emeritus members, staff "
       "who are not board members, and meeting attendees. Return JSON only.")


def extract_roster(text: str) -> dict | None:
    if not text or not llm.configured():
        return None
    user = (
        "From the district web page text below, list the CURRENT superintendent and the "
        "CURRENT elected school board members (names only). Return JSON exactly: "
        '{"superintendent": "Full Name" or null, "board_members": ["Full Name", ...]}.\n\n'
        f"PAGE TEXT:\n{text}"
    )
    try:
        data = llm.complete_json_sync(SYS, user, max_tokens=800)
    except Exception:
        return None
    supt = (data.get("superintendent") or "")
    supt = supt.strip() or None if isinstance(supt, str) else None
    members = [m.strip() for m in (data.get("board_members") or [])
               if isinstance(m, str) and m.strip()]
    if not supt and not members:
        return None
    return {"superintendent": supt, "board_members": members}
