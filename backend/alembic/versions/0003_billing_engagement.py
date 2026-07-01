"""Phase 1b: billing — membership, certification, engagement, referral, invoice

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("tier", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("stripe_subscription_id", sa.String(200), nullable=True),
        sa.Column("stripe_customer_id", sa.String(200), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tail_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_founding", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("irr_demo_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("founding_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount_cents", sa.Integer, nullable=False, server_default="250000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "certification",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("stripe_payment_intent_id", sa.String(200), nullable=True),
        sa.Column("dropbox_sign_envelope_id", sa.String(200), nullable=True),
        sa.Column("agreement_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text, nullable=True),
        sa.Column("amount_cents", sa.Integer, nullable=False, server_default="500000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "district_engagement",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("facilitator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_esb_referral", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("esb_pct", sa.Integer, nullable=False, server_default="15"),
        sa.Column("facilitator_pct", sa.Integer, nullable=False, server_default="85"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tail_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engagement_meta", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "district_referral",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("recommended_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("recommendation_rationale", sa.Text, nullable=True),
        sa.Column("assignment_note", sa.Text, nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "invoice",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("stripe_invoice_id", sa.String(200), nullable=True),
        sa.Column("stripe_payment_link", sa.String(500), nullable=True),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("line_items", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("esb_amount_cents", sa.Integer, nullable=True),
        sa.Column("facilitator_amount_cents", sa.Integer, nullable=True),
        sa.Column("facilitator_stripe_account", sa.String(200), nullable=True),
        sa.Column("disbursed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_membership_person", "membership", ["person_id"])
    op.create_index("ix_certification_person", "certification", ["person_id"])
    op.create_index("ix_engagement_facilitator", "district_engagement", ["facilitator_id"])
    op.create_index("ix_referral_recommended", "district_referral", ["recommended_to_id"])


def downgrade() -> None:
    op.drop_table("invoice")
    op.drop_table("district_referral")
    op.drop_table("district_engagement")
    op.drop_table("certification")
    op.drop_table("membership")
