"""Change admin_id from UUID to VARCHAR

Revision ID: 003
Revises: 002
Create Date: 2026-04-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("hotels", "admin_id", existing_type=UUID(as_uuid=True), type_=sa.String(255), nullable=True)


def downgrade() -> None:
    op.alter_column("hotels", "admin_id", existing_type=sa.String(255), type_=UUID(as_uuid=True), nullable=True)
