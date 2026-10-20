"""Report language (en | mr) for English / Marathi PDF downloads.

Revision ID: 0003_report_language
Revises: 0002_report_fields
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_report_language"
down_revision = "0002_report_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing reports were all English, so the server default backfills them correctly.
    with op.batch_alter_table("reports") as b:
        b.add_column(sa.Column("language", sa.String(5), nullable=True, server_default="en"))


def downgrade() -> None:
    with op.batch_alter_table("reports") as b:
        b.drop_column("language")
