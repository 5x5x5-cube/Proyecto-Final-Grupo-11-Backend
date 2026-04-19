import uuid
from datetime import date, datetime, timezone

from sqlalchemy import DECIMAL, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[float | None] = mapped_column(DECIMAL(2, 1))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    rooms: Mapped[list["Room"]] = relationship(back_populates="hotel", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False
    )
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)
    room_number: Mapped[str | None] = mapped_column(String(20))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_night: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    tax_rate: Mapped[float] = mapped_column(DECIMAL(5, 4), default=0.19)
    description: Mapped[str | None] = mapped_column(Text)
    amenities: Mapped[dict | None] = mapped_column(JSONB)
    total_quantity: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    hotel: Mapped["Hotel"] = relationship(back_populates="rooms")
    availabilities: Mapped[list["Availability"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )
    holds: Mapped[list["Hold"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    tariffs: Mapped[list["Tariff"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (UniqueConstraint("room_id", "date", name="uix_room_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    room: Mapped["Room"] = relationship(back_populates="availabilities")


class Hold(Base):
    __tablename__ = "holds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    room: Mapped["Room"] = relationship(back_populates="holds")


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False
    )
    rate_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price_per_night: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    room: Mapped["Room"] = relationship(back_populates="tariffs")


__all__ = ["Hotel", "Room", "Availability", "Hold", "Tariff", "Base"]
