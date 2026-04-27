"""Auth resolution services for the API gateway.

Two resolvers handle different endpoint types:
- resolve_traveler: validates token, returns user_id
- resolve_hotel_admin: validates token + resolves hotel_id from inventory
"""

import logging

import httpx

logger = logging.getLogger(__name__)

AUTH_TIMEOUT = 5.0


async def resolve_traveler(token: str, auth_service_url: str) -> dict | None:
    """Validate a Bearer token via the auth service.

    Returns {"user_id": ..., "role": ...} on success, None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=AUTH_TIMEOUT) as client:
            resp = await client.get(
                f"{auth_service_url}/api/v1/auth/me",
                params={"token": token},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {"user_id": data["user_id"], "role": data.get("role", "traveler")}
    except Exception:
        logger.exception("Failed to resolve traveler token")
        return None


async def resolve_hotel_admin(
    token: str, auth_service_url: str, inventory_service_url: str
) -> dict | None:
    """Validate a Bearer token and resolve the admin's hotel_id.

    1. Calls auth service /me to get user info
    2. Verifies role is hotel_admin
    3. Calls inventory service to find the hotel associated with this admin

    Returns {"user_id": ..., "role": ..., "hotel_id": ...} on success, None on failure.
    """
    user = await resolve_traveler(token, auth_service_url)
    if not user:
        return None

    if user["role"] != "hotel_admin":
        logger.warning("User %s is not a hotel_admin (role=%s)", user["user_id"], user["role"])
        return None

    try:
        async with httpx.AsyncClient(timeout=AUTH_TIMEOUT) as client:
            resp = await client.get(
                f"{inventory_service_url}/api/v1/inventory/hotels",
                params={"admin_id": user["user_id"]},
            )
        if resp.status_code != 200:
            logger.warning(
                "Inventory service returned %s for admin_id=%s", resp.status_code, user["user_id"]
            )
            return None

        hotels = resp.json()
        if not hotels:
            logger.warning("No hotel found for admin_id=%s", user["user_id"])
            return None

        hotel_id = str(hotels[0]["id"])
        return {"user_id": user["user_id"], "role": user["role"], "hotel_id": hotel_id}
    except Exception:
        logger.exception("Failed to resolve hotel for admin %s", user["user_id"])
        return None
