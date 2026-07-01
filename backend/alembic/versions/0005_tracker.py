"""Coach Progress Tracker: tracker_coaches, tracker_competency_completions, tracker_competency_catalog

Revision ID: 0005
Revises: 0004

Ported natively into the portal from coach-devon's /tracker/* module.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

CATALOG_SEED = [
    ("GK1", "Governance Knowledge", "Distinguish between inputs, outputs, and outcomes", False, 0),
    ("GK2", "Governance Knowledge", "Distinguish between adult outcomes and student outcomes", False, 1),
    ("GK3", "Governance Knowledge", "Distinguish between customer service and owner service", False, 2),
    ("GK4", "Governance Knowledge", "Distinguish between low and high quality goals", False, 3),
    ("GK5", "Governance Knowledge", "Distinguish between board work and superintendent work", False, 4),
    ("GK6", "Governance Knowledge", "Distinguish between board responsibility and board accountability (added 1.1.25)", False, 5),
    ("GK7", "Governance Knowledge", "Distinguish between low and high quality monitoring reports", False, 6),
    ("GK8", "Governance Knowledge", "Summarize similarities and differences between the policy governance principles", False, 7),
    ("GK9", "Governance Knowledge", "Summarize observations of at least 20 school board meetings from at least 5 different school districts", False, 8),
    ("GK10", "Governance Knowledge", "Summarize observations of at least 2 ESB workshops that are led by at least 2 different ESB practitioners", False, 9),
    ("GK11", "Governance Knowledge", "Summarize the similarities and differences of the accountability systems for at least 3 different school districts", False, 10),
    ("GK12", "Governance Knowledge", "Summarize the similarities and differences of the statutory frameworks for at least 3 different states", False, 11),
    ("GK13", "Governance Knowledge", "Individually summarize learnings from each of the following five ESB recommended books", False, 12),
    ("GK13.a", "Governance Knowledge", "Great On Their Behalf: Chapters 1, 7, 8, 9 and 10", False, 13),
    ("GK13.d", "Governance Knowledge", "A Framework for School Governance", False, 14),
    ("GK13.b", "Governance Knowledge", "Four Disciplines of Execution", False, 15),
    ("GK13.c", "Governance Knowledge", "Boards That Make A Difference", False, 16),
    ("GK13.e", "Governance Knowledge", "School District Leadership That Works", False, 17),
    ("GS1", "Governance Skills", "Communicate the difference between inputs, outputs, outcomes, and why it matters", False, 18),
    ("GS2", "Governance Skills", "Communicate the difference between adult outcomes and student outcomes, and why it matters", False, 19),
    ("GS3", "Governance Skills", "Distinguish between effective goal monitoring and ineffective goal monitoring (added 1.1.25)", False, 20),
    ("GS4", "Governance Skills", "Conduct a time use evaluation for at least 3 school board meetings from at least 3 different school districts", False, 21),
    ("GS5", "Governance Skills", "Conduct an agenda evaluation for at least 3 school board meetings from at least 3 different school districts", False, 22),
    ("GS6", "Governance Skills", "Conduct a committee diet sample (at least 3 committees) for at least 3 different school districts", False, 23),
    ("GS7", "Governance Skills", "Create a draft implementation timeline", False, 24),
    ("GS8", "Governance Skills", "Create a draft set of goals, guardrails, interim goals, and interim guardrails", False, 25),
    ("GS9", "Governance Skills", "Conduct a policy diet sample (at least 10 policies) for at least 3 different school districts", False, 26),
    ("GS10", "Governance Skills", "Conduct a quarterly self evaluation sample (at least Clarify Priorities 1 and all of Working with the Superintendent) for at least 3 different school districts", False, 27),
    ("GS11", "Governance Skills", "Individually summarize learnings from each of the following four ESB recommended books", False, 28),
    ("GS11.a", "Governance Skills", "Great On Their Behalf: Chapters 2, 11, 12, 13, 14, 15, 16, 17", False, 29),
    ("GS11.b", "Governance Skills", "Policy Governance Consistency Framework", False, 30),
    ("GS11.c", "Governance Skills", "The Relationship Between School Board Governance Behaviors & Student Achievement", False, 31),
    ("GS11.d", "Governance Skills", "Eight Characteristics of Effective School Boards", False, 32),
    ("GM1", "Governance Mindset", "Communicate why school systems exist", False, 33),
    ("GM2", "Governance Mindset", "Communicate why school boards exist and why superintendents exist", False, 34),
    ("GM3", "Governance Mindset", "Communicate the intention behind, 'student outcomes don't change until adult behaviors change'", False, 35),
    ("GM4", "Governance Mindset", "Individually summarize learnings from each of the following five ESB recommended books", False, 36),
    ("GM4.a", "Governance Mindset", "Great On Their Behalf: Introduction and Chapters 3, 4, 5, 6", False, 37),
    ("GM4.b", "Governance Mindset", "Leadership & Self-Deception", False, 38),
    ("GM4.c", "Governance Mindset", "Immunity To Change", False, 39),
    ("GM4.d", "Governance Mindset", "School Governance Matters", False, 40),
    ("GM4.e", "Governance Mindset", "Is Discord Detrimental", False, 41),
    ("CK1", "Practitioner Knowledge", "Distinguish between feedback and criticism", False, 42),
    ("CK2", "Practitioner Knowledge", "Distinguish between project management and performance management", False, 43),
    ("CK3", "Practitioner Knowledge", "Distinguish between diagnostic, formative, interim, and summative assessment types", False, 44),
    ("CK4", "Practitioner Knowledge", "Distinguish between norm-referenced and criterion-referenced assessment scoring", False, 45),
    ("CK5", "Practitioner Knowledge", "Distinguish between proficiency, growth, and comparison goal types", False, 46),
    ("CK6", "Practitioner Knowledge", "Distinguish between static and cohort goal types", False, 47),
    ("CK7", "Practitioner Knowledge", "Distinguish between low and high quality interim goals/interim guardrails", False, 48),
    ("CS1", "Practitioner Skills", "Facilitate at least 2 conversations on Governance Knowledge 1-12 without a script", False, 49),
    ("CS2", "Practitioner Skills", "Facilitate at least 2 conversations on Governance Skills 1-9 without a script", False, 50),
    ("CS3", "Practitioner Skills", "Demonstrate the use of SCP & ICP", False, 51),
    ("CS4", "Practitioner Skills", "Demonstrate the use of Blooms & ICAP (removed 1.1.25)", True, 52),
    ("CS4_v2", "Practitioner Skills", "Complete a Knowledge & Skills workshop", False, 53),
    ("CS5", "Practitioner Skills", "Create a 1-3 page coaching recommendations memo for a board chair and superintendent", False, 54),
    ("CS6", "Practitioner Skills", "Participate, under the guidance of a certified ESB Practitioner, in the support of at least 1 school board", False, 55),
    ("CM1", "Practitioner Mindset", "Complete at least 5 ESB mindset practices within 14 days (merged 1.1.25)", True, 56),
    ("CM1_v2", "Practitioner Mindset", "Complete a Mindset workshop (Must complete at least 5 mindset practices within 14 days)", False, 57),
    ("CM2", "Practitioner Mindset", "Communicate the intention behind, 'I as Genesis'", False, 58),
    ("CM3", "Practitioner Mindset", "Communicate the intention behind, 'Integrity as Access'", False, 59),
    ("CM4", "Practitioner Mindset", "Facilitate at least 2 conversations on Governance Mindset 1-3 and Practitioner Mindset 2-3 without a script", False, 60),
    ("CM5", "Practitioner Mindset", "Facilitate at least 1 ESB 2-day workshop", False, 61),
    ("CM6.1", "Practitioner Mindset", "Integrity: Being your word (merged 1.1.25)", False, 62),
    ("CM6.2", "Practitioner Mindset", "Knowledge/Skill: Being accurate about the material (merged 1.1.25)", False, 63),
    ("CM6.3", "Practitioner Mindset", "Skill/Mindset: Being a safe and firm guide to support participant self-reflection (merged 1.1.25)", False, 64),
]

catalog_table = sa.table(
    "tracker_competency_catalog",
    sa.column("key", sa.String),
    sa.column("category", sa.String),
    sa.column("description", sa.Text),
    sa.column("is_legacy", sa.Boolean),
    sa.column("sort_order", sa.Integer),
)


def upgrade() -> None:
    op.create_table(
        "tracker_coaches",
        sa.Column("code", sa.VARCHAR(20), primary_key=True),
        sa.Column("name", sa.VARCHAR(200), nullable=False),
        sa.Column("email", sa.VARCHAR(320), nullable=True),
        sa.Column("phone", sa.VARCHAR(50), nullable=True),
        sa.Column("org", sa.VARCHAR(200), nullable=True),
        sa.Column("state", sa.VARCHAR(10), nullable=True),
        sa.Column("cert_status", sa.INTEGER(), nullable=False, server_default="0"),
        sa.Column("cert_date", sa.VARCHAR(20), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "tracker_competency_catalog",
        sa.Column("key", sa.VARCHAR(30), primary_key=True),
        sa.Column("category", sa.VARCHAR(100), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=False, server_default=""),
        sa.Column("is_legacy", sa.BOOLEAN(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.INTEGER(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "tracker_competency_completions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("coach_code", sa.VARCHAR(20), sa.ForeignKey("tracker_coaches.code", ondelete="CASCADE"), nullable=False),
        sa.Column("competency_key", sa.VARCHAR(30), sa.ForeignKey("tracker_competency_catalog.key", ondelete="CASCADE"), nullable=False),
        sa.Column("completed", sa.BOOLEAN(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("coach_code", "competency_key", name="uq_tracker_coach_competency"),
    )
    op.bulk_insert(catalog_table, [
        {"key": k, "category": c, "description": d, "is_legacy": legacy, "sort_order": s}
        for k, c, d, legacy, s in CATALOG_SEED
    ])


def downgrade() -> None:
    op.drop_table("tracker_competency_completions")
    op.drop_table("tracker_competency_catalog")
    op.drop_table("tracker_coaches")
