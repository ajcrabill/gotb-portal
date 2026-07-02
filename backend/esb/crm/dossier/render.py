"""Render a completed dossier into the markdown deliverable — the sole
practitioner-facing output (per AJ, 2026-07-01). Structure follows
templates/person_template.md / organization_template.md. Only claims at
or above scoring.CONFIDENCE_THRESHOLD appear in the body; everything else
stays in the crm_claims table for audit but is omitted here, per instruction.
"""
from __future__ import annotations

from datetime import datetime, timezone

from esb.crm.dossier.scoring import CONFIDENCE_THRESHOLD

# field-name prefixes -> which template section they belong under.
# Extraction is free-text (field names come from the LLM, not a fixed enum),
# so this is a best-effort router, not an exhaustive switch — anything that
# doesn't match a known prefix lands in "Other Findings" rather than being
# dropped, so nothing silently disappears from the audit trail's visible half.
_PERSON_SECTIONS = [
    ("Current Role", ("title", "role", "position", "start_date", "tenure", "term", "contract")),
    ("Career History", ("career", "employment", "previous", "prior_role", "former")),
    ("Education", ("education", "degree", "school", "university", "certification", "license")),
    ("Track Record & Public Positions", ("initiative", "priority", "vote", "committee", "outcome")),
    ("Public Statements & Media Presence", ("quote", "statement", "op-ed", "interview")),
    ("News Coverage", ("news", "coverage", "article")),
    ("Areas of Scrutiny", ("lawsuit", "controversy", "investigation", "complaint", "resign", "no_confidence", "scrutiny")),
    ("Campaign Finance & Political Activity", ("donor", "campaign", "pac", "election", "opponent")),
    ("Professional Network & Affiliations", ("affiliation", "board_member_of", "association", "network")),
    ("Public Financial / Property Footprint", ("property", "business", "director", "filing")),
    ("Newsletter", ("newsletter_subscriber",)),
]

_ORG_SECTIONS = [
    ("Basic Profile", ("enrollment", "schools", "locale", "district_type", "nces")),
    ("Governance Structure", ("board", "governance", "election_method", "term")),
    ("Recent Leadership History", ("superintendent_change", "turnover", "leadership")),
    ("Financial Health", ("revenue", "expenditure", "budget", "bond", "finance")),
    ("Academic Performance", ("test_score", "graduation", "performance", "accreditation")),
    ("Demographic & Enrollment Trends", ("demographic", "enrollment_trend", "socioeconomic")),
    ("Strategic Priorities", ("strategic", "priority", "goal", "initiative")),
    ("Areas of Scrutiny", ("lawsuit", "controversy", "investigation", "takeover", "walkout", "scrutiny")),
    ("News Coverage", ("news", "coverage", "article")),
    ("Community Context", ("union", "community", "political")),
]


def _section_for(field: str, sections: list[tuple[str, tuple[str, ...]]]) -> str | None:
    f = field.lower()
    for title, prefixes in sections:
        if any(p in f for p in prefixes):
            return title
    return None


def _fmt_claim(c) -> str:
    return f"- {c.value} *(source: [{c.source_url}]({c.source_url}), confidence {c.confidence:.2f})*"


def render_markdown(dossier, claims: list, searches: list, is_org: bool, subject_label: str, wayback_note: str = "") -> str:
    confirmed = [c for c in claims if c.confidence >= CONFIDENCE_THRESHOLD]
    below_threshold_count = len([c for c in claims if 0 < c.confidence < CONFIDENCE_THRESHOLD])

    sections = _ORG_SECTIONS if is_org else _PERSON_SECTIONS
    by_section: dict[str, list] = {}
    other: list = []
    for c in confirmed:
        sec = _section_for(c.field, sections)
        if sec:
            by_section.setdefault(sec, []).append(c)
        else:
            other.append(c)

    lines: list[str] = []
    lines.append(f"# {subject_label}")
    lines.append("")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines.append(f"*Dossier generated {now} · {len(searches)} sources reviewed · {len(confirmed)} claims at ≥{CONFIDENCE_THRESHOLD:.0%} confidence*")
    lines.append("")

    if dossier.summary:
        lines.append("## Executive Summary")
        lines.append(dossier.summary)
        lines.append("")

    for title, _prefixes in sections:
        items = by_section.get(title)
        if not items:
            continue
        lines.append(f"## {title}")
        for c in items:
            lines.append(_fmt_claim(c))
        lines.append("")

    if other:
        lines.append("## Other Findings")
        for c in other:
            lines.append(f"- **{c.field}:** {_fmt_claim(c)[2:]}")
        lines.append("")

    if wayback_note:
        lines.append("## Historical Note")
        lines.append(wayback_note)
        lines.append("")

    lines.append("## Sources")
    for s in searches:
        if s.found and s.url:
            lines.append(f"- [{s.notes or s.url}]({s.url}) — {s.source}/{s.method}")
    lines.append("")

    lines.append("## Research Gaps")
    all_titles = {t for t, _ in sections}
    covered = set(by_section.keys())
    missing = sorted(all_titles - covered)
    if missing:
        lines.append("Not found at sufficient confidence:")
        for m in missing:
            lines.append(f"- {m}")
    if below_threshold_count:
        lines.append(f"- {below_threshold_count} additional claim(s) were found but fell below the {CONFIDENCE_THRESHOLD:.0%} confidence threshold and were omitted — available in the audit log if you want to review them manually.")
    if not missing and not below_threshold_count:
        lines.append("None — every template section has at least one confirmed finding.")
    lines.append("")

    return "\n".join(lines)
