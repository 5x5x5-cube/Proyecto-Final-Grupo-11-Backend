"""Add payment_id column to bookings table

Revision ID: 002
Revises: 001
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("payment_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "payment_id")
