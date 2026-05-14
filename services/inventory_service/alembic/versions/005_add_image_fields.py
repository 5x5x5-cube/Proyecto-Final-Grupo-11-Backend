"""Add image fields to hotels and rooms

Revision ID: 005
Revises: 004
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hotels", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("hotels", sa.Column("images", JSONB, nullable=True))
    op.add_column("rooms", sa.Column("images", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("rooms", "images")
    op.drop_column("hotels", "images")
    op.drop_column("hotels", "image_url")
