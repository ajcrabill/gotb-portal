"""Practitioner terminology: rename facilitator/coaching_manager roles, add content_manager

Revision ID: 0004
Revises: 0003

"Practitioner" is the correct term throughout (Certified Great on Their
Behalf Practitioner). "Facilitator" was never correct; "Coach" is the
retired prior-generation ESB certification.
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ROLE_RENAMES = [
    ("senior_facilitator", "senior_practitioner"),
    ("coaching_manager", "facilitation_manager"),
    ("certified_facilitator", "certified_practitioner"),
    ("facilitator_in_training", "practitioner_in_training"),
]


def upgrade() -> None:
    for old, new in ROLE_RENAMES:
        op.execute(f"ALTER TYPE roletype RENAME VALUE '{old}' TO '{new}'")
    op.execute("ALTER TYPE roletype ADD VALUE 'content_manager'")

    op.alter_column("district_engagement", "facilitator_id", new_column_name="practitioner_id")
    op.alter_column("district_engagement", "facilitator_pct", new_column_name="practitioner_pct")
    op.alter_column("invoice", "facilitator_amount_cents", new_column_name="practitioner_amount_cents")
    op.alter_column("invoice", "facilitator_stripe_account", new_column_name="practitioner_stripe_account")
    op.execute("ALTER INDEX ix_engagement_facilitator RENAME TO ix_engagement_practitioner")


def downgrade() -> None:
    op.execute("ALTER INDEX ix_engagement_practitioner RENAME TO ix_engagement_facilitator")
    op.alter_column("invoice", "practitioner_stripe_account", new_column_name="facilitator_stripe_account")
    op.alter_column("invoice", "practitioner_amount_cents", new_column_name="facilitator_amount_cents")
    op.alter_column("district_engagement", "practitioner_pct", new_column_name="facilitator_pct")
    op.alter_column("district_engagement", "practitioner_id", new_column_name="facilitator_id")

    # Note: content_manager cannot be cleanly removed from a Postgres enum;
    # downgrade only reverses the renames, not the addition.
    for old, new in ROLE_RENAMES:
        op.execute(f"ALTER TYPE roletype RENAME VALUE '{new}' TO '{old}'")
