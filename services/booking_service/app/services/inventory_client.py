"""Async HTTP client for the inventory_service."""

import logging
import uuid
from datetime import date

import httpx

from ..config import settings
from ..exceptions import InventoryServiceError

logger = logging.getLogger(__name__)

BASE_URL = settings.inventory_service_url


async def check_hold(
    room_id: uuid.UUID,
    check_in: date,
    check_out: date,
    user_id: uuid.UUID,
) -> dict:
    """Quick check if the room has an active hold for the date range."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/holds/check/{room_id}",
            params={
                "checkIn": check_in.isoformat(),
                "checkOut": check_out.isoformat(),
                "userId": str(user_id),
            },
        )
        if resp.status_code == 200:
            return resp.json()
        raise InventoryServiceError(f"Hold check failed: {resp.text}", status_code=resp.status_code)


async def create_hold(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    check_in: date,
    check_out: date,
) -> dict:
    """Create a 15-min hold on the room via inventory_service."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}/holds",
            json={
                "roomId": str(room_id),
                "userId": str(user_id),
                "checkIn": check_in.isoformat(),
                "checkOut": check_out.isoformat(),
            },
        )
        if resp.status_code == 201:
            return resp.json()
        if resp.status_code == 409:
            raise InventoryServiceError(
                resp.json().get("message", "Room unavailable or held"),
                status_code=409,
            )
        raise InventoryServiceError(
            f"Create hold failed: {resp.text}", status_code=resp.status_code
        )


async def release_hold(hold_id: uuid.UUID) -> None:
    """Release a hold (compensation on failure)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(f"{BASE_URL}/holds/{hold_id}")
            if resp.status_code not in (204, 404):
                logger.warning(f"Release hold {hold_id} returned {resp.status_code}: {resp.text}")
    except Exception:
        logger.exception(f"Failed to release hold {hold_id} (compensation)")


async def get_room(room_id: uuid.UUID) -> dict:
    """Get room details from inventory_service."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE_URL}/rooms/{room_id}")
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            raise InventoryServiceError(f"Room {room_id} not found", status_code=404)
        raise InventoryServiceError(f"Get room failed: {resp.text}", status_code=resp.status_code)
