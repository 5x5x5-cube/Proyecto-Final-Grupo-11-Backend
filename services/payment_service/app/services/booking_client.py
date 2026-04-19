"""HTTP client to create bookings via the booking service."""

import uuid
from typing import Any, Dict

import httpx

from ..config import settings


async def create_booking(user_id: uuid.UUID, cart: Dict[str, Any]) -> Dict[str, Any]:
    """Create a booking from cart data by calling the booking service."""
    price = cart.get("priceBreakdown", {})

    payload = {
        "roomId": cart.get("roomId"),
        "hotelId": cart.get("hotelId"),
        "holdId": cart.get("holdId"),
        "checkIn": cart.get("checkIn"),
        "checkOut": cart.get("checkOut"),
        "guests": cart.get("guests"),
        "basePrice": float(price.get("subtotal", 0)),
        "taxAmount": float(price.get("vat", 0)),
        "serviceFee": float(price.get("serviceFee", 0)),
        "totalPrice": float(price.get("total", 0)),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.booking_service_url}/api/v1/bookings",
            json=payload,
            headers={"X-User-Id": str(user_id)},
        )
        response.raise_for_status()
        return response.json()
