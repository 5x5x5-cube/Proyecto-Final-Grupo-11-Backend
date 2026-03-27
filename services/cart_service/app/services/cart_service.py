from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import CartExpiredError, CartNotFoundError
from ..models import Cart
from ..schemas import CartResponse, PriceBreakdown
from . import inventory_client

logger = logging.getLogger(__name__)


def calculate_price(
    price_per_night: Decimal,
    tax_rate: Decimal,
    check_in: date,
    check_out: date,
) -> PriceBreakdown:
    nights = (check_out - check_in).days
    subtotal = price_per_night * nights
    vat = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = (subtotal + vat).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return PriceBreakdown(
        price_per_night=price_per_night,
        nights=nights,
        subtotal=subtotal,
        vat=vat,
        total=total,
    )


def _build_response(cart: Cart) -> CartResponse:
    price = calculate_price(
        Decimal(str(cart.price_per_night)),
        Decimal(str(cart.tax_rate)),
        cart.check_in,
        cart.check_out,
    )
    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        room_id=cart.room_id,
        hotel_id=cart.hotel_id,
        check_in=cart.check_in,
        check_out=cart.check_out,
        guests=cart.guests,
        hold_id=cart.hold_id,
        hold_expires_at=cart.hold_expires_at,
        room_type=cart.room_type,
        hotel_name=cart.hotel_name,
        room_name=cart.room_name,
        location=cart.location,
        rating=float(cart.rating) if cart.rating is not None else None,
        review_count=cart.review_count,
        room_features=cart.room_features,
        nights=price.nights,
        price_breakdown=price,
        created_at=cart.created_at,
    )


async def upsert_cart(
    db: AsyncSession,
    user_id: uuid.UUID,
    room_id: uuid.UUID,
    hotel_id: uuid.UUID,
    check_in: date,
    check_out: date,
    guests: int,
) -> CartResponse:
    # 1. Check for existing cart
    result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    existing = result.scalar_one_or_none()

    if existing is not None:
        # 2. Same room + same dates → idempotent return if hold still alive
        if (
            existing.room_id == room_id
            and existing.check_in == check_in
            and existing.check_out == check_out
            and existing.hold_expires_at > datetime.now(timezone.utc)
        ):
            return _build_response(existing)

        # 3. Different room or dates → release old hold, delete old cart
        try:
            await inventory_client.release_hold(existing.hold_id)
        except Exception:
            logger.warning("Failed to release old hold %s (may have expired)", existing.hold_id)
        await db.delete(existing)
        await db.flush()

    # 4. Create hold via inventory service
    hold_data = await inventory_client.create_hold(room_id, user_id, check_in, check_out)

    # 5. Get room + hotel display data
    room_data = await inventory_client.get_room(room_id)
    hotel_data = await inventory_client.get_room_hotel(room_id)

    # Build location from hotel data
    city = hotel_data.get("city", "")
    country = hotel_data.get("country", "")
    location = f"{city}, {country}" if city and country else city or country or ""

    # Room features from description/amenities
    room_features = room_data.get("description", "")

    # 6. Create cart row
    cart = Cart(
        user_id=user_id,
        room_id=room_id,
        hotel_id=hotel_id,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        hold_id=uuid.UUID(hold_data["id"]) if isinstance(hold_data["id"], str) else hold_data["id"],
        hold_expires_at=datetime.fromisoformat(hold_data["expires_at"]),
        price_per_night=hold_data.get("price_per_night", 0),
        tax_rate=hold_data.get("tax_rate", 0.19),
        room_type=hold_data.get("room_type", "standard"),
        hotel_name=hotel_data.get("name", ""),
        room_name=room_data.get("room_type", ""),
        location=location,
        rating=hotel_data.get("rating"),
        review_count=None,
        room_features=room_features,
    )
    db.add(cart)
    await db.commit()
    await db.refresh(cart)

    return _build_response(cart)


async def get_cart(db: AsyncSession, user_id: uuid.UUID) -> CartResponse:
    result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    cart = result.scalar_one_or_none()

    if cart is None:
        raise CartNotFoundError(str(user_id))

    # Check if hold has expired
    if cart.hold_expires_at < datetime.now(timezone.utc):
        await db.delete(cart)
        await db.commit()
        raise CartExpiredError(str(user_id))

    return _build_response(cart)


async def delete_cart(db: AsyncSession, user_id: uuid.UUID) -> None:
    result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    cart = result.scalar_one_or_none()

    if cart is None:
        raise CartNotFoundError(str(user_id))

    # Try to release hold (ignore errors — hold may have expired)
    try:
        await inventory_client.release_hold(cart.hold_id)
    except Exception:
        logger.warning(
            "Failed to release hold %s during cart delete (may have expired)", cart.hold_id
        )

    await db.delete(cart)
    await db.commit()
