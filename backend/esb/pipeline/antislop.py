"""Anti-slop scanner — mechanical, zero-token quality control for ESB portal content.

Ported from Coach Libra's antislop.py and extended for ESB governance content.
Catches AI tells, clichés, weak constructions, and ESB IP violations without any
LLM call (same text in → identical findings out).

Two hard rules beyond the slop tiers:
  1. IP guard: "Coach" in client/practitioner-facing copy is a TIER1 kill
     (only enforced when is_client_facing=True — internal role labels are fine).
  2. Sanctioned-phrase allow-list: certain phrases read as slop but are correct
     ESB terminology and must never be flagged.

scan() → findings dict (non-destructive).
clean() → (fixed_text, findings) with only safe, meaning-preserving fixes applied.
"""
from __future__ import annotations

import re

# ── Tiered banned vocabulary ───────────────────────────────────────────────────
# Tier 1 = strong AI tells + ESB IP violations → severity 5 each
# Tier 2 = overused filler → severity 2 each
# Tier 3 = weak hedges/intensifiers → severity 1 each

TIER1 = [
    # AI tells (from Coach Libra base)
    "delve", "tapestry", "realm", "beacon", "underscore", "multifaceted",
    "seamless", "transformative", "leverage", "pivotal", "robust", "navigate",
    "testament", "treasure trove", "in today's world", "ever-evolving",
    "it's worth noting", "needless to say", "at the end of the day",
    # ESB voice violations
    "empower", "impactful", "synergy", "best practices", "move the needle",
    "circle back", "take this to the next level", "game changer", "game-changer",
    "paradigm shift", "thought leader", "data-driven", "drill down",
    "boil the ocean", "bandwidth", "deep dive",
]

TIER2 = [
    "moreover", "furthermore", "additionally", "however", "nevertheless",
    "utilize", "facilitate", "plethora", "myriad", "embark", "unleash",
    "elevate", "foster", "harness", "vibrant", "bustling", "comprehensive",
    "innovative", "cutting-edge", "forward-thinking", "holistic", "robust",
    "streamline", "optimize", "scale", "ecosystem", "landscape",
]

TIER3 = [
    "very", "really", "actually", "basically", "literally", "just", "simply",
    "quite", "rather", "somewhat", "definitely", "certainly", "clearly",
]

_TIER_WEIGHT = {1: 5, 2: 2, 3: 1}

# ── Client-facing IP guard ─────────────────────────────────────────────────────
# "Coach" must never appear in client/practitioner-facing copy (credential rule).
# Only enforced when is_client_facing=True to allow internal role labels.
_COACH_RE = re.compile(r"\bcoach\b", re.I)

# ── Sanctioned phrases (never flag these, even if they look like slop) ─────────
# These are correct ESB terminology. Checked before tier scanning.
SANCTIONED_PHRASES = [
    "certified great on their behalf practitioner",
    "great on their behalf",
    "not yet validated",
    "will be benchmarked once norms publish",
    "indicative",
    "self-scored",
    "focus mindset",
    "clarify priorities",
    "monitor progress",
    "align resources",
    "communicate results",
    "beginning focus",
    "beginning clarity",
    "beginning monitoring",
    "beginning alignment",
    "beginning communication",
    "emerging focus",
    "effective focus",
    "highly effective focus",
]

# ── ESB IP hard-blocks (must never appear in any ESB content) ─────────────────
# Violating these is a HARD FAIL regardless of context.
_IP_BLOCKS = [
    "sofg",
    "student outcomes focused governance",
    "lone star governance",
    "lsg",
]
_IP_BLOCK_RES = [re.compile(r"\b" + re.escape(p) + r"\b", re.I) for p in _IP_BLOCKS]

# ── AI narrative "tells" ──────────────────────────────────────────────────────
_TELL_RES = [
    re.compile(r"\b(a|the)\s+(shiver|chill|warmth)\s+ran\s+(up|down)\b", re.I),
    re.compile(r"\bbreath\s+(he|she|they|I)\s+didn'?t\s+know\b", re.I),
    re.compile(r"\blanded\s+like\s+a\b", re.I),
    re.compile(r"\bcouldn'?t\s+help\s+but\b", re.I),
    re.compile(r"\blittle\s+did\s+(he|she|they|I)\s+know\b", re.I),
    # Governance-specific AI tells
    re.compile(r"\bjourneys?\s+(forward|ahead)\b", re.I),
    re.compile(r"\bspearhead(ing|s|ed)?\b", re.I),
]


def _count_phrase(text_l: str, phrase: str) -> int:
    if " " in phrase:
        return text_l.count(phrase)
    return len(re.findall(rf"\b{re.escape(phrase)}\b", text_l))


