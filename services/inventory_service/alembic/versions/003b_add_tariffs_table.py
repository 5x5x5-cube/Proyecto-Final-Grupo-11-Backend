"""add tariffs table

Revision ID: 003b
Revises: 003
Create Date: 2026-05-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "003b"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tariffs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "room_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rooms.id"),
            nullable=False,
        ),
        sa.Column("rate_type", sa.String(20), nullable=False),
        sa.Column("price_per_night", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tariffs_room_id", "tariffs", ["room_id"])


def downgrade() -> None:
    op.drop_index("ix_tariffs_room_id", table_name="tariffs")
    op.drop_table("tariffs")
