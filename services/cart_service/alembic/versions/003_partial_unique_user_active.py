"""Replace user_id unique constraint with partial unique index on active carts

Revision ID: 003
Revises: 002
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("carts_user_id_key", "carts", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_carts_user_id_active " "ON carts (user_id) WHERE status = 'active'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_carts_user_id_active")
    op.create_unique_constraint("carts_user_id_key", "carts", ["user_id"])
