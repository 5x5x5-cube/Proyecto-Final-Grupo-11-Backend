import uuid
from datetime import datetime, timezone

from sqlalchemy import DECIMAL, Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    check_in: Mapped[datetime] = mapped_column(Date, nullable=False)
    check_out: Mapped[datetime] = mapped_column(Date, nullable=False)
    guests: Mapped[int] = mapped_column(Integer, nullable=False)
    hold_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hold_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_per_night: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    tax_rate: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)
    hotel_name: Mapped[str] = mapped_column(String(200), nullable=False)
    room_name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    rating: Mapped[float | None] = mapped_column(DECIMAL(3, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    room_features: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
