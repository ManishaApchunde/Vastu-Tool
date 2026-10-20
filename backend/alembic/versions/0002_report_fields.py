"""Report redesign: remedy kind/phase/structural note, property client name.

Revision ID: 0002_report_fields
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_report_fields"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("remedies") as b:
        b.add_column(sa.Column("kind", sa.String(20), nullable=True, server_default="non_structural"))
        b.add_column(sa.Column("phase", sa.String(20), nullable=True))
        b.add_column(sa.Column("structural_note", sa.Text(), nullable=True))
    with op.batch_alter_table("properties") as b:
        b.add_column(sa.Column("client_name", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("properties") as b:
        b.drop_column("client_name")
    with op.batch_alter_table("remedies") as b:
        b.drop_column("structural_note")
        b.drop_column("phase")
        b.drop_column("kind")
