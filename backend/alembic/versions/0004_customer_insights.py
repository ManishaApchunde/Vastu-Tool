"""Customer insight tools: FitCheck constraints, family profile, construction stage,
site (post-move) verifications and expert review handoffs.

Revision ID: 0004_customer_insights
Revises: 0003_report_language
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_customer_insights"
down_revision = "0003_report_language"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("properties") as b:
        b.add_column(sa.Column("fit_constraints", sa.JSON(), nullable=True))
        b.add_column(sa.Column("family_profile", sa.JSON(), nullable=True))
        b.add_column(sa.Column("construction_stage", sa.String(30), nullable=True))

    op.create_table(
        "site_verifications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_id", sa.String(32), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("compass_north_angle", sa.Float(), nullable=True),
        sa.Column("entrance_confirmed", sa.Boolean(), nullable=True),
        sa.Column("items", sa.JSON(), nullable=True),
        sa.Column("remedy_progress", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_site_verifications_project_id", "site_verifications", ["project_id"])

    op.create_table(
        "expert_reviews",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_id", sa.String(32), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expert_name", sa.String(200), nullable=True),
        sa.Column("expert_role", sa.String(50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("include_contact", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feedback", sa.JSON(), nullable=True),
        sa.Column("reviewer_signature", sa.String(200), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_expert_reviews_project_id", "expert_reviews", ["project_id"])
    op.create_index("ix_expert_reviews_token_hash", "expert_reviews", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("expert_reviews")
    op.drop_table("site_verifications")
    with op.batch_alter_table("properties") as b:
        b.drop_column("construction_stage")
        b.drop_column("family_profile")
        b.drop_column("fit_constraints")
