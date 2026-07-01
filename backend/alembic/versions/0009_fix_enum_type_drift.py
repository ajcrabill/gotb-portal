"""Fix enum type drift — several columns were created as plain VARCHAR in
earlier migrations (0002, 0003) while their ORM models declare native
Postgres ENUM types (sa.Enum / SAEnum). Every INSERT/UPDATE through the
ORM on these columns fails with asyncpg.exceptions.UndefinedObjectError:
type "..." does not exist, since the enum type was never created in the
database. This predates any work done this session — assessment
submission and the IRR simulator have never worked in production.

Revision ID: 0009
Revises: 0008
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# (enum type name, values, table, column)
_ENUMS = [
    ("assessmenttier",       ["indicative", "certified"],
     "assessment_session", "tier"),
    ("assessmentstatus",     ["draft", "submitted", "scored", "archived"],
     "assessment_session", "status"),
    ("irrscenariotype",      ["time_use_eval", "gotb_index"],
     "irr_scenario", "scenario_type"),
    ("irrscenariotype",      ["time_use_eval", "gotb_index"],
     "irr_progress", "scenario_type"),
    ("irrattemptstatus",     ["in_progress", "submitted", "scored"],
     "irr_attempt", "status"),
    ("membershiptier",       ["annual", "founding_free", "founding_paid"],
     "membership", "tier"),
    ("membershipstatus",     ["active", "lapsed", "canceled", "founding"],
     "membership", "status"),
    ("certificationstatus",  ["active", "expired", "revoked", "pending"],
     "certification", "status"),
    ("referralstatus",       ["pending", "accepted", "declined", "assigned", "completed", "rerouted"],
     "district_referral", "status"),
    ("invoicestatus",        ["draft", "sent", "paid", "void", "refunded"],
     "invoice", "status"),
]

def upgrade() -> None:
    created_types: set[str] = set()
    for type_name, values, table, column in _ENUMS:
        if type_name not in created_types:
            values_sql = ", ".join(f"'{v}'" for v in values)
            op.execute(f"CREATE TYPE {type_name} AS ENUM ({values_sql})")
            created_types.add(type_name)
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {type_name} "
            f"USING {column}::text::{type_name}"
        )


def downgrade() -> None:
    for type_name, _values, table, column in _ENUMS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(50) USING {column}::text")
    for type_name in {t for t, *_ in _ENUMS}:
        op.execute(f"DROP TYPE IF EXISTS {type_name}")
