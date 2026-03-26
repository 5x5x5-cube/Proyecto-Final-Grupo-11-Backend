"""Create inventory tables: hotels, rooms, availability, holds

Revision ID: 001
Revises:
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hotels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("city", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("rating", sa.DECIMAL(2, 1)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "rooms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("hotel_id", UUID(as_uuid=True), sa.ForeignKey("hotels.id"), nullable=False),
        sa.Column("room_type", sa.String(50), nullable=False),
        sa.Column("room_number", sa.String(20)),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("price_per_night", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("tax_rate", sa.DECIMAL(5, 4), server_default="0.1900"),
        sa.Column("description", sa.Text),
        sa.Column("amenities", JSONB),
        sa.Column("total_quantity", sa.Integer, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "availability",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("total_quantity", sa.Integer, nullable=False),
        sa.Column("available_quantity", sa.Integer, nullable=False),
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
        sa.UniqueConstraint("room_id", "date", name="uix_room_date"),
    )

    op.create_table(
        "holds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("check_in", sa.Date, nullable=False),
        sa.Column("check_out", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("holds")
    op.drop_table("availability")
    op.drop_table("rooms")
    op.drop_table("hotels")
