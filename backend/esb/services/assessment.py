"""Assessment scoring service.

Applies the canonical scoring model to a set of band choices, enforcing
the Clarify Priorities conjunctive rule.

Conjunctive rule (CP):
  Both goals AND guardrails must be well-formed at the assessed band level.
  The score assigned is the MINIMUM of the two sub-scores. If goals are at
  Band 3 but guardrails are at Band 1, the CP score is Band 1.

Band → score mapping is read from the active ScoringConfig, not hardcoded,
so future recalibrations apply to new sessions without changing this code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from esb.models.assessment import AssessmentSession, AssessmentStatus, AssessmentTier
from esb.models.scoring import (
    PRACTICE_CEILINGS,
    PRACTICE_KEYS,
    ScoringConfig,
)
from esb.services.scoring import get_active_config

log = structlog.get_logger()

KAPPA_PASS_THRESHOLD = 0.70


def _band_to_score(practice: str, band: int, config: ScoringConfig) -> int:
    """Convert a 0-indexed band (0-3) to its point value for a practice."""
    cfg = config.config
    practice_cfg = cfg["practices"][practice]
    return practice_cfg["band_scores"][band]


def _compute_clarify_score(
    goals_band: int,
    guardrails_band: int,
    config: ScoringConfig,
) -> tuple[int, int]:
    """
    Conjunctive CP rule: score = min(goals_band, guardrails_band).
    Returns (conjunctive_band, score).
    """
    conjunctive_band = min(goals_band, guardrails_band)
    score = _band_to_score("clarify", conjunctive_band, config)
    return conjunctive_band, score


def compute_total_band(total_score: int) -> int:
    """Derive the composite band from total score (1-indexed)."""
    if total_score < 25:
        return 1
    elif total_score < 60:
        return 2
    elif total_score < 85:
        return 3
    else:
        return 4


async def score_assessment(
    db: AsyncSession,
    session: AssessmentSession,
) -> AssessmentSession:
    """
    Score an assessment session in-place. Mutates session.practice_scores,
    session.total_score, session.composite_band. Does NOT commit.
    """
    config = await get_active_config(db)
    if not config:
        raise RuntimeError("No active scoring config found. Run seed_initial_config first.")

    raw = session.raw_responses  # {"focus_mindset": 2, "clarify_goals": 1, "clarify_guardrails": 2, ...}
    practice_scores = []
    total = 0

    for practice in PRACTICE_KEYS:
        if practice == "clarify":
            goals_band      = int(raw.get("clarify_goals", 0))
            guardrails_band = int(raw.get("clarify_guardrails", 0))
            band, score = _compute_clarify_score(goals_band, guardrails_band, config)
            session.clarify_detail = {
                "goals_band": goals_band,
                "guardrails_band": guardrails_band,
                "conjunctive_band": band,
            }
        else:
            band  = int(raw.get(practice, 0))
            score = _band_to_score(practice, band, config)

        band_labels = config.config["practices"][practice]["band_labels"]
        practice_scores.append({
            "practice": practice,
            "raw_band": band,
            "score": score,
            "ceiling": PRACTICE_CEILINGS[practice],
            "band_label": band_labels[band],
        })
        total += score

    session.practice_scores   = practice_scores
    session.total_score       = total
    session.composite_band    = compute_total_band(total)
    session.scoring_config_id = config.id
    session.status            = AssessmentStatus.scored
    session.scored_at         = datetime.now(timezone.utc)

    log.info(
        "assessment.scored",
        session_id=str(session.id),
        total=total,
        band=session.composite_band,
        tier=session.tier.value,
    )
    return session


async def create_indicative_session(
    db: AsyncSession,
    district_id: UUID,
    raw_responses: dict,
) -> AssessmentSession:
    """Create and immediately score an indicative (self-assessed) session."""
    from esb.services.scoring import get_active_config
    config = await get_active_config(db)
    if not config:
        raise RuntimeError("No active scoring config.")

    session = AssessmentSession(
        district_id=district_id,
        tier=AssessmentTier.indicative,
        status=AssessmentStatus.draft,
        scoring_config_id=config.id,
        raw_responses=raw_responses,
    )
    db.add(session)
    await db.flush()
    await score_assessment(db, session)
    session.status = AssessmentStatus.scored
    session.submitted_at = datetime.now(timezone.utc)
    await db.flush()
    return session
