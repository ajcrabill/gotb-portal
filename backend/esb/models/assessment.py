"""Assessment models — self-assessment and certified assessment sessions."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from esb.core.database import Base
from esb.models.base import UUIDMixin, TimestampMixin
from esb.models.scoring import PRACTICE_KEYS


class AssessmentTier(str, enum.Enum):
    indicative = "indicative"    # self-scored, unvalidated
    certified  = "certified"     # practitioner-administered, validated


class AssessmentStatus(str, enum.Enum):
    draft      = "draft"
    submitted  = "submitted"
    scored     = "scored"
    archived   = "archived"


class AssessmentSession(UUIDMixin, TimestampMixin, Base):
    """
    One complete assessment of a district by a board (or practitioner).

    Tier determines validity claims:
      indicative — MAY NOT be represented as validated or benchmarked.
      certified  — MAY be represented as validated; administered by credentialed practitioner.

    scoring_config_id FK locks which scoring config version produced these scores.
    This means historic scores remain interpretable even after config changes.
    """
    __tablename__ = "assessment_session"

    district_id: Mapped[UUID] = mapped_column(ForeignKey("district.id"), nullable=False)
    scored_by_id: Mapped[UUID | None] = mapped_column(nullable=True)  # None = self-assessed
    tier: Mapped[AssessmentTier] = mapped_column(SAEnum(AssessmentTier), nullable=False)
    status: Mapped[AssessmentStatus] = mapped_column(
        SAEnum(AssessmentStatus), nullable=False, default=AssessmentStatus.draft
    )
    scoring_config_id: Mapped[UUID] = mapped_column(
        ForeignKey("scoring_config.id"), nullable=False
    )
    # Period the assessment covers (required for certified; optional for indicative)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Denormalized for fast rendering; canonical in practice_scores
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    composite_band: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1–4

    # Raw respondent answers (band choices) stored as JSONB
    # {"focus_mindset": 2, "clarify": 1, ...}
    raw_responses: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Computed score breakdown
    # [{"practice": "focus_mindset", "raw_band": 2, "score": 5, "band_label": "..."}]
    practice_scores: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Clarify Priorities conjunctive sub-scores
    # {"goals_band": 2, "guardrails_band": 1, "conjunctive_band": 1}
    clarify_detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Notes (practitioner-only for certified assessments)
    practitioner_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
