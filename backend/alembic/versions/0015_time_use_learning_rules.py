"""time_use_learning_rules — practitioner corrections to the Time Use
classification guide, filed from IRR Simulator results.

Revision ID: 0015
Revises: 0014
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "time_use_learning_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("irr_attempt.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activity_id", sa.String(60), nullable=False),
        sa.Column("context_snapshot", sa.String(2000), nullable=False, server_default=""),
        sa.Column("note", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_time_use_learning_rules_created_by_id", "time_use_learning_rules", ["created_by_id"])
    op.create_index("ix_time_use_learning_rules_attempt_id", "time_use_learning_rules", ["attempt_id"])
    op.create_index("ix_time_use_learning_rules_activity_id", "time_use_learning_rules", ["activity_id"])


def downgrade() -> None:
    op.drop_index("ix_time_use_learning_rules_activity_id", table_name="time_use_learning_rules")
    op.drop_index("ix_time_use_learning_rules_attempt_id", table_name="time_use_learning_rules")
    op.drop_index("ix_time_use_learning_rules_created_by_id", table_name="time_use_learning_rules")
    op.drop_table("time_use_learning_rules")
