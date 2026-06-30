"""Scoring config service — seed, retrieve, and version active config."""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.models.base import content_hash
from esb.models.scoring import (
    BAND_LABELS,
    PRACTICE_BAND_SCORES,
    PRACTICE_CEILINGS,
    PRACTICE_KEYS,
    TOTAL_CEILING,
    ScoringConfig,
)

log = structlog.get_logger()


def _build_phase0_config() -> dict:
    """Construct the canonical Phase 0 scoring configuration."""
    return {
        "version": "phase0-v1",
        "total_ceiling": TOTAL_CEILING,
        "practices": {
            key: {
                "ceiling": PRACTICE_CEILINGS[key],
                "band_scores": PRACTICE_BAND_SCORES[key],
                "band_labels": BAND_LABELS[key],
            }
            for key in PRACTICE_KEYS
        },
        "clarify_conjunctive": True,
        "description": (
            "Phase 0 canonical scoring. Clarify Priorities (CP) uses a conjunctive "
            "rubric: both goals AND guardrails must be well-formed at the band level."
        ),
    }


async def get_active_config(db: AsyncSession) -> ScoringConfig | None:
    return await db.scalar(
        select(ScoringConfig).where(ScoringConfig.is_active)
    )


async def seed_initial_config(db: AsyncSession) -> ScoringConfig:
    """Idempotent: seed the Phase 0 config if no active config exists."""
    existing = await get_active_config(db)
    if existing:
        log.debug("scoring.config_already_seeded", config_id=str(existing.id))
        return existing

    config_data = _build_phase0_config()
    config_hash = content_hash(config_data)

    cfg = ScoringConfig(
        content_hash_value=config_hash,
        config=config_data,
        is_active=True,
        renormalization_fn=None,
    )
    db.add(cfg)
    await db.flush()

    log.info("scoring.config_seeded", config_id=str(cfg.id), hash=config_hash[:12])
    return cfg


async def get_config_by_id(db: AsyncSession, config_id: UUID) -> ScoringConfig | None:
    return await db.scalar(
        select(ScoringConfig).where(ScoringConfig.id == config_id)
    )
