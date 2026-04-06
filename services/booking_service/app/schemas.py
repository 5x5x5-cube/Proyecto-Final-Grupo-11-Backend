import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateBookingRequest(BaseModel):
    room_id: uuid.UUID = Field(..., alias="roomId")
    hotel_id: uuid.UUID = Field(..., alias="hotelId")
    hold_id: uuid.UUID = Field(..., alias="holdId")
    check_in: date = Field(..., alias="checkIn")
    check_out: date = Field(..., alias="checkOut")
    guests: int = Field(..., ge=1, le=10)
    base_price: Decimal = Field(..., alias="basePrice")
    tax_amount: Decimal = Field(..., alias="taxAmount")
    service_fee: Decimal = Field(Decimal("0"), alias="serviceFee")
    total_price: Decimal = Field(..., alias="totalPrice")
    guest_name: str | None = Field(None, alias="guestName", max_length=200)
    guest_email: str | None = Field(None, alias="guestEmail", max_length=254)
    guest_phone: str | None = Field(None, alias="guestPhone", max_length=30)

    model_config = ConfigDict(populate_by_name=True)


class PriceBreakdown(BaseModel):
    price_per_night: float = Field(..., alias="pricePerNight")
    nights: int
    base_price: float = Field(..., alias="basePrice")
    vat: float
    service_fee: float = Field(..., alias="serviceFee")
    total_price: float = Field(..., alias="totalPrice")
    currency: str = "COP"

    model_config = ConfigDict(populate_by_name=True)


class BookingTimelineEvent(BaseModel):
    event: str
    timestamp: datetime
    description: str


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    code: str
    user_id: uuid.UUID = Field(..., alias="userId")
    hotel_id: uuid.UUID = Field(..., alias="hotelId")
    room_id: uuid.UUID = Field(..., alias="roomId")
    hold_id: uuid.UUID | None = Field(None, alias="holdId")
    check_in: date = Field(..., alias="checkIn")
    check_out: date = Field(..., alias="checkOut")
    guests: int
    status: str
    total_price: float = Field(..., alias="totalPrice")
    currency: str
    price_breakdown: PriceBreakdown | None = Field(None, alias="priceBreakdown")
    hold_expires_at: datetime | None = Field(None, alias="holdExpiresAt")
    created_at: datetime = Field(..., alias="createdAt")
    guest_name: str | None = Field(None, alias="guestName")
    guest_email: str | None = Field(None, alias="guestEmail")
    guest_phone: str | None = Field(None, alias="guestPhone")
    timeline: list[BookingTimelineEvent] = Field(default_factory=list)


class BookingListResponse(BaseModel):
    data: list[BookingResponse]
    total: int
    page: int
    limit: int


class HotelBookingSummary(BaseModel):
    total: int
    confirmed: int
    pending: int
    cancelled: int


class HotelBookingListResponse(BaseModel):
    data: list[BookingResponse]
    total: int
    page: int
    limit: int
    summary: HotelBookingSummary


class UpdateBookingStatusRequest(BaseModel):
    action: str = Field(..., pattern="^(confirm|reject)$")


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None