def _is_sanctioned(text_l: str, phrase: str) -> bool:
    return phrase in text_l


def scan(
    text: str,
    *,
    is_client_facing: bool = True,
    never_rules: list[str] | None = None,
    ruleset_version: str = "esb-v1",
) -> dict:
    """
    Scan text for slop, IP violations, and ESB voice violations.

    Args:
        text: content to scan
        is_client_facing: if True, "Coach" triggers a hard IP violation (TIER1)
        never_rules: list of NEVER rule strings (same format as Coach Libra)
        ruleset_version: version of the ruleset used (stamped on every verdict)

    Returns dict with keys:
        banned, tells, never_hits, ip_violations, structural,
        severity, score (0-100, 100=clean), clean (bool), ruleset_version
    """
    text = text or ""
    tl = text.lower()
    words = re.findall(r"[a-z']+", tl)
    n_words = max(len(words), 1)

    # Hard IP block check — these are ALWAYS a fail regardless of other scores
    ip_violations = []
    for rx in _IP_BLOCK_RES:
        hits = rx.findall(text)
        if hits:
            ip_violations.append({"pattern": rx.pattern, "count": len(hits)})

    # "Coach" in client-facing copy
    if is_client_facing:
        coach_hits = _COACH_RE.findall(text)
        if coach_hits:
            ip_violations.append({"pattern": "coach (client-facing)", "count": len(coach_hits)})

    # Tier scanning — skip sanctioned phrases
    sanctioned_in_text = {p for p in SANCTIONED_PHRASES if _is_sanctioned(tl, p)}

    banned = []
    for tier, lst in ((1, TIER1), (2, TIER2), (3, TIER3)):
        for w in lst:
            # Don't flag a term that appears only inside a sanctioned phrase
            count = _count_phrase(tl, w)
            if not count:
                continue
            # Subtract occurrences covered by sanctioned phrases
            covered = sum(
                _count_phrase(p, w) * tl.count(p)
                for p in sanctioned_in_text
                if w in p
            )
            net = max(0, count - covered)
            if net:
                banned.append({"term": w, "tier": tier, "count": net})

    tells = []
    for rx in _TELL_RES:
        hits = rx.findall(text)
        if hits:
            tells.append({"pattern": rx.pattern, "count": len(hits)})

    never_hits = []
    for rule in (never_rules or []):
        for q in re.findall(r'"([^"]+)"', rule):
            c = _count_phrase(tl, q.lower())
            if c:
                never_hits.append({"rule": rule, "term": q, "count": c})

    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    openers = [re.findall(r"[A-Za-z']+", p)[:1] for p in paras]
    openers = [o[0].lower() for o in openers if o]
    repeated_openers = {w: c for w, c in _counter(openers).items() if c >= 3}
    em_dashes = text.count("—")
    structural = {
        "em_dash_per_1k_words": round(1000 * em_dashes / n_words, 2),
        "exclaims": text.count("!"),
        "ellipses": text.count("...") + text.count("…"),
        "repeated_paragraph_openers": repeated_openers,
    }

    severity = (
        sum(_TIER_WEIGHT[b["tier"]] * b["count"] for b in banned)
        + 5 * sum(t["count"] for t in tells)
        + 6 * sum(h["count"] for h in never_hits)
        + 3 * sum(repeated_openers.values())
        + (2 if structural["em_dash_per_1k_words"] > 8 else 0)
        + 20 * sum(v["count"] for v in ip_violations)  # IP violations heavily penalized
    )
    density = 1000 * severity / n_words
    score = max(0, min(100, round(100 - density)))
    has_ip_violation = bool(ip_violations)

    return {
        "banned": banned,
        "tells": tells,
        "never_hits": never_hits,
        "ip_violations": ip_violations,
        "structural": structural,
        "severity": severity,
        "score": score,
        "clean": severity == 0,
        "has_ip_violation": has_ip_violation,
        "ruleset_version": ruleset_version,
    }


def clean(
    text: str,
    *,
    is_client_facing: bool = True,
    never_rules: list[str] | None = None,
) -> tuple[str, dict]:
    """Apply ONLY safe, meaning-preserving fixes. Returns (fixed_text, findings)."""
    findings = scan(text, is_client_facing=is_client_facing, never_rules=never_rules)
    fixed = text or ""
    fixed = re.sub(r"\.{3,}", "…", fixed)
    fixed = re.sub(r"[ \t]{2,}", " ", fixed)
    fixed = re.sub(r"\s+([,.;:!?])", r"\1", fixed)
    fixed = re.sub(r"!{2,}", "!", fixed)
    return fixed, findings


def _counter(items: list) -> dict:
    d: dict = {}
    for it in items:
        d[it] = d.get(it, 0) + 1
    return d
