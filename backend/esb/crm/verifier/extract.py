"""Extract emails from HTML, including common obfuscation patterns.

Ported from coach-devon's verifier/extract.py.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from esb.crm.verifier.validate import EMAIL_RE

_DEOBFUSCATE = [
    (re.compile(r"\s*[\[\(]?\s*(?:at|AT|@)\s*[\]\)]?\s*"), "@"),
    (re.compile(r"\s*[\[\(]?\s*(?:dot|DOT)\s*[\]\)]?\s*"), "."),
]
_RAW_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def deobfuscate(text: str) -> str:
    for pat, rep in _DEOBFUSCATE:
        text = pat.sub(rep, text)
    return text


def emails_from_html(html: str, domain: str | None = None) -> set[str]:
    """All emails on the page (mailto links + visible text, deobfuscated).
    If a domain is given, restrict to that domain (district-official addresses)."""
    found: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.select("a[href^=mailto]"):
        addr = a.get("href", "")[7:].split("?")[0].strip().lower()
        if EMAIL_RE.match(addr):
            found.add(addr)

    text = deobfuscate(soup.get_text(" "))
    for m in _RAW_EMAIL.findall(text):
        found.add(m.lower())

    found = {e for e in found if EMAIL_RE.match(e)}
    if domain:
        found = {e for e in found if e.endswith("@" + domain)}
    return {e for e in found if not e.startswith(("example@", "email@", "your@", "name@"))}
