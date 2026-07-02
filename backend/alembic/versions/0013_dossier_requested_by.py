"""Add requested_by_id to crm_dossiers — tracks which practitioner kicked
off each build, for the "My Dossiers" / "All Dossiers" listing tabs.

Revision ID: 0013
Revises: 0012
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crm_dossiers", sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_crm_dossiers_requested_by_id", "crm_dossiers", ["requested_by_id"])


def downgrade() -> None:
    op.drop_index("ix_crm_dossiers_requested_by_id", table_name="crm_dossiers")
    op.drop_column("crm_dossiers", "requested_by_id")
