"""Devon CRM domain: districts, people, emails, dossiers, signals, outreach

Revision ID: 0008
Revises: 0007

Ported natively from coach-devon. Tables are prefixed crm_ to avoid any
collision with the portal's own `people`/`districts` concepts, which are
distinct entities (portal practitioners/clients vs. CRM superintendents/
board members; portal engagement districts vs. the national CRM district
universe).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_districts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nces_lea_id", sa.String(20), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("normalized_name", sa.String(300), nullable=False),
        sa.Column("city", sa.String(120), nullable=False, server_default=""),
        sa.Column("state", sa.String(2), nullable=False, server_default=""),
        sa.Column("zip", sa.String(10), nullable=False, server_default=""),
        sa.Column("street", sa.String(300), nullable=False, server_default=""),
        sa.Column("phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("website", sa.String(500), nullable=False, server_default=""),
        sa.Column("county", sa.String(150), nullable=False, server_default=""),
        sa.Column("operational_schools", sa.Integer(), nullable=True),
        sa.Column("enrollment", sa.Integer(), nullable=True),
        sa.Column("enrollment_band", sa.String(12), nullable=False, server_default=""),
        sa.Column("locale", sa.String(60), nullable=False, server_default=""),
        sa.Column("district_type", sa.String(60), nullable=False, server_default=""),
        sa.Column("cgcs_member", sa.Boolean(), nullable=True),
        sa.Column("board_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("situation_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_crawl_note", sa.String(200), nullable=False, server_default=""),
        sa.Column("cms_platform", sa.String(40), nullable=False, server_default=""),
        sa.Column("last_news_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pipeline_state", sa.String(20), nullable=False, server_default="untouched"),
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
        sa.Column("context_source", sa.String(20), nullable=False, server_default=""),
        sa.Column("context_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("state", "normalized_name", name="uq_crm_district_state_name"),
    )
    op.create_index("ix_crm_districts_nces_lea_id", "crm_districts", ["nces_lea_id"])
    op.create_index("ix_crm_districts_normalized_name", "crm_districts", ["normalized_name"])
    op.create_index("ix_crm_districts_state", "crm_districts", ["state"])
    op.create_index("ix_crm_districts_enrollment", "crm_districts", ["enrollment"])
    op.create_index("ix_crm_districts_enrollment_band", "crm_districts", ["enrollment_band"])
    op.create_index("ix_crm_districts_last_crawled_at", "crm_districts", ["last_crawled_at"])
    op.create_index("ix_crm_districts_last_news_scan_at", "crm_districts", ["last_news_scan_at"])
    op.create_index("ix_crm_districts_pipeline_state", "crm_districts", ["pipeline_state"])

    op.create_table(
        "crm_people",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_districts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(150), nullable=False, server_default=""),
        sa.Column("status", sa.String(12), nullable=False, server_default="current"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_dossiered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("district_id", "role", "normalized_name", name="uq_crm_person"),
    )
    op.create_index("ix_crm_people_district_id", "crm_people", ["district_id"])
    op.create_index("ix_crm_people_role", "crm_people", ["role"])
    op.create_index("ix_crm_people_status", "crm_people", ["status"])
    op.create_index("ix_crm_people_last_dossiered_at", "crm_people", ["last_dossiered_at"])

    op.create_table(
        "crm_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("source", sa.String(40), nullable=False, server_default="sheet_import"),
        sa.Column("status", sa.String(20), nullable=False, server_default="imported"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(300), nullable=False, server_default=""),
        sa.UniqueConstraint("person_id", "email", name="uq_crm_person_email"),
    )
    op.create_index("ix_crm_emails_person_id", "crm_emails", ["person_id"])
    op.create_index("ix_crm_emails_email", "crm_emails", ["email"])

    op.create_table(
        "crm_dossiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_districts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="gathering"),
        sa.Column("summary", sa.String(4000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_dossiers_person_id", "crm_dossiers", ["person_id"])
    op.create_index("ix_crm_dossiers_district_id", "crm_dossiers", ["district_id"])

    op.create_table(
        "crm_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_dossiers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.String(120), nullable=True),
        sa.Column("value", sa.String(2000), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_url", sa.String(800), nullable=False),
        sa.Column("source_tier", sa.String(20), nullable=False, server_default=""),
        sa.Column("verdict", sa.String(20), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_claims_dossier_id", "crm_claims", ["dossier_id"])

    op.create_table(
        "crm_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_dossiers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(40), nullable=True),
        sa.Column("source", sa.String(60), nullable=True),
        sa.Column("query", sa.String(500), nullable=False, server_default=""),
        sa.Column("url", sa.String(800), nullable=False, server_default=""),
        sa.Column("found", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_searches_dossier_id", "crm_searches", ["dossier_id"])

    op.create_table(
        "crm_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_districts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=True),
        sa.Column("severity", sa.String(10), nullable=False, server_default="low"),
        sa.Column("headline", sa.String(500), nullable=True),
        sa.Column("snippet", sa.String(600), nullable=False, server_default=""),
        sa.Column("url", sa.String(800), nullable=True),
        sa.Column("matched_terms", sa.String(300), nullable=False, server_default=""),
        sa.Column("outreach_status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("district_id", "url", name="uq_crm_signal_url"),
    )
    op.create_index("ix_crm_signals_district_id", "crm_signals", ["district_id"])
    op.create_index("ix_crm_signals_kind", "crm_signals", ["kind"])

    op.create_table(
        "crm_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("segment", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("subject", sa.String(300), nullable=False, server_default=""),
        sa.Column("template", sa.Text(), nullable=False, server_default=""),
        sa.Column("daily_cap", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "crm_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_contacted"),
        sa.Column("current_touch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vars", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_crm_sequences_person_id", "crm_sequences", ["person_id"])
    op.create_index("ix_crm_sequences_email", "crm_sequences", ["email"])
    op.create_index("ix_crm_sequences_status", "crm_sequences", ["status"])
    op.create_index("ix_crm_sequences_next_due_at", "crm_sequences", ["next_due_at"])

    op.create_table(
        "crm_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_campaigns.id", ondelete="CASCADE"), nullable=True),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_sequences.id", ondelete="CASCADE"), nullable=True),
        sa.Column("touch_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("subject", sa.String(300), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("rationale", sa.String(600), nullable=False, server_default=""),
        sa.Column("decline_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("decline_intent", sa.String(16), nullable=False, server_default=""),
        sa.Column("unsubscribe_token", sa.String(255), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_messages_campaign_id", "crm_messages", ["campaign_id"])
    op.create_index("ix_crm_messages_sequence_id", "crm_messages", ["sequence_id"])
    op.create_index("ix_crm_messages_status", "crm_messages", ["status"])
    op.create_index("ix_crm_messages_email", "crm_messages", ["email"])
    op.create_index("ix_crm_messages_unsubscribe_token", "crm_messages", ["unsubscribe_token"])

    op.create_table(
        "crm_voice_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("trigger", sa.String(600), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
    )
    op.create_index("ix_crm_voice_samples_role", "crm_voice_samples", ["role"])

    op.create_table(
        "crm_directives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "crm_subscribers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_crm_subscribers_email", "crm_subscribers", ["email"], unique=True)

    op.create_table(
        "crm_suppression",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("reason", sa.String(40), nullable=False, server_default="unsubscribe"),
    )
    op.create_index("ix_crm_suppression_email", "crm_suppression", ["email"], unique=True)


def downgrade() -> None:
    op.drop_table("crm_suppression")
    op.drop_table("crm_subscribers")
    op.drop_table("crm_directives")
    op.drop_table("crm_voice_samples")
    op.drop_table("crm_messages")
    op.drop_table("crm_sequences")
    op.drop_table("crm_campaigns")
    op.drop_table("crm_signals")
    op.drop_table("crm_searches")
    op.drop_table("crm_claims")
    op.drop_table("crm_dossiers")
    op.drop_table("crm_emails")
    op.drop_table("crm_people")
    op.drop_table("crm_districts")
