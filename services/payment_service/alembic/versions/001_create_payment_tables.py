"""Create payment tables

Revision ID: 001
Revises:
Create Date: 2026-04-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("card_last4", sa.String(4), nullable=False),
        sa.Column("card_brand", sa.String(20), nullable=False),
        sa.Column("card_holder", sa.String(200), nullable=False),
        sa.Column("card_number_hash", sa.String(64), nullable=False),
        sa.Column("expiry_month", sa.Integer, nullable=False),
        sa.Column("expiry_year", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("booking_id", UUID(as_uuid=True), nullable=True),
        sa.Column("booking_code", sa.String(20), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.DECIMAL(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="COP"),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="processing"),
        sa.Column(
            "token_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payment_tokens.id"),
            nullable=False,
        ),
        sa.Column("card_last4", sa.String(4)),
        sa.Column("card_brand", sa.String(20)),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("payment_tokens")
