import uuid

import httpx

from ..config import settings


async def create_booking(user_id: uuid.UUID, booking_data: dict) -> dict:
    """Create a booking by calling the booking service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.booking_service_url}/api/v1/bookings",
            json=booking_data,
            headers={"X-User-Id": str(user_id)},
        )
        response.raise_for_status()
        return response.json()
