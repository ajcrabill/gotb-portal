import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from esb.core.database import Base
from esb.models.base import TimestampMixin, UUIDMixin


class DistrictMatchStatus(str, enum.Enum):
    unmatched = "unmatched"
    pending_confirmation = "pending_confirmation"
    confirmed = "confirmed"
    disputed = "disputed"


class District(UUIDMixin, TimestampMixin, Base):
    """
    Canonical district entity. Migrated from Devon CRM.
    CGCS member districts are flagged and hard-blocked at intake (Sys-12, M1, M3, M10).
    """
    __tablename__ = "districts"

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    nces_lea_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # CGCS hard-block: if True, no engagement, no lead routing, no assessment creation.
    # Flag to LSP on any inbound. Checked at intake, pipeline advance, session creation.
    is_cgcs_member: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # PII governance
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DistrictMatch(UUIDMixin, TimestampMixin, Base):
    """
    Structured resolution object for linking inbound entities (leads, SA submissions)
    to canonical Districts. Client-visible use (baselines, funnel KPIs) requires
    a confirmed match. Re-match/un-match are first-class audited events (§5).
    """
    __tablename__ = "district_matches"

    source_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    district_id: Mapped[UUID | None] = mapped_column(ForeignKey("districts.id"), nullable=True)

    # Candidate keys considered during matching
    candidate_keys: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    # exact_nces | verified_email | fuzzy_name_state | no_candidate
    status: Mapped[DistrictMatchStatus] = mapped_column(
        Enum(DistrictMatchStatus), default=DistrictMatchStatus.unmatched, nullable=False
    )

    # Actor provenance: who confirmed/rejected the match
    confirmed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
