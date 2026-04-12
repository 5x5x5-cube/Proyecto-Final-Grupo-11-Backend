from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UpsertCartRequest(BaseModel):
    room_id: uuid.UUID = Field(..., alias="roomId")
    hotel_id: uuid.UUID = Field(..., alias="hotelId")
    check_in: date = Field(..., alias="checkIn")
    check_out: date = Field(..., alias="checkOut")
    guests: int

    model_config = ConfigDict(populate_by_name=True)


class PriceBreakdown(BaseModel):
    price_per_night: Decimal = Field(..., alias="pricePerNight")
    nights: int
    subtotal: Decimal
    vat: Decimal
    tourism_tax: Decimal = Field(default=Decimal("0"), alias="tourismTax")
    service_fee: Decimal = Field(default=Decimal("0"), alias="serviceFee")
    total: Decimal
    currency: str = "COP"

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CartResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID = Field(..., alias="userId")
    room_id: uuid.UUID = Field(..., alias="roomId")
    hotel_id: uuid.UUID = Field(..., alias="hotelId")
    check_in: date = Field(..., alias="checkIn")
    check_out: date = Field(..., alias="checkOut")
    guests: int
    hold_id: uuid.UUID = Field(..., alias="holdId")
    hold_expires_at: datetime = Field(..., alias="holdExpiresAt")
    room_type: str = Field(..., alias="roomType")
    hotel_name: str = Field(..., alias="hotelName")
    room_name: str = Field(..., alias="roomName")
    location: str
    rating: float | None = None
    review_count: int | None = Field(default=None, alias="reviewCount")
    room_features: str | None = Field(default=None, alias="roomFeatures")
    nights: int
    price_breakdown: PriceBreakdown = Field(..., alias="priceBreakdown")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True, from_attributes=True)
