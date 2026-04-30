"""Create notification tables

Revision ID: 001
Revises:
Create Date: 2026-04-30

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
        "push_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("expo_push_token", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(255), unique=True, nullable=False),
        sa.Column("platform", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_push_tokens_user_id", "push_tokens", ["user_id"])
    op.create_index("idx_push_tokens_device_id", "push_tokens", ["device_id"])

    op.create_table(
        "notification_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("delivered", sa.Boolean, server_default="false"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("extra_data", JSONB, nullable=True),
    )
    op.create_index("idx_notification_history_user_id", "notification_history", ["user_id"])
    op.create_index("idx_notification_history_booking_id", "notification_history", ["booking_id"])


def downgrade() -> None:
    op.drop_table("notification_history")
    op.drop_table("push_tokens")
