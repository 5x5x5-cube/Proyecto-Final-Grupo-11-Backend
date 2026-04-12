import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .hotel import HotelBase, HotelCreate, HotelResponse  # noqa: F401

# --- Room schemas ---


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hotel_id: uuid.UUID
    room_type: str
    room_number: str | None = None
    capacity: int
    price_per_night: float
    tax_rate: float
    description: str | None = None
    amenities: dict | None = None
    total_quantity: int
    created_at: datetime


# --- Availability schemas ---


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    date: date
    total_quantity: int
    available_quantity: int


class AvailabilityRangeResponse(BaseModel):
    room_id: uuid.UUID
    check_in: date
    check_out: date
    is_available: bool
    dates: list[AvailabilityResponse]


# --- Hold schemas ---


class CreateHoldRequest(BaseModel):
    room_id: uuid.UUID = Field(..., alias="roomId")
    check_in: date = Field(..., alias="checkIn")
    check_out: date = Field(..., alias="checkOut")

    model_config = ConfigDict(populate_by_name=True)


class HoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    user_id: uuid.UUID
    check_in: date
    check_out: date
    status: str
    expires_at: datetime
    created_at: datetime
    price_per_night: float | None = None
    tax_rate: float | None = None
    room_type: str | None = None


class HoldCheckResponse(BaseModel):
    held: bool
    holder_id: uuid.UUID | None = None
    hold_id: uuid.UUID | None = None
    same_user: bool = False
    expires_at: datetime | None = None


# --- Error schemas ---


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


__all__ = [
    "HotelBase",
    "HotelCreate",
    "HotelResponse",
    "RoomResponse",
    "AvailabilityResponse",
    "AvailabilityRangeResponse",
    "CreateHoldRequest",
    "HoldResponse",
    "HoldCheckResponse",
    "ErrorResponse",
]
