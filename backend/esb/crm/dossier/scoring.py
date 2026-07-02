"""Confidence scoring — source-tier + corroboration, per RESEARCH_PLAN.md §1.
Adapted from the Admiralty Code / NATO source-reliability framework.
"""
from __future__ import annotations

import re
import urllib.parse

# Tier weights (source_tier stored on CrmClaim as the tier name)
TIER_WEIGHTS = {
    "primary": 1.00,
    "high": 0.85,
    "medium": 0.65,
    "low": 0.35,
}

CONFIDENCE_THRESHOLD = 0.9
_CORROBORATION_STEP = 0.05
_CORROBORATION_CAP = 0.15

_HIGH_TIER_DOMAINS = (
    "ballotpedia.org", "wikipedia.org", "nces.ed.gov",
    "followthemoney.org", "opensecrets.org",
)
_LOW_TIER_DOMAIN_HINTS = (
    "blogspot.", "wordpress.com", "medium.com", "substack.com",
    "reddit.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "tiktok.com", "spokeo.com", "peoplefinder", "whitepages.com",
    "forum", "quora.com",
)
_MAJOR_NEWS_DOMAINS = (
    "nytimes.com", "washingtonpost.com", "wsj.com", "apnews.com", "reuters.com",
    "npr.org", "usatoday.com", "cnn.com", "nbcnews.com", "abcnews.go.com",
    "cbsnews.com", "chalkbeat.org", "edweek.org", "propublica.org",
)


def _domain(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def classify_source_tier(url: str, official_domain: str = "") -> str:
    """Classify a source URL into primary/high/medium/low per §1's table."""
    domain = _domain(url)
    if not domain:
        return "low"

    if domain.endswith(".gov") or domain.endswith(".mil"):
        return "primary"
    if official_domain and (domain == official_domain or domain.endswith("." + official_domain)):
        return "primary"

    if any(domain == d or domain.endswith("." + d) for d in _HIGH_TIER_DOMAINS):
        return "high"
    if any(domain == d or domain.endswith("." + d) for d in _MAJOR_NEWS_DOMAINS):
        return "high"

    if any(hint in domain for hint in _LOW_TIER_DOMAIN_HINTS):
        return "low"

    # Local news / trade publications / press releases — the broad middle tier.
    # News-shaped domains (has "news" in it, or is a .org/.edu press page) lean medium;
    # everything else uncategorized also defaults to medium rather than silently
    # inflating to high or deflating to low without a specific signal either way.
    return "medium"


def _normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def score_claims(claims: list) -> None:
    """Mutates each CrmClaim's .confidence in place using tier weight +
    corroboration bonus. Corroboration = independent domains (not just
    independent URLs — two articles on the same site don't count as
    independent corroboration) reporting the same (field, value)."""
    groups: dict[tuple[str, str], list] = {}
    for c in claims:
        key = (c.field, _normalize_value(c.value))
        groups.setdefault(key, []).append(c)

    for members in groups.values():
        domains = {_domain(c.source_url) for c in members if c.source_url}
        corroboration_bonus = min(_CORROBORATION_STEP * (len(domains) - 1), _CORROBORATION_CAP)
        for c in members:
            base = TIER_WEIGHTS.get(c.source_tier, TIER_WEIGHTS["low"])
            if c.verdict == "false":
                c.confidence = 0.0
                continue
            if c.verdict == "insufficient":
                base = min(base, TIER_WEIGHTS["medium"])
            c.confidence = round(min(base + corroboration_bonus, 0.98), 3)
