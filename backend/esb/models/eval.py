"""Time Use Evaluation models — video submission → transcript → classification → report."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from esb.core.database import Base
from esb.models.base import UUIDMixin


class EvalJob(UUIDMixin, Base):
    __tablename__ = "eval_jobs"

    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(30), nullable=True)
    district_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meeting_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    meeting_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_span: Mapped[str] = mapped_column(String(20), nullable=False, default="1_meeting")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    meetings_analyzed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvalBrokenReport(UUIDMixin, Base):
    __tablename__ = "eval_broken_reports"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("eval_jobs.id", ondelete="CASCADE"), nullable=False)
    reporter_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_exists: Mapped[bool] = mapped_column(Boolean, nullable=False)
