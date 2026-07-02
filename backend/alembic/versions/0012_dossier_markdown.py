"""Add markdown column to crm_dossiers

Revision ID: 0012
Revises: 0011

The rendered markdown deliverable per the dossier redesign (templates +
research plan added 2026-07-01) — the sole practitioner-facing output.
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crm_dossiers", sa.Column("markdown", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("crm_dossiers", "markdown")
