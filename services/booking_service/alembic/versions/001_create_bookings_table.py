"""Create bookings table

Revision ID: 001
Revises:
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("hotel_id", UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", UUID(as_uuid=True), nullable=False),
        sa.Column("hold_id", UUID(as_uuid=True)),
        sa.Column("check_in", sa.Date, nullable=False),
        sa.Column("check_out", sa.Date, nullable=False),
        sa.Column("guests", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("base_price", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("tax_amount", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("service_fee", sa.DECIMAL(10, 2), server_default="0"),
        sa.Column("total_price", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="COP"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("bookings")
