"""Create exchange_rates table with seed data

Revision ID: 002
Revises: 001
Create Date: 2026-04-19

"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_RATES = [
    {"currency": "COP", "rate": 1.0, "symbol": "COP", "decimals": 0},
    {"currency": "USD", "rate": 0.00024, "symbol": "USD", "decimals": 2},
    {"currency": "MXN", "rate": 0.0041, "symbol": "MXN", "decimals": 0},
    {"currency": "ARS", "rate": 0.21, "symbol": "ARS", "decimals": 0},
    {"currency": "CLP", "rate": 0.22, "symbol": "CLP", "decimals": 0},
    {"currency": "PEN", "rate": 0.00089, "symbol": "PEN", "decimals": 2},
]


def upgrade() -> None:
    table = op.create_table(
        "exchange_rates",
        sa.Column("currency", sa.String(3), primary_key=True),
        sa.Column("rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("symbol", sa.String(5), nullable=False),
        sa.Column("decimals", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        table,
        [{**r, "updated_at": now} for r in SEED_RATES],
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
