"""Content pipeline service — orchestrates Stage 1 + Stage 2 for ESB portal content.

This is the single entry point for all content checking. Nothing ESB-generated
reaches a practitioner or client without passing through here.

Author-time vs render-time:
  - Author-time (templates, questions, disclaimers, guidance docs): both stages,
    verdict cached by content hash. Expensive Stage 2 runs once.
  - Render-time (dynamic slots interpolated into pre-cleared templates): Stage 1
    only on the dynamic portion. Pre-cleared template body is not re-checked.
  - Error/empty-state/button strings: author-time literals only. Never a
    synchronous LLM call on an error path.

Circuit breaker: after CIRCUIT_BREAKER_THRESHOLD consecutive Stage 2 failures,
Stage 2 is bypassed for fail-open classes until the circuit resets (5 min).
Fail-closed classes still block even with circuit open.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

import structlog

from esb.pipeline.antislop import clean
from esb.pipeline.quality import (
    ContentClass,
    Stage2UnavailableError,
    Verdict,
    review_content,
)

log = structlog.get_logger()

# Simple in-process verdict cache (content-addressed)
# In production: back with Redis for cross-process sharing
_verdict_cache: dict[str, Verdict] = {}
_circuit_failures: int = 0
_circuit_open_until: float = 0.0
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_RESET_SECONDS = 300


@dataclass
class PipelineResult:
    passed: bool
    stage1_score: int           # 0-100, 100=clean
    stage1_findings: dict = field(default_factory=dict)
    stage2_verdict: Verdict | None = None
    held: bool = False          # True = content held, goes to CM queue
    hold_reason: str = ""
    cache_hit: bool = False
    ruleset_version: str = "esb-v1"


def _cache_key(content: str, content_class: ContentClass, is_client_facing: bool) -> str:
    raw = f"{content_class.value}:{is_client_facing}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _circuit_is_open() -> bool:
    return time.monotonic() < _circuit_open_until


def _record_circuit_failure() -> None:
    global _circuit_failures, _circuit_open_until
    _circuit_failures += 1
    if _circuit_failures >= CIRCUIT_BREAKER_THRESHOLD:
        _circuit_open_until = time.monotonic() + CIRCUIT_RESET_SECONDS
        log.warning("pipeline.circuit_open", reset_in_seconds=CIRCUIT_RESET_SECONDS)


def _reset_circuit() -> None:
    global _circuit_failures, _circuit_open_until
    _circuit_failures = 0
    _circuit_open_until = 0.0


def check(
    content: str,
    *,
    content_class: ContentClass,
    llm_provider=None,
    is_client_facing: bool = True,
    context_hint: str = "",
    use_cache: bool = True,
    ruleset_version: str = "esb-v1",
) -> PipelineResult:
    """
    Run the full two-stage content pipeline.

    Stage 1 always runs (zero-token, deterministic).
    Stage 2 runs for author-time content; uses cache for repeated content.

    Returns PipelineResult. Caller is responsible for routing held content
    to the CM hold queue (the pipeline service doesn't know about the DB).
    """
    content = (content or "").strip()

    # Stage 1 — deterministic floor
    fixed, findings = clean(content, is_client_facing=is_client_facing)
    stage1_score = findings["score"]
    has_ip_violation = findings.get("has_ip_violation", False)

    # IP violations from Stage 1 are a hard block regardless of stage 2
    if has_ip_violation:
        log.error(
            "pipeline.ip_violation",
            violations=findings.get("ip_violations"),
            content_class=content_class.value,
        )
        return PipelineResult(
            passed=False,
            stage1_score=stage1_score,
            stage1_findings=findings,
            held=True,
            hold_reason="IP violation detected by Stage 1",
            ruleset_version=ruleset_version,
        )

    # Check cache before running Stage 2
    cache_key = _cache_key(content, content_class, is_client_facing)
    if use_cache and cache_key in _verdict_cache:
        cached = _verdict_cache[cache_key]
        log.debug("pipeline.cache_hit", cache_key=cache_key[:12])
        return PipelineResult(
            passed=not cached.block,
            stage1_score=stage1_score,
            stage1_findings=findings,
            stage2_verdict=cached,
            held=cached.block,
            hold_reason="; ".join(cached.issues) if cached.block else "",
            cache_hit=True,
            ruleset_version=ruleset_version,
        )

    # Stage 2 — independent-model reviewer
    if llm_provider is None or _circuit_is_open():
        # Circuit open or no provider: degraded mode
        try:
            from esb.pipeline.quality import _handle_unavailable
            verdict = _handle_unavailable(content_class, ruleset_version)
        except Stage2UnavailableError as e:
            return PipelineResult(
                passed=False,
                stage1_score=stage1_score,
                stage1_findings=findings,
                held=True,
                hold_reason=str(e),
                ruleset_version=ruleset_version,
            )
        log.info(
            "pipeline.stage2_skipped",
            content_class=content_class.value,
            reason="circuit_open" if _circuit_is_open() else "no_provider",
        )
        return PipelineResult(
            passed=True,
            stage1_score=stage1_score,
            stage1_findings=findings,
            stage2_verdict=verdict,
            ruleset_version=ruleset_version,
        )

    try:
        verdict = review_content(
            llm_provider,
            content=content,
            content_class=content_class,
            context_hint=context_hint,
            is_client_facing=is_client_facing,
            ruleset_version=ruleset_version,
        )
        _reset_circuit()
    except Stage2UnavailableError as e:
        _record_circuit_failure()
        return PipelineResult(
            passed=False,
            stage1_score=stage1_score,
            stage1_findings=findings,
            held=True,
            hold_reason=str(e),
            ruleset_version=ruleset_version,
        )
    except Exception as e:
        _record_circuit_failure()
        log.error("pipeline.stage2_error", error=str(e), content_class=content_class.value)
        try:
            from esb.pipeline.quality import _handle_unavailable
            verdict = _handle_unavailable(content_class, ruleset_version)
        except Stage2UnavailableError as e2:
            return PipelineResult(
                passed=False,
                stage1_score=stage1_score,
                stage1_findings=findings,
                held=True,
                hold_reason=str(e2),
                ruleset_version=ruleset_version,
            )

    # Cache the verdict (content-addressed; same text → same result)
    if use_cache and not verdict.stage2_skipped:
        _verdict_cache[cache_key] = verdict

    passed = not verdict.block
    return PipelineResult(
        passed=passed,
        stage1_score=stage1_score,
        stage1_findings=findings,
        stage2_verdict=verdict,
        held=not passed,
        hold_reason="; ".join(verdict.issues) if not passed else "",
        ruleset_version=ruleset_version,
    )
