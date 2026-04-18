"""Create payment tables

Revision ID: 001
Revises:
Create Date: 2026-04-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Gateway simulation table (would not exist with a real gateway)
    op.create_table(
        "payment_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("display_label", sa.String(200), nullable=False),
        sa.Column("method_data", JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Our domain: user's saved payment methods
    op.create_table(
        "user_payment_methods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("gateway_token", sa.String(64), nullable=False),
        sa.Column("method_type", sa.String(20), nullable=False),
        sa.Column("display_label", sa.String(200), nullable=False),
        sa.Column("card_last4", sa.String(4)),
        sa.Column("card_brand", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Our domain: payment records
    op.create_table(
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payment_method_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user_payment_methods.id"),
            nullable=False,
        ),
        sa.Column("cart_id", UUID(as_uuid=True), nullable=True),
        sa.Column("booking_snapshot", JSON, nullable=True),
        sa.Column("amount", sa.DECIMAL(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="COP"),
        sa.Column("status", sa.String(20), server_default="processing"),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("booking_id", UUID(as_uuid=True), nullable=True),
        sa.Column("booking_code", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("user_payment_methods")
    op.drop_table("payment_tokens")
