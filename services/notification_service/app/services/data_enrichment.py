"""Fetches data from sibling services to enrich notifications."""

import logging
from typing import Any, Dict, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


async def _get(url: str, label: str) -> Optional[Dict[str, Any]]:
    """Generic GET helper with error handling."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("%s returned %s", label, resp.status_code)
            return None
    except Exception as e:
        logger.error("Failed to fetch %s: %s", label, e)
        return None


async def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user email and name from auth service."""
    return await _get(
        f"{settings.auth_service_url}/api/v1/auth/users/{user_id}",
        f"user {user_id}",
    )


async def get_booking_info(booking_id: str) -> Optional[Dict[str, Any]]:
    """Fetch booking details (code, dates, guests, prices, hotel/room names)."""
    return await _get(
        f"{settings.booking_service_url}/api/v1/bookings/{booking_id}",
        f"booking {booking_id}",
    )


async def get_payment_info(payment_id: str) -> Optional[Dict[str, Any]]:
    """Fetch payment details (amount, currency, payment method display)."""
    return await _get(
        f"{settings.payment_service_url}/api/v1/payments/{payment_id}",
        f"payment {payment_id}",
    )
