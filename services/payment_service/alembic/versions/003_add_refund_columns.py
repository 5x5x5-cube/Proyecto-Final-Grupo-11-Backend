"""Add refund columns to payments

Revision ID: 003
Revises: 002
Create Date: 2026-05-14

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("refund_amount", sa.DECIMAL(12, 2), nullable=True))
    op.add_column("payments", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "refunded_at")
    op.drop_column("payments", "refund_amount")
