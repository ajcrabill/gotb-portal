"""crm_verify_jobs — background job tracking for Email Verifier crawls

Revision ID: 0010
Revises: 0009

process_district() measured 205s for a real district (website crawl +
per-email verification) — a synchronous request/response with no
streaming would drop the connection on Traefik's idle timeout with zero
response ever sent, surfacing to the browser as "Failed to fetch". Same
fix pattern as 0009's dossier-builder conversion: background job + poll.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_verify_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_districts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_verify_jobs_district_id", "crm_verify_jobs", ["district_id"])


def downgrade() -> None:
    op.drop_index("ix_crm_verify_jobs_district_id", table_name="crm_verify_jobs")
    op.drop_table("crm_verify_jobs")
