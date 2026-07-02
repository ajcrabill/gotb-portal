"""Devon CRM domain models — districts, people, emails, dossiers, signals, outreach.

Ported natively from coach-devon into the portal. Access: lead_senior_practitioner
only (all CRM sub-modules), except the Strategic Plan Generator (all practitioners
+ paid clients — see esb/routers/plan.py).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from esb.core.database import Base
from esb.models.base import TimestampMixin, UUIDMixin


class CrmDistrict(TimestampMixin, UUIDMixin, Base):
    __tablename__ = "crm_districts"
    __table_args__ = (UniqueConstraint("state", "normalized_name", name="uq_crm_district_state_name"),)

    nces_lea_id: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(2), default="", index=True)
    zip: Mapped[str] = mapped_column(String(10), default="")
    street: Mapped[str] = mapped_column(String(300), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    county: Mapped[str] = mapped_column(String(150), default="")
    operational_schools: Mapped[int | None] = mapped_column(Integer)
    enrollment: Mapped[int | None] = mapped_column(Integer, index=True)
    enrollment_band: Mapped[str] = mapped_column(String(12), default="", index=True)
    locale: Mapped[str] = mapped_column(String(60), default="")
    district_type: Mapped[str] = mapped_column(String(60), default="")
    cgcs_member: Mapped[bool | None] = mapped_column(Boolean)
    board_url: Mapped[str] = mapped_column(String(500), default="")
    situation_score: Mapped[int] = mapped_column(Integer, default=0)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_crawl_note: Mapped[str] = mapped_column(String(200), default="")
    cms_platform: Mapped[str] = mapped_column(String(40), default="")
    last_news_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    pipeline_state: Mapped[str] = mapped_column(String(20), default="untouched", index=True)
    context: Mapped[str] = mapped_column(Text, default="")
    context_source: Mapped[str] = mapped_column(String(20), default="")
    context_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(40), default="")

    people: Mapped[list["CrmPerson"]] = relationship(back_populates="district", cascade="all, delete-orphan")


class CrmPerson(TimestampMixin, UUIDMixin, Base):
    __tablename__ = "crm_people"
    __table_args__ = (UniqueConstraint("district_id", "role", "normalized_name", name="uq_crm_person"),)

    district_id: Mapped[UUID] = mapped_column(ForeignKey("crm_districts.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), index=True)  # superintendent | board_member
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(150), default="")
    status: Mapped[str] = mapped_column(String(12), default="current", index=True)  # current | former
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dossiered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    district: Mapped["CrmDistrict"] = relationship(back_populates="people")
    emails: Mapped[list["CrmEmail"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class CrmEmail(UUIDMixin, Base):
    __tablename__ = "crm_emails"
    __table_args__ = (UniqueConstraint("person_id", "email", name="uq_crm_person_email"),)

    person_id: Mapped[UUID] = mapped_column(ForeignKey("crm_people.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), default="sheet_import")
    status: Mapped[str] = mapped_column(String(20), default="imported")
    confidence: Mapped[float | None] = mapped_column(Float)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(String(300), default="")

    person: Mapped["CrmPerson"] = relationship(back_populates="emails")


class CrmDossier(TimestampMixin, UUIDMixin, Base):
    __tablename__ = "crm_dossiers"

    person_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_people.id", ondelete="SET NULL"), index=True)
    district_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_districts.id", ondelete="SET NULL"), index=True)
    subject_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="gathering")  # gathering|needs_llm|complete|failed
    summary: Mapped[str] = mapped_column(String(4000), default="")
    voice_flags: Mapped[list] = mapped_column(JSON, default=list)
    markdown: Mapped[str] = mapped_column(Text, default="")

    claims: Mapped[list["CrmClaim"]] = relationship(back_populates="dossier", cascade="all, delete-orphan")
    searches: Mapped[list["CrmSearch"]] = relationship(back_populates="dossier", cascade="all, delete-orphan")


class CrmClaim(UUIDMixin, Base):
    __tablename__ = "crm_claims"

    dossier_id: Mapped[UUID] = mapped_column(ForeignKey("crm_dossiers.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(String(2000))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_url: Mapped[str] = mapped_column(String(800), nullable=False)
    source_tier: Mapped[str] = mapped_column(String(20), default="")
    verdict: Mapped[str] = mapped_column(String(20), default="")

    dossier: Mapped["CrmDossier"] = relationship(back_populates="claims")


class CrmSearch(UUIDMixin, Base):
    __tablename__ = "crm_searches"

    dossier_id: Mapped[UUID] = mapped_column(ForeignKey("crm_dossiers.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(60))
    query: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(800), default="")
    found: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(String(500), default="")

    dossier: Mapped["CrmDossier"] = relationship(back_populates="searches")


class CrmVerifyJob(UUIDMixin, TimestampMixin, Base):
    """Background job record for a district email-verification crawl.

    Crawling a district's website + verifying every discovered email is
    unbounded (observed 2+ minutes for a real district) — too long for a
    synchronous request/response, so it runs in the background and the
    frontend polls this row for status/result."""
    __tablename__ = "crm_verify_jobs"

    district_id: Mapped[UUID] = mapped_column(ForeignKey("crm_districts.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|complete|failed
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(500), default="")


class CrmSignal(UUIDMixin, Base):
    __tablename__ = "crm_signals"
    __table_args__ = (UniqueConstraint("district_id", "url", name="uq_crm_signal_url"),)

    district_id: Mapped[UUID] = mapped_column(ForeignKey("crm_districts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(10), default="low")  # high|medium|low
    headline: Mapped[str] = mapped_column(String(500))
    snippet: Mapped[str] = mapped_column(String(600), default="")
    url: Mapped[str] = mapped_column(String(800))
    matched_terms: Mapped[str] = mapped_column(String(300), default="")
    outreach_status: Mapped[str] = mapped_column(String(20), default="new")  # new|queued|sent|dismissed


class CrmCampaign(UUIDMixin, Base):
    __tablename__ = "crm_campaigns"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    segment: Mapped[dict] = mapped_column(JSON, default=dict)
    subject: Mapped[str] = mapped_column(String(300), default="")
    template: Mapped[str] = mapped_column(Text, default="")
    daily_cap: Mapped[int] = mapped_column(Integer, default=40)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|built|sending|paused|done

    messages: Mapped[list["CrmMessage"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class CrmSequence(UUIDMixin, Base):
    __tablename__ = "crm_sequences"

    person_id: Mapped[UUID] = mapped_column(ForeignKey("crm_people.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    status: Mapped[str] = mapped_column(String(20), default="not_contacted", index=True)
    current_touch: Mapped[int] = mapped_column(Integer, default=0)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    vars: Mapped[dict] = mapped_column(JSON, default=dict)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CrmMessage(UUIDMixin, Base):
    __tablename__ = "crm_messages"

    campaign_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_campaigns.id", ondelete="CASCADE"), index=True)
    sequence_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_sequences.id", ondelete="CASCADE"), index=True)
    touch_number: Mapped[int] = mapped_column(Integer, default=0)
    person_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_people.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    rationale: Mapped[str] = mapped_column(String(600), default="")
    decline_reason: Mapped[str] = mapped_column(Text, default="")
    decline_intent: Mapped[str] = mapped_column(String(16), default="")
    unsubscribe_token: Mapped[str] = mapped_column(String(255), default="", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voice_flags: Mapped[list] = mapped_column(JSON, default=list)

    campaign: Mapped["CrmCampaign"] = relationship(back_populates="messages")


class CrmVoiceSample(UUIDMixin, Base):
    __tablename__ = "crm_voice_samples"

    role: Mapped[str] = mapped_column(String(20), index=True)
    trigger: Mapped[str] = mapped_column(String(600), default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)


class CrmGlobalDirective(UUIDMixin, Base):
    __tablename__ = "crm_directives"

    text: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CrmSubscriber(UUIDMixin, Base):
    __tablename__ = "crm_subscribers"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    tier: Mapped[str] = mapped_column(String(20), default="free")
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CrmSuppression(UUIDMixin, Base):
    __tablename__ = "crm_suppression"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(40), default="unsubscribe")  # unsubscribe|bounce|manual
