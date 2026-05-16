import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    images: list | None = None
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


# --- Tariff schemas ---


class TariffCreate(BaseModel):
    room_id: uuid.UUID
    rate_type: str
    price_per_night: float
    start_date: date | None = None
    end_date: date | None = None


class TariffUpdate(BaseModel):
    rate_type: str | None = None
    price_per_night: float | None = None
    start_date: date | None = None
    end_date: date | None = None


class TariffResponse(BaseModel):
    id: uuid.UUID
    room_id: uuid.UUID
    room_name: str
    room_location: str
    room_image: str | None = None
    rate_type: str
    price_per_night: float
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime


# --- Discount schemas ---


class DiscountCreate(BaseModel):
    tariff_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=100)
    discount_type: str = Field(..., pattern="^(percentage|fixed)$")
    value: float = Field(..., gt=0)
    start_date: date
    end_date: date

    @field_validator("value")
    @classmethod
    def value_max_100_if_percentage(cls, v: float, info: Any) -> float:
        if info.data.get("discount_type") == "percentage" and v > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "DiscountCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class DiscountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    discount_type: str | None = Field(None, pattern="^(percentage|fixed)$")
    value: float | None = Field(None, gt=0)
    start_date: date | None = None
    end_date: date | None = None


class DiscountResponse(BaseModel):
    id: uuid.UUID
    tariff_id: uuid.UUID
    name: str
    discount_type: str
    value: float
    start_date: date
    end_date: date
    status: str
    created_at: datetime


# --- Admin room schemas ---


class AdminRoomResponse(BaseModel):
    id: uuid.UUID
    name: str
    location: str


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
    "TariffCreate",
    "TariffUpdate",
    "TariffResponse",
    "AdminRoomResponse",
    "DiscountCreate",
    "DiscountUpdate",
    "DiscountResponse",
]
