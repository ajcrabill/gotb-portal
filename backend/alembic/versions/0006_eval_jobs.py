"""Time Use Evaluation: eval_jobs, eval_broken_reports

Revision ID: 0006
Revises: 0005

Ported natively into the portal from esby-portal's video-eval feature
(SQLite eval_jobs table -> Postgres, scoped to person_id instead of
esby-portal's separate user table).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(30), nullable=True),
        sa.Column("district_name", sa.String(255), nullable=True),
        sa.Column("meeting_date", sa.String(20), nullable=True),
        sa.Column("meeting_type", sa.String(100), nullable=True),
        sa.Column("review_span", sa.String(20), nullable=False, server_default="1_meeting"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_file", sa.Text(), nullable=True),
        sa.Column("result_url", sa.Text(), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("meetings_analyzed", sa.Integer(), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_eval_jobs_person_id", "eval_jobs", ["person_id"])

    op.create_table(
        "eval_broken_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eval_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("file_exists", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("eval_broken_reports")
    op.drop_table("eval_jobs")
