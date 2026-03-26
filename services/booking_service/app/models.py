import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import DECIMAL, Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def generate_booking_code() -> str:
    """Generate a unique booking code like BK-A3F8B2C1."""
    return f"BK-{secrets.token_hex(4).upper()}"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, default=generate_booking_code
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hold_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    check_in: Mapped[datetime] = mapped_column(Date, nullable=False)
    check_out: Mapped[datetime] = mapped_column(Date, nullable=False)
    guests: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    base_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    service_fee: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)
    total_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
