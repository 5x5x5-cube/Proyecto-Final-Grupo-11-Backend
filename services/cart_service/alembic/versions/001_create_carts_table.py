"""Create carts table

Revision ID: 001
Revises:
Create Date: 2026-03-26

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
        "carts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("room_id", UUID(as_uuid=True), nullable=False),
        sa.Column("hotel_id", UUID(as_uuid=True), nullable=False),
        sa.Column("check_in", sa.Date, nullable=False),
        sa.Column("check_out", sa.Date, nullable=False),
        sa.Column("guests", sa.Integer, nullable=False),
        sa.Column("hold_id", UUID(as_uuid=True), nullable=False),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_per_night", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("tax_rate", sa.DECIMAL(5, 4), nullable=False),
        sa.Column("room_type", sa.String(50), nullable=False),
        sa.Column("hotel_name", sa.String(200), nullable=False),
        sa.Column("room_name", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("rating", sa.DECIMAL(3, 2)),
        sa.Column("review_count", sa.Integer),
        sa.Column("room_features", sa.String(500)),
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
    op.drop_table("carts")
