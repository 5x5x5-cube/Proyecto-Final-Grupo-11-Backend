"""add discounts table

Revision ID: 004
Revises: 003
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tariff_id", UUID(as_uuid=True), sa.ForeignKey("tariffs.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("discount_type", sa.String(20), nullable=False),
        sa.Column("value", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_discounts_tariff_id", "discounts", ["tariff_id"])


def downgrade() -> None:
    op.drop_index("ix_discounts_tariff_id", table_name="discounts")
    op.drop_table("discounts")
