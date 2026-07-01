"""Phase 1: assessment_session, irr_scenario, irr_attempt, irr_progress

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("scored_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tier", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("scoring_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scoring_configs.id"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_score", sa.Integer, nullable=True),
        sa.Column("composite_band", sa.Integer, nullable=True),
        sa.Column("raw_responses", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("practice_scores", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("clarify_detail", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("practitioner_notes", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "irr_scenario",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scenario_type", sa.String(50), nullable=False, server_default="time_use_eval"),
        sa.Column("template_version", sa.String(50), nullable=False, server_default="v1"),
        sa.Column("generation_seed", sa.String(100), nullable=False),
        sa.Column("scenario_data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("system_scores", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("focus_areas", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("difficulty", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "irr_attempt",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("irr_scenario.id"), nullable=False),
        sa.Column("practitioner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="in_progress"),
        sa.Column("practitioner_scores", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("kappa", sa.Float, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
        sa.Column("item_kappas", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("item_feedback", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "irr_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("practitioner_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("scenario_type", sa.String(50), nullable=False, server_default="time_use_eval"),
        sa.Column("attempts_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("attempts_passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rolling_kappa", sa.Float, nullable=True),
        sa.Column("window_size", sa.Integer, nullable=False, server_default="5"),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_irr_attempt_practitioner", "irr_attempt", ["practitioner_id"])
    op.create_index("ix_assessment_district", "assessment_session", ["district_id"])


def downgrade() -> None:
    op.drop_table("irr_progress")
    op.drop_table("irr_attempt")
    op.drop_table("irr_scenario")
    op.drop_table("assessment_session")
