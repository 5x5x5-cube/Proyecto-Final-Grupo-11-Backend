"""Add status column to carts table

Revision ID: 002
Revises: 001
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "carts", sa.Column("status", sa.String(20), server_default="active", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("carts", "status")
