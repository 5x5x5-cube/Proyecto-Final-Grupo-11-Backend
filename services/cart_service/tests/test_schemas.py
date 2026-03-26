from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from app.schemas import CartResponse, PriceBreakdown, UpsertCartRequest


class TestUpsertCartRequest:
    def test_from_camel_case(self):
        data = {
            "roomId": "b1000000-0000-0000-0000-000000000001",
            "hotelId": "a1000000-0000-0000-0000-000000000001",
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
            "guests": 2,
        }
        req = UpsertCartRequest(**data)
        assert req.room_id == uuid.UUID("b1000000-0000-0000-0000-000000000001")
        assert req.check_in == date(2026, 4, 1)
        assert req.guests == 2

    def test_from_snake_case(self):
        req = UpsertCartRequest(
            room_id=uuid.UUID("b1000000-0000-0000-0000-000000000001"),
            hotel_id=uuid.UUID("a1000000-0000-0000-0000-000000000001"),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 3),
            guests=2,
        )
        assert req.room_id == uuid.UUID("b1000000-0000-0000-0000-000000000001")


class TestPriceBreakdown:
    def test_serialization_uses_camel_case(self):
        price = PriceBreakdown(
            price_per_night=Decimal("250000"),
            nights=2,
            subtotal=Decimal("500000"),
            vat=Decimal("95000"),
            total=Decimal("595000"),
        )
        data = price.model_dump(by_alias=True)
        assert "pricePerNight" in data
        assert "tourismTax" in data
        assert "serviceFee" in data
        assert data["currency"] == "COP"


class TestCartResponse:
    def test_serialization_uses_camel_case(self):
        now = datetime.now(timezone.utc)
        price = PriceBreakdown(
            price_per_night=Decimal("250000"),
            nights=2,
            subtotal=Decimal("500000"),
            vat=Decimal("95000"),
            total=Decimal("595000"),
        )
        cart = CartResponse(
            id=uuid.uuid4(),
            user_id=uuid.UUID("c1000000-0000-0000-0000-000000000001"),
            room_id=uuid.UUID("b1000000-0000-0000-0000-000000000001"),
            hotel_id=uuid.UUID("a1000000-0000-0000-0000-000000000001"),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 3),
            guests=2,
            hold_id=uuid.UUID("d1000000-0000-0000-0000-000000000001"),
            hold_expires_at=now,
            room_type="Deluxe",
            hotel_name="Hotel Test",
            room_name="Deluxe Room",
            location="Bogota, Colombia",
            rating=4.5,
            review_count=120,
            room_features="Ocean view",
            nights=2,
            price_breakdown=price,
            created_at=now,
        )
        data = cart.model_dump(by_alias=True)
        assert "userId" in data
        assert "roomId" in data
        assert "hotelId" in data
        assert "checkIn" in data
        assert "checkOut" in data
        assert "holdId" in data
        assert "holdExpiresAt" in data
        assert "roomType" in data
        assert "hotelName" in data
        assert "roomName" in data
        assert "reviewCount" in data
        assert "roomFeatures" in data
        assert "priceBreakdown" in data
        assert "createdAt" in data
