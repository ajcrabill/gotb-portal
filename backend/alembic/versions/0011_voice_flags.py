"""Add voice_flags to crm_dossiers and crm_messages

Revision ID: 0011
Revises: 0010

ESB/AJ voice alignment checking (studio.voice_lint) previously only ran
on Governance Writer output and was never wired into Dossier summaries,
Lead Generator outreach copy, or (separately) Presentation Creator
outlines/decks. This adds storage for the first two; Presentation
Creator's check is stateless (computed fresh on generate/build) and
needs no column.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crm_dossiers", sa.Column("voice_flags", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("crm_messages", sa.Column("voice_flags", postgresql.JSONB(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("crm_messages", "voice_flags")
    op.drop_column("crm_dossiers", "voice_flags")
