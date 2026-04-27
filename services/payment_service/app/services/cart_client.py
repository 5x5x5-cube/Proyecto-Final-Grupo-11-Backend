"""HTTP client to fetch cart data from cart_service."""

import uuid

import httpx

from ..config import settings
from ..schemas import CartData


class CartNotFoundError(Exception):
    pass


class CartExpiredError(Exception):
    pass


async def get_cart(cart_id: uuid.UUID, user_id: uuid.UUID) -> CartData:
    """Fetch a cart by ID from the cart service and validate ownership."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.cart_service_url}/api/v1/cart",
            headers={"X-User-Id": str(user_id)},
        )

    if response.status_code == 404:
        raise CartNotFoundError(f"Cart not found for user {user_id}")

    if response.status_code == 410:
        raise CartExpiredError("Cart hold has expired")

    response.raise_for_status()
    cart = CartData.model_validate(response.json())

    if str(cart.id) != str(cart_id):
        raise CartNotFoundError(f"Cart {cart_id} does not match user's active cart")

    return cart
