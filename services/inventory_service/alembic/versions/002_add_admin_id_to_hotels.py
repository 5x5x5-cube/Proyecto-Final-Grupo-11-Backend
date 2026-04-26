"""Add admin_id to hotels table

Revision ID: 002
Revises: 001
Create Date: 2026-04-26

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hotels", sa.Column("admin_id", UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("hotels", "admin_id")
