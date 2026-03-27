from __future__ import annotations

import uuid
from datetime import date

import httpx

from ..config import settings
from ..exceptions import InventoryServiceError, RoomUnavailableError


async def create_hold(
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    check_in: date,
    check_out: date,
) -> dict:
    """POST /holds — create a hold on a room for the given dates."""
    async with httpx.AsyncClient(base_url=settings.inventory_service_url) as client:
        response = await client.post(
            "/holds",
            headers={"X-User-Id": str(user_id)},
            json={
                "roomId": str(room_id),
                "checkIn": check_in.isoformat(),
                "checkOut": check_out.isoformat(),
            },
        )
    if response.status_code == 201:
        return response.json()
    if response.status_code == 409:
        detail = response.json().get("message", "Room is unavailable")
        raise RoomUnavailableError(detail)
    if response.status_code == 404:
        raise InventoryServiceError("Room not found", status_code=404)
    raise InventoryServiceError(
        f"Inventory service error: {response.status_code}", status_code=response.status_code
    )


async def release_hold(hold_id: uuid.UUID) -> None:
    """DELETE /holds/{hold_id} — release an existing hold."""
    async with httpx.AsyncClient(base_url=settings.inventory_service_url) as client:
        response = await client.delete(f"/holds/{hold_id}")
    if response.status_code in (204, 404):
        return
    raise InventoryServiceError(
        f"Failed to release hold: {response.status_code}", status_code=response.status_code
    )


async def get_hold(hold_id: uuid.UUID) -> dict:
    """GET /holds/{hold_id} — retrieve hold details."""
    async with httpx.AsyncClient(base_url=settings.inventory_service_url) as client:
        response = await client.get(f"/holds/{hold_id}")
    if response.status_code == 200:
        return response.json()
    if response.status_code == 404:
        raise InventoryServiceError("Hold not found", status_code=404)
    raise InventoryServiceError(
        f"Inventory service error: {response.status_code}", status_code=response.status_code
    )


async def get_room(room_id: uuid.UUID) -> dict:
    """GET /rooms/{room_id} — retrieve room details."""
    async with httpx.AsyncClient(base_url=settings.inventory_service_url) as client:
        response = await client.get(f"/rooms/{room_id}")
    if response.status_code == 200:
        return response.json()
    if response.status_code == 404:
        raise InventoryServiceError("Room not found", status_code=404)
    raise InventoryServiceError(
        f"Inventory service error: {response.status_code}", status_code=response.status_code
    )


async def get_room_hotel(room_id: uuid.UUID) -> dict:
    """GET /rooms/{room_id}/hotel — retrieve hotel details for a room."""
    async with httpx.AsyncClient(base_url=settings.inventory_service_url) as client:
        response = await client.get(f"/rooms/{room_id}/hotel")
    if response.status_code == 200:
        return response.json()
    if response.status_code == 404:
        raise InventoryServiceError("Hotel not found", status_code=404)
    raise InventoryServiceError(
        f"Inventory service error: {response.status_code}", status_code=response.status_code
    )
