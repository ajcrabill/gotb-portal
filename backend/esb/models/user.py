import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from esb.core.database import Base
from esb.models.base import TimestampMixin, UUIDMixin


class RoleType(str, enum.Enum):
    """
    "Practitioner" is the correct term throughout — a Certified Great on Their
    Behalf Practitioner. Never "facilitator" or "coach" ("coach" is the retired
    prior-generation ESB certification, not this one).
    """
    superuser = "superuser"
    lead_senior_practitioner = "lead_senior_practitioner"  # LSP (AJ)
    senior_practitioner = "senior_practitioner"
    practitioner_manager = "practitioner_manager"
    business_manager = "business_manager"
    content_manager = "content_manager"
    certified_practitioner = "certified_practitioner"
    practitioner_in_training = "practitioner_in_training"
    client = "client"
    investor = "investor"
    public = "public"


class ConsentPurpose(str, enum.Enum):
    benchmarking_inclusion = "benchmarking_inclusion"
    calibration_video_reuse = "calibration_video_reuse"


class Person(UUIDMixin, TimestampMixin, Base):
    """
    First-class keyed identity entity. One canonical identity across all districts.
    Cross-district dedup via email. PII columns required on every table per Sys-5.
    """
    __tablename__ = "people"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # PII governance (Sys-5 / Phase 0 requirement — cannot be retrofitted)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Stripe Connect (practitioners only; null for clients/public)
    stripe_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    role_memberships: Mapped[list["RoleMembership"]] = relationship(
        back_populates="person", cascade="all, delete-orphan",
        foreign_keys="RoleMembership.person_id",
    )
    consent_grants: Mapped[list["ConsentGrant"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    otp_codes: Mapped[list["OTPCode"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class RoleMembership(UUIDMixin, Base):
    """
    Effective-dated role assignment. Current membership = effective_until IS NULL.
    Former membership = effective_until IS NOT NULL.
    Re-check on every role-flag change invalidates stale session scope (Sys-13).
    """
    __tablename__ = "role_memberships"

    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    role: Mapped[RoleType] = mapped_column(Enum(RoleType), nullable=False)

    # Effective dates (not a boolean — supports history)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scoping (e.g., practitioner scoped to a district, client scoped to a district)
    scoped_district_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("districts.id"), nullable=True
    )

    granted_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    revoked_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    person: Mapped["Person"] = relationship(back_populates="role_memberships", foreign_keys=[person_id])


class ConsentGrant(UUIDMixin, Base):
    """
    Per-person per-purpose consent record. Each purpose is independently revocable.
    Two purposes cannot be modeled as a single scalar — hence this entity (Sys-5 / §5).
    """
    __tablename__ = "consent_grants"

    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    purpose: Mapped[ConsentPurpose] = mapped_column(Enum(ConsentPurpose), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by: Mapped[str] = mapped_column(String(255), nullable=False)  # "self" or person_id

    person: Mapped["Person"] = relationship(back_populates="consent_grants")


class OTPCode(UUIDMixin, Base):
    """
    Hardened OTP: hashed storage, single-use, TTL, attempt lockout, rate-limited (Sys-13).
    Purpose field distinguishes login, step-up, and share-link OTPs.
    """
    __tablename__ = "otp_codes"

    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)  # login | step_up | share_link
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    person: Mapped["Person"] = relationship(back_populates="otp_codes")


class UserSession(UUIDMixin, Base):
    """
    Session token (hashed). Role snapshot re-checked on every request; if
    role_memberships changed since last_role_check, session is invalidated (Sys-13).
    Step-up sessions have a shorter TTL and are separately tracked.
    """
    __tablename__ = "user_sessions"

    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Snapshot of roles at session creation — re-validated against current memberships
    role_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    is_step_up: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_role_check: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    person: Mapped["Person"] = relationship(back_populates="sessions")


# Import here to avoid circular refs — districts referenced in RoleMembership
from esb.models.district import District  # noqa: E402, F401
