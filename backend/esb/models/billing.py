"""Billing models — membership, certification, Stripe integration."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from esb.core.database import Base
from esb.models.base import UUIDMixin, TimestampMixin


class MembershipStatus(str, enum.Enum):
    active   = "active"
    lapsed   = "lapsed"
    canceled = "canceled"
    founding = "founding"   # grandfathered Founding Certified Facilitators


class MembershipTier(str, enum.Enum):
    annual          = "annual"        # $2,500/yr standard
    founding_free   = "founding_free" # Option A: $0 through July 2027
    founding_paid   = "founding_paid" # Option B: $500 through Dec 2027


class CertificationStatus(str, enum.Enum):
    active    = "active"
    expired   = "expired"
    revoked   = "revoked"
    pending   = "pending"


class InvoiceStatus(str, enum.Enum):
    draft     = "draft"
    sent      = "sent"
    paid      = "paid"
    void      = "void"
    refunded  = "refunded"


class ReferralStatus(str, enum.Enum):
    pending   = "pending"
    accepted  = "accepted"
    declined  = "declined"
    assigned  = "assigned"
    completed = "completed"
    rerouted  = "rerouted"   # facilitator lost cert; client moved elsewhere


class Membership(UUIDMixin, TimestampMixin, Base):
    """
    Practitioner membership — $2,500/yr or founding-rate variants.

    Lapse handling: if renewed_at is null and period_end < now(), status → lapsed.
    On lapse: 12-month tail active, non-compete in effect, client rerouted after tail.
    """
    __tablename__ = "membership"

    person_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    tier: Mapped[MembershipTier] = mapped_column(SAEnum(MembershipTier), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        SAEnum(MembershipStatus), nullable=False, default=MembershipStatus.active
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stripe_customer_id:     Mapped[str | None] = mapped_column(String(200), nullable=True)

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tail_until:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Founding grandfathering
    is_founding:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    irr_demo_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    founding_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=250000)  # $2,500.00


class Certification(UUIDMixin, TimestampMixin, Base):
    """
    Certified Great on Their Behalf Practitioner credential.
    $5,000 for 3-year term. Requires active membership + IRR demo.
    """
    __tablename__ = "certification"

    person_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[CertificationStatus] = mapped_column(
        SAEnum(CertificationStatus), nullable=False, default=CertificationStatus.pending
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dropbox_sign_envelope_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agreement_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    issued_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # +3 years
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=500000)  # $5,000.00


class DistrictEngagement(UUIDMixin, TimestampMixin, Base):
    """
    Tracks an ESB client engagement (referral or self-sourced).

    ESB referrals: ESB retains 15%, pays facilitator 85% via Stripe Connect.
    Self-sourced: facilitator keeps 100%; ESB not in financial relationship.
    """
    __tablename__ = "district_engagement"

    district_id:      Mapped[UUID] = mapped_column(ForeignKey("district.id"), nullable=False)
    facilitator_id:   Mapped[UUID] = mapped_column(nullable=False)
    is_esb_referral:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ESB split (only meaningful for is_esb_referral=True)
    esb_pct:          Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    facilitator_pct:  Mapped[int] = mapped_column(Integer, nullable=False, default=85)

    # Engagement term
    started_at:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tail_until:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    engagement_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class DistrictReferral(UUIDMixin, TimestampMixin, Base):
    """
    Inbound district referral routing.

    Coaching Manager reviews system recommendation and presses the final button.
    Once assigned, engagement record is created.
    """
    __tablename__ = "district_referral"

    district_id:         Mapped[UUID] = mapped_column(ForeignKey("district.id"), nullable=False)
    recommended_to_id:   Mapped[UUID | None] = mapped_column(nullable=True)
    assigned_to_id:      Mapped[UUID | None] = mapped_column(nullable=True)
    assigned_by_id:      Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(ReferralStatus), nullable=False, default=ReferralStatus.pending
    )
    recommendation_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignment_note:          Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_at:              Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Invoice(UUIDMixin, TimestampMixin, Base):
    """Financial record — membership, certification, and engagement invoices."""
    __tablename__ = "invoice"

    person_id:           Mapped[UUID] = mapped_column(nullable=False)
    district_id:         Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus), nullable=False, default=InvoiceStatus.draft
    )
    stripe_invoice_id:   Mapped[str | None] = mapped_column(String(200), nullable=True)
    stripe_payment_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    amount_cents:         Mapped[int]   = mapped_column(Integer, nullable=False)
    currency:             Mapped[str]   = mapped_column(String(3), nullable=False, default="usd")
    description:          Mapped[str]   = mapped_column(String(500), nullable=False)
    line_items:           Mapped[list]  = mapped_column(JSONB, nullable=False, default=list)

    due_at:               Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at:              Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Disbursement (for referral revenue splits)
    esb_amount_cents:            Mapped[int | None] = mapped_column(Integer, nullable=True)
    facilitator_amount_cents:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    facilitator_stripe_account:  Mapped[str | None] = mapped_column(String(200), nullable=True)
    disbursed_at:                Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
