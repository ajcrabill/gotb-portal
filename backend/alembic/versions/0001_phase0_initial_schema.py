"""Phase 0 initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-29

All tables required before any data can be written. Must ship before Phase 1.
Includes: people, role_memberships, consent_grants, otp_codes, user_sessions,
districts, district_matches, audit_log, scoring_configs, reference_data_versions.

PII governance columns (retention_until, deletion_requested) are on every table
that holds personal data — cannot be retrofitted after first data write.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── people ────────────────────────────────────────────────────────────────
    op.create_table(
        "people",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_requested", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_account_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_people_email", "people", ["email"], unique=True)

    # ── districts ─────────────────────────────────────────────────────────────
    op.create_table(
        "districts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("nces_lea_id", sa.String(20), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("is_cgcs_member", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_requested", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_districts_state", "districts", ["state"])
    op.create_index("ix_districts_nces_lea_id", "districts", ["nces_lea_id"], unique=True)

    # ── role_memberships ──────────────────────────────────────────────────────
    op.create_table(
        "role_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "superuser", "lead_senior_practitioner", "senior_facilitator",
                "coaching_manager", "business_manager", "certified_facilitator",
                "facilitator_in_training", "client", "investor", "public",
                name="roletype",
            ),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scoped_district_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("granted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["scoped_district_id"], ["districts.id"]),
        sa.ForeignKeyConstraint(["granted_by_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["revoked_by_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_role_memberships_person_id", "role_memberships", ["person_id"])

    # ── consent_grants ────────────────────────────────────────────────────────
    op.create_table(
        "consent_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("benchmarking_inclusion", "calibration_video_reuse", name="consentpurpose"),
            nullable=False,
        ),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_grants_person_id", "consent_grants", ["person_id"])

    # ── otp_codes ─────────────────────────────────────────────────────────────
    op.create_table(
        "otp_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_otp_codes_person_id", "otp_codes", ["person_id"])

    # ── user_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("role_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("is_step_up", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_role_check", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_person_id", "user_sessions", ["person_id"])
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)

    # ── scoring_configs ───────────────────────────────────────────────────────
    op.create_table(
        "scoring_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash_value", sa.String(64), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("renormalization_fn", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_configs_content_hash_value", "scoring_configs", ["content_hash_value"], unique=True)

    # ── reference_data_versions ───────────────────────────────────────────────
    op.create_table(
        "reference_data_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_type", sa.String(100), nullable=False),
        sa.Column("version_label", sa.String(100), nullable=False),
        sa.Column("content_hash_value", sa.String(64), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data_type", "content_hash_value", name="uq_ref_data_type_hash"),
    )

    # ── district_matches ──────────────────────────────────────────────────────
    op.create_table(
        "district_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_entity_type", sa.String(100), nullable=False),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_keys", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence_tier", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "unmatched", "pending_confirmation", "confirmed", "disputed",
                name="districtmatchstatus",
            ),
            nullable=False,
            server_default="unmatched",
        ),
        sa.Column("confirmed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["district_id"], ["districts.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_district_matches_source_entity_id", "district_matches", ["source_entity_id"])

    # ── audit_log (append-only, WORM) ─────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(100), nullable=True),
        sa.Column("actor_ip", sa.String(45), nullable=True),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("pipeline_verdict", sa.String(50), nullable=True),
        sa.Column("ruleset_version", sa.String(64), nullable=True),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # No UPDATE or DELETE on audit_log enforced by DB trigger below
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_immutable()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log rows are immutable';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable()")
    op.drop_table("audit_log")
    op.drop_table("district_matches")
    op.drop_table("reference_data_versions")
    op.drop_table("scoring_configs")
    op.drop_table("user_sessions")
    op.drop_table("otp_codes")
    op.drop_table("consent_grants")
    op.drop_table("role_memberships")
    op.drop_table("districts")
    op.drop_table("people")
    op.execute("DROP TYPE IF EXISTS districtmatchstatus")
    op.execute("DROP TYPE IF EXISTS consentpurpose")
    op.execute("DROP TYPE IF EXISTS roletype")
