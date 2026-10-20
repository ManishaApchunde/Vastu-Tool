"""Report options (personal action plan) and narrated video reports.

Revision ID: 0005_action_plan_and_video
Revises: 0004_customer_insights
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_action_plan_and_video"
down_revision = "0004_customer_insights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as b:
        b.add_column(sa.Column("options", sa.JSON(), nullable=True))
    op.create_table(
        "report_videos",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_id", sa.String(32), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("narration", sa.String(20), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("scenes", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("subtitles_key", sa.String(500), nullable=True),
        sa.Column("captions_key", sa.String(500), nullable=True),
        sa.Column("poster_key", sa.String(500), nullable=True),
        sa.Column("transcript", sa.JSON(), nullable=True),
        sa.Column("job_id", sa.String(32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_videos_project_id", "report_videos", ["project_id"])


def downgrade() -> None:
    op.drop_table("report_videos")
    with op.batch_alter_table("reports") as b:
        b.drop_column("options")
