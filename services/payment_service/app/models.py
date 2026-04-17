import enum
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DECIMAL, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .schemas import MethodData


class Base(DeclarativeBase):
    pass


class PaymentMethodType(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    DIGITAL_WALLET = "digital_wallet"
    TRANSFER = "transfer"


def generate_token() -> str:
    return f"tok_{secrets.token_hex(16)}"


# ── Gateway domain (simulated — would not exist in our DB with a real gateway) ──


class PaymentToken(Base):
    """Simulates the gateway's internal token store. In production, this lives
    on the gateway side and we'd never have direct access to it."""

    __tablename__ = "payment_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=generate_token
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    display_label: Mapped[str] = mapped_column(String(200), nullable=False)
    method_data: Mapped[MethodData] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(minutes=15),
    )


# ── Our domain (payment service's own tables) ──


class UserPaymentMethod(Base):
    """A user's saved payment method, created from data the gateway returns
    at tokenization time. Contains only display-safe information."""

    __tablename__ = "user_payment_methods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    gateway_token: Mapped[str] = mapped_column(String(64), nullable=False)
    method_type: Mapped[str] = mapped_column(String(20), nullable=False)
    display_label: Mapped[str] = mapped_column(String(200), nullable=False)
    card_last4: Mapped[str | None] = mapped_column(String(4))
    card_brand: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payment_method_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_payment_methods.id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    status: Mapped[str] = mapped_column(String(20), default="processing")
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    booking_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
