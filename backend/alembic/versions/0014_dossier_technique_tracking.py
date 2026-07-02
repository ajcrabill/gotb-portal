"""Add technique tracking to crm_searches and crm_claims — the learning-loop
dimension for measuring which search strategies (including each individual
matrix pivot) actually produce confirmed findings, so unproductive ones can
be phased out over time.

Revision ID: 0014
Revises: 0013
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crm_searches", sa.Column("technique", sa.String(60), nullable=False, server_default=""))
    op.add_column("crm_claims", sa.Column("technique", sa.String(60), nullable=False, server_default=""))
    op.create_index("ix_crm_searches_technique", "crm_searches", ["technique"])
    op.create_index("ix_crm_claims_technique", "crm_claims", ["technique"])


def downgrade() -> None:
    op.drop_index("ix_crm_claims_technique", table_name="crm_claims")
    op.drop_index("ix_crm_searches_technique", table_name="crm_searches")
    op.drop_column("crm_claims", "technique")
    op.drop_column("crm_searches", "technique")
