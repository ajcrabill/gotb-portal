"""IRR Simulator models — M20.

The IRR Simulator generates synthetic Time Use Evaluation scenarios, scores
them against the canonical rubric, then lets practitioners attempt to score
them. Inter-rater reliability (Cohen's kappa) is computed item by item.

Flow:
  1. System generates a scenario (IRRScenario) with synthetic agenda + minutes data
  2. System pre-scores it (system_scores JSONB)
  3. Practitioner scores it (IRRAttempt.practitioner_scores JSONB)
  4. Kappa is computed per item; feedback generated for each missed item
  5. Practitioner repeats until kappa >= 0.70 on all items across a rolling window

IRR simulator data is never mixed with certified assessment data.
"""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from esb.core.database import Base
from esb.models.base import TimestampMixin, UUIDMixin


class IRRScenarioType(str, enum.Enum):
    time_use_eval = "time_use_eval"
    gotb_index    = "gotb_index"     # Phase 2: full index IRR


class IRRAttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    submitted   = "submitted"
    scored      = "scored"


class IRRScenario(UUIDMixin, TimestampMixin, Base):
    """
    A synthetically generated scenario for IRR practice.

    Each scenario is generated fresh from a template + random seed, so
    practitioners always get new data. The system's own scores are stored
    here (ground truth for kappa computation).

    scenario_data: the synthetic document (agenda items, time allocations,
      participant roles, etc.) presented to the practitioner.
    system_scores: the canonical scoring of each rubric item by the system.
    generation_seed: ensures reproducibility for audit purposes.
    """
    __tablename__ = "irr_scenario"

    scenario_type: Mapped[IRRScenarioType] = mapped_column(
        SAEnum(IRRScenarioType), nullable=False, default=IRRScenarioType.time_use_eval
    )
    template_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    generation_seed:  Mapped[str] = mapped_column(String(100), nullable=False)

    # The synthetic document presented to the practitioner
    scenario_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Ground truth: system's own scores for each rubric item
    # {"item_id": {"score": 3, "rationale": "...", "criteria_met": [...]}}
    system_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Metadata about what the scenario tests
    focus_areas: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    difficulty:  Mapped[str]  = mapped_column(String(20), nullable=False, default="standard")
    is_active:   Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IRRAttempt(UUIDMixin, TimestampMixin, Base):
    """
    One practitioner attempt at scoring an IRR scenario.

    kappa: Cohen's kappa across all items in this attempt.
    item_kappas: per-item kappa values.
    item_feedback: for each item where practitioner differed from system,
      explains the correct reasoning.
    """
    __tablename__ = "irr_attempt"

    scenario_id:  Mapped[UUID] = mapped_column(ForeignKey("irr_scenario.id"), nullable=False)
    practitioner_id: Mapped[UUID] = mapped_column(nullable=False)

    status: Mapped[IRRAttemptStatus] = mapped_column(
        SAEnum(IRRAttemptStatus), nullable=False, default=IRRAttemptStatus.in_progress
    )

    # Practitioner's scores for each rubric item
    # {"item_id": {"score": 2, "notes": "..."}}
    practitioner_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Computed after submission
    kappa:        Mapped[float | None] = mapped_column(Float, nullable=True)
    passed:       Mapped[bool | None]  = mapped_column(Boolean, nullable=True)

    # Per-item kappas and feedback
    item_kappas:   Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    item_feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IRRProgress(UUIDMixin, TimestampMixin, Base):
    """
    Rolling reliability window for a practitioner.

    Tracks their kappa trend across the last N attempts (window_size=5 default)
    so we know when they've consistently hit >= 0.70 threshold.
    """
    __tablename__ = "irr_progress"
    __table_args__ = (
        {"comment": "Rolling IRR reliability window per practitioner"},
    )

    practitioner_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    scenario_type:   Mapped[IRRScenarioType] = mapped_column(SAEnum(IRRScenarioType), nullable=False)

    attempts_total:     Mapped[int]         = mapped_column(Integer, nullable=False, default=0)
    attempts_passed:    Mapped[int]         = mapped_column(Integer, nullable=False, default=0)
    rolling_kappa:      Mapped[float | None] = mapped_column(Float, nullable=True)
    window_size:        Mapped[int]         = mapped_column(Integer, nullable=False, default=5)
    certified_at:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TimeUseLearningRule(UUIDMixin, TimestampMixin, Base):
    """
    A practitioner-submitted correction to the Time Use classification
    guide (esb/eval/classification_guide.py), filed from an IRR Simulator
    result when the system's scoring was wrong. Compiled onto the base
    guide (see classification_guide.render_with_rules) and used both to
    show corrections in the simulator and to inform the real Time Use
    Evaluation tool's LLM classification prompt — the same feedback-loop
    pattern already used for the Plan Generator's corrections.

    Gated to superuser/lead_senior_practitioner — same authority that
    reviews and corrects any other AI-assisted output in the portal.
    """
    __tablename__ = "time_use_learning_rules"

    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    attempt_id:    Mapped[UUID | None] = mapped_column(ForeignKey("irr_attempt.id", ondelete="SET NULL"), nullable=True, index=True)

    activity_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # Auto-captured context (item title/description/system score) at the
    # moment the correction was filed — so the rule stays interpretable
    # even if the disputed scenario data changes later.
    context_snapshot: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(2000), nullable=False)
