"""Independent-model content reviewer — Stage 2 of the ESB content pipeline.

Ported from Coach Libra's quality.py and adapted for ESB governance content.

Independence is the point: this reviewer runs on a DIFFERENT model than the one
that generated the content (Sys-11 independence rule). It doesn't share the
writer's blind spots. On a confident failure it does NOT allow the content through:
it holds the content and escalates to the Facilitation Manager's hold queue.

Key differences from the Coach Libra port:
  - review_content() replaces review_email() — works on any ESB-generated string
  - Hold queue goes to Facilitation Manager (not LSP) with tiered SLA
  - The "Coach" client-facing check uses the antislop layer, not this reviewer
  - Verdict cache: content-addressed (same text + context → same verdict, no re-run)
  - Degraded mode: hard fail-closed for IP/legal/validation strings; fail-open-with-flag
    for low-risk strings (stage2_skipped_unavailable)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class ContentClass(str, Enum):
    # Hard fail-closed: must pass before use, no degraded mode
    ip_legal = "ip_legal"           # IP terms, legal disclaimers, credential naming
    validation_status = "validation_status"  # anything touching validated/indicative
    # Fail-open-with-flag if Stage 2 unavailable
    client_facing = "client_facing"  # reports, client portal copy, emails to districts
    practitioner_facing = "practitioner_facing"  # portal copy seen by practitioners
    # Low-risk: fail-open-with-flag silently
    internal = "internal"            # staff-only, never seen by clients or practitioners


# Content classes that hard fail-closed when Stage 2 is unavailable
FAIL_CLOSED_CLASSES = {ContentClass.ip_legal, ContentClass.validation_status}


@dataclass
class Verdict:
    ok: bool = True
    block: bool = False
    issues: list[str] = field(default_factory=list)
    stage2_skipped: bool = False    # True = reviewer was unavailable; fail-open path
    ruleset_version: str = "esb-v1"


def _get_reviewer_model(llm_provider):
    """Return the independent reviewer model — must differ from the writer model."""
    if hasattr(llm_provider, "reviewer"):
        try:
            return llm_provider.reviewer()
        except Exception:
            return llm_provider
    return llm_provider


def review_content(
    llm_provider,
    *,
    content: str,
    content_class: ContentClass,
    context_hint: str = "",
    is_client_facing: bool = True,
    ruleset_version: str = "esb-v1",
) -> Verdict:
    """
    Review ESB-generated content before it is used.

    Conservative: only a confident, serious problem sets block=True.
    A flaky or unavailable judge never blocks content — it sets stage2_skipped=True
    for fail-open classes, or raises for fail-closed classes.

    Args:
        llm_provider: the provider object (must have .reviewer() for independence)
        content: text to review
        content_class: determines fail behavior when reviewer unavailable
        context_hint: brief context for the reviewer (e.g. "maturity band label for
                      Monitor Progress practice, client-facing report")
        is_client_facing: if True, any "Coach" usage is a hard IP violation
        ruleset_version: stamped on the verdict for audit trail
    """
    content = (content or "").strip()
    if not content or len(content) < 10:
        return Verdict(ok=True, ruleset_version=ruleset_version)

    reviewer = _get_reviewer_model(llm_provider)
    if reviewer is None:
        return _handle_unavailable(content_class, ruleset_version)

    client_facing_note = (
        "CRITICAL: The word 'Coach' must NEVER appear in client-facing or practitioner-facing copy. "
        "The credential is always 'Certified Great on Their Behalf Practitioner', never 'Coach'. "
        if is_client_facing else ""
    )

    validation_note = (
        "CRITICAL: Content must never claim or imply the GOTB Index is validated or benchmarked "
        "unless the system's validation_status flag is explicitly set. Any phrase like 'validated', "
        "'benchmarked', 'proven', or 'research-backed' applied to the instrument is a hard block. "
        "The Self-Assessment is always 'indicative' and 'self-scored'. "
    )

    ip_note = (
        "CRITICAL: The following terms must NEVER appear: 'SOFG', 'Student Outcomes Focused "
        "Governance', 'Lone Star Governance', 'LSG'. These are owned by other organizations. "
    )

    prompt = (
        "You are a STRICT reviewer for ESB (Effective School Boards) portal content. "
        "Your job is to decide whether the content below is safe to use. Be skeptical but precise — "
        "only flag genuine problems, not stylistic preferences.\n\n"
        + client_facing_note
        + validation_note
        + ip_note
        + f"Content class: {content_class.value}\n"
        + (f"Context: {context_hint}\n" if context_hint else "")
        + f"\nContent to review:\n{content[:3000]}\n\n"
        "Block (set block=true) if ANY of these are true:\n"
        "1. Uses 'Coach' in client/practitioner-facing copy.\n"
        "2. Claims the instrument is validated, benchmarked, proven, or research-backed "
        "without a server-injected disclaimer.\n"
        "3. References SOFG, Student Outcomes Focused Governance, Lone Star Governance, or LSG.\n"
        "4. Makes a factual claim about a district, board, or person not grounded in the content.\n"
        "5. Contradicts the established maturity band labels or practice names.\n"
        "Also note (warn, do not block) if tone is corporate, bureaucratic, or AI-sounding.\n\n"
        'Respond ONLY as JSON: {"block": <bool>, "issues": ["short reason", ...]}. '
        "Empty issues means it is clean."
    )

    try:
        raw = (reviewer.complete(prompt, temperature=0, max_tokens=300) or "").strip()
        d = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except Exception:
        # Flaky judge never blocks — treat as unavailable
        return _handle_unavailable(content_class, ruleset_version)

    issues = [str(x) for x in (d.get("issues") or []) if str(x).strip()][:8]
    block = bool(d.get("block"))
    return Verdict(
        ok=not issues,
        block=block,
        issues=issues,
        ruleset_version=ruleset_version,
    )


def _handle_unavailable(content_class: ContentClass, ruleset_version: str) -> Verdict:
    """
    Degraded mode behavior when Stage 2 reviewer is unavailable.
    - FAIL_CLOSED_CLASSES: raise (caller must handle — content is held)
    - All others: return fail-open verdict with stage2_skipped=True
    """
    if content_class in FAIL_CLOSED_CLASSES:
        raise Stage2UnavailableError(
            f"Stage 2 reviewer unavailable for {content_class.value} content. "
            "This content class requires Stage 2. Content held."
        )
    return Verdict(
        ok=True,
        block=False,
        stage2_skipped=True,
        ruleset_version=ruleset_version,
    )


class Stage2UnavailableError(RuntimeError):
    """Raised when Stage 2 is unavailable for a fail-closed content class."""
