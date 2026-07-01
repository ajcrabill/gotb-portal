"""Deterministic email validation: syntax + live MX lookup.

Ported from coach-devon's verifier/validate.py.
"""
from __future__ import annotations

import re

import dns.resolver

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

_mx_cache: dict[str, bool] = {}


def syntax_ok(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower().strip() if "@" in email else ""


def domain_has_mx(domain: str) -> bool:
    if not domain:
        return False
    if domain in _mx_cache:
        return _mx_cache[domain]
    ok = False
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        ok = len(answers) > 0
    except Exception:
        try:
            dns.resolver.resolve(domain, "A", lifetime=5)
            ok = True
        except Exception:
            ok = False
    _mx_cache[domain] = ok
    return ok


def classify(email: str) -> tuple[str, float]:
    if not syntax_ok(email):
        return "invalid_syntax", 0.0
    if domain_has_mx(domain_of(email)):
        return "valid_mx", 0.6
    return "bad_domain", 0.0
