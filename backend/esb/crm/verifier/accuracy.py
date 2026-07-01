"""Email accuracy — the binding constraint of the whole system.

Ported from coach-devon's verifier/accuracy.py.

Tiers (status on EmailAddr):
  verified      — published on the district's official board/leadership page (+MX). ACCURATE.
  web_confirmed — a derived candidate confirmed via web/site search, OR a direct
                  address found online at the district domain. ACCURATE.
  pattern       — derived from the district's email format but unconfirmed. NOT contactable.
  valid_mx / imported — domain resolves, address unconfirmed. NOT accurate enough alone.
"""
from __future__ import annotations

import re
from collections import Counter

from esb.crm import connectors as C

ACCURATE = ("verified", "web_confirmed")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_HONORIFICS = {"dr", "mr", "mrs", "ms", "mx", "hon", "rev", "prof", "the"}
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "edd", "md"}

PATTERNS: list[tuple[str, callable]] = [
    ("first.last", lambda f, l: f"{f}.{l}"),
    ("flast", lambda f, l: f"{f[0]}{l}"),
    ("firstlast", lambda f, l: f"{f}{l}"),
    ("f.last", lambda f, l: f"{f[0]}.{l}"),
    ("firstl", lambda f, l: f"{f}{l[0]}"),
    ("first_last", lambda f, l: f"{f}_{l}"),
    ("lastf", lambda f, l: f"{l}{f[0]}"),
    ("last.first", lambda f, l: f"{l}.{f}"),
    ("first", lambda f, l: f"{f}"),
]
_FMT = dict(PATTERNS)


def split_name(name: str) -> tuple[str, str] | None:
    toks = [t.lower() for t in re.sub(r"[^A-Za-z ]", " ", name or "").split()]
    toks = [t for t in toks if t not in _HONORIFICS and t not in _SUFFIXES and len(t) > 1]
    if len(toks) < 2:
        return None
    return toks[0], toks[-1]


def detect_format(pairs: list[tuple[str, str]]) -> tuple[str, str] | None:
    votes: Counter = Counter()
    for name, email in pairs:
        lp, _, dom = (email or "").lower().partition("@")
        nm = split_name(name)
        if not dom or not nm:
            continue
        f, l = nm
        for key, fn in PATTERNS:
            try:
                if fn(f, l) == lp:
                    votes[(key, dom)] += 1
                    break
            except Exception:
                pass
    return votes.most_common(1)[0][0] if votes else None


def candidate(name: str, fmt_key: str, domain: str) -> str | None:
    nm = split_name(name)
    if not nm:
        return None
    f, l = nm
    try:
        return f"{_FMT[fmt_key](f, l)}@{domain}"
    except Exception:
        return None


def find_or_confirm(name: str, domain: str, guess: str | None) -> tuple[str, str] | None:
    """Search the web/site for this person's real address, or confirm the guess.
    Returns (email, 'web_confirmed') or None. Bounded: a couple of searches."""
    nm = split_name(name)
    if not nm:
        return None
    last = nm[1]

    if guess:
        for d in (C.web_search(f'"{guess}"') or [])[:5]:
            blob = f"{d.url} {d.title} {d.snippet}".lower()
            if guess.lower() in blob:
                return guess, "web_confirmed"

    for d in (C.web_search(f'{name} {domain} email') or [])[:3]:
        text = C.fetch_text(d.url) or (d.snippet or "")
        for em in EMAIL_RE.findall(text):
            em = em.lower()
            if em.endswith("@" + domain) and last in em.split("@")[0]:
                return em, "web_confirmed"
    return None
