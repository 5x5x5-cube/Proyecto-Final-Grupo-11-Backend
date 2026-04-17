import enum
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DECIMAL, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .schemas import MethodData


class Base(DeclarativeBase):
    pass


class PaymentMethod(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    DIGITAL_WALLET = "digital_wallet"
    TRANSFER = "transfer"


def generate_token() -> str:
    return f"tok_{secrets.token_hex(16)}"


class PaymentToken(Base):
    __tablename__ = "payment_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_token
    )
    method: Mapped[str] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum", create_constraint=False),
        nullable=False,
    )
    display_label: Mapped[str] = mapped_column(String(200), nullable=False)
    method_data: Mapped[MethodData] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(minutes=15),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    booking_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    method: Mapped[str] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum", create_constraint=False),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="processing")
    token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_tokens.id"), nullable=False
    )
    display_label: Mapped[str | None] = mapped_column(String(200))
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
