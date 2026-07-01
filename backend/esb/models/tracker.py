"""Coach Progress Tracker models — practitioner certification competency checklist."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from esb.core.database import Base
from esb.models.base import TimestampMixin, UUIDMixin


class TrackerCoach(TimestampMixin, Base):
    __tablename__ = "tracker_coaches"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    org: Mapped[str | None] = mapped_column(String(200), nullable=True)
    state: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cert_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cert_date: Mapped[str | None] = mapped_column(String(20), nullable=True)


class TrackerCompetencyCatalog(TimestampMixin, Base):
    __tablename__ = "tracker_competency_catalog"

    key: Mapped[str] = mapped_column(String(30), primary_key=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TrackerCompetencyCompletion(UUIDMixin, Base):
    __tablename__ = "tracker_competency_completions"

    coach_code: Mapped[str] = mapped_column(
        ForeignKey("tracker_coaches.code", ondelete="CASCADE"), nullable=False
    )
    competency_key: Mapped[str] = mapped_column(
        ForeignKey("tracker_competency_catalog.key", ondelete="CASCADE"), nullable=False
    )
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("coach_code", "competency_key", name="uq_tracker_coach_competency"),
    )
