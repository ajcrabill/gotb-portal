import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from esb.core.database import Base
from esb.models.base import TimestampMixin, UUIDMixin, content_hash

# ── Canonical scoring model (§2a of architecture v3.2) ───────────────────────
#
# 5 practices = 5 buckets (1:1).
# Clarify Priorities uses a conjunctive rubric: both goals AND guardrails must be
# well-formed at the assessed band level for the practice to score at that level.
# The `clarify` bucket is a single score; the rubric enforces the conjunctive logic.
#
# Band scores (the only valid values per practice):
#   focus_mindset:  0, 1,  5, 10
#   clarify:        0, 5, 10, 20
#   monitor:        0, 10, 20, 40
#   align:          0, 5, 10, 20
#   communicate:    0, 1,  5, 10
#   total ceiling:  100

PRACTICE_KEYS = ["focus_mindset", "clarify", "monitor", "align", "communicate"]
PRACTICE_CEILINGS = {
    "focus_mindset": 10,
    "clarify": 20,
    "monitor": 40,
    "align": 20,
    "communicate": 10,
}
PRACTICE_BAND_SCORES = {
    "focus_mindset": [0, 1, 5, 10],
    "clarify": [0, 5, 10, 20],
    "monitor": [0, 10, 20, 40],
    "align": [0, 5, 10, 20],
    "communicate": [0, 1, 5, 10],
}
TOTAL_CEILING = 100

assert sum(PRACTICE_CEILINGS.values()) == TOTAL_CEILING, "bucket ceilings must sum to 100"
assert set(PRACTICE_KEYS) == set(PRACTICE_CEILINGS.keys()), "every practice needs a ceiling"

# Band labels (§2b): Band 1 is practice-specific; Bands 2-4 use universal "Focus" frame
BAND_LABELS = {
    "focus_mindset": ["Beginning Focus", "Emerging Focus", "Effective Focus", "Highly Effective Focus"],
    "clarify":       ["Beginning Clarity", "Emerging Focus", "Effective Focus", "Highly Effective Focus"],
    "monitor":       ["Beginning Monitoring", "Emerging Focus", "Effective Focus", "Highly Effective Focus"],
    "align":         ["Beginning Alignment", "Emerging Focus", "Effective Focus", "Highly Effective Focus"],
    "communicate":   ["Beginning Communication", "Emerging Focus", "Effective Focus", "Highly Effective Focus"],
}


class ScoringConfig(UUIDMixin, Base):
    """
    Append-only, content-hashed scoring configuration. Every assessment session
    carries a FK to the exact config that scored it. Edits mint a new version.
    Trend/benchmark surfaces must either refuse cross-version comparison or
    apply the documented re-normalization function registered here (§C-3).
    """
    __tablename__ = "scoring_configs"

    content_hash_value: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Re-normalization function (if any) for cross-version comparison. Null = refuse comparison.
    renormalization_fn: Mapped[str | None] = mapped_column(Text, nullable=True)

    @classmethod
    def make_hash(cls, config: dict) -> str:
        return content_hash(config)


class ReferenceDataVersion(UUIDMixin, Base):
    """
    Versioned reference data: cert rubrics, exemplars, competency framework,
    calibration anchors, label vocabulary. Pinned onto each submission/attempt.
    Items cannot be hard-deleted — only superseded by a new version (§5).
    """
    __tablename__ = "reference_data_versions"

    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. cert_rubric | competency_framework | calibration_anchors | label_vocabulary
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash_value: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("data_type", "content_hash_value", name="uq_ref_data_type_hash"),
    )
