from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import CartExpiredError, CartNotFoundError
from app.models import Cart
from app.services.cart_service import calculate_price, delete_cart, get_cart, upsert_cart


def _mock_db_with_result(cart_or_none):
    """Create a mock db session whose execute().scalar_one_or_none() returns the given value."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = cart_or_none
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


class TestCalculatePrice:
    def test_basic_calculation(self):
        price = calculate_price(
            price_per_night=Decimal("250000"),
            tax_rate=Decimal("0.19"),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 3),
        )
        assert price.nights == 2
        assert price.subtotal == Decimal("500000")
        assert price.vat == Decimal("95000.00")
        assert price.total == Decimal("595000.00")
        assert price.currency == "COP"

    def test_single_night(self):
        price = calculate_price(
            price_per_night=Decimal("100000"),
            tax_rate=Decimal("0.19"),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 2),
        )
        assert price.nights == 1
        assert price.subtotal == Decimal("100000")
        assert price.vat == Decimal("19000.00")
        assert price.total == Decimal("119000.00")


class TestUpsertCart:
    @patch("app.services.cart_service.inventory_client")
    async def test_upsert_creates_new_cart(
        self,
        mock_inv,
        mock_hold_response,
        mock_room_response,
        mock_hotel_response,
        sample_user_id,
        sample_room_id,
        sample_hotel_id,
    ):
        mock_inv.create_hold = AsyncMock(return_value=mock_hold_response)
        mock_inv.get_room = AsyncMock(return_value=mock_room_response)
        mock_inv.get_room_hotel = AsyncMock(return_value=mock_hotel_response)

        mock_db = _mock_db_with_result(None)

        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=3)

        # Mock refresh to set computed fields
        async def mock_refresh(cart):
            cart.id = uuid.uuid4()
            cart.created_at = datetime.now(timezone.utc)
            cart.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = mock_refresh

        result = await upsert_cart(
            db=mock_db,
            user_id=sample_user_id,
            room_id=sample_room_id,
            hotel_id=sample_hotel_id,
            check_in=check_in,
            check_out=check_out,
            guests=2,
        )

        assert result.hotel_name == "Hotel Test"
        assert result.room_name == "Deluxe"
        assert result.location == "Bogota, Colombia"
        mock_inv.create_hold.assert_called_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.services.cart_service.inventory_client")
    async def test_upsert_idempotent_same_room(
        self,
        mock_inv,
        sample_cart,
        sample_user_id,
        sample_room_id,
        sample_hotel_id,
    ):
        mock_db = _mock_db_with_result(sample_cart)

        result = await upsert_cart(
            db=mock_db,
            user_id=sample_user_id,
            room_id=sample_room_id,
            hotel_id=sample_hotel_id,
            check_in=sample_cart.check_in,
            check_out=sample_cart.check_out,
            guests=2,
        )

        # Should return existing cart without calling inventory
        mock_inv.create_hold.assert_not_called()
        assert result.hotel_name == "Hotel Test"

    @patch("app.services.cart_service.inventory_client")
    async def test_upsert_replaces_different_room(
        self,
        mock_inv,
        sample_cart,
        mock_hold_response,
        mock_room_response,
        mock_hotel_response,
        sample_user_id,
        sample_hotel_id,
    ):
        mock_inv.release_hold = AsyncMock()
        mock_inv.create_hold = AsyncMock(return_value=mock_hold_response)
        mock_inv.get_room = AsyncMock(return_value=mock_room_response)
        mock_inv.get_room_hotel = AsyncMock(return_value=mock_hotel_response)

        mock_db = _mock_db_with_result(sample_cart)

        new_room_id = uuid.UUID("b2000000-0000-0000-0000-000000000002")
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=3)

        async def mock_refresh(cart):
            cart.id = uuid.uuid4()
            cart.created_at = datetime.now(timezone.utc)
            cart.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = mock_refresh

        await upsert_cart(
            db=mock_db,
            user_id=sample_user_id,
            room_id=new_room_id,
            hotel_id=sample_hotel_id,
            check_in=check_in,
            check_out=check_out,
            guests=2,
        )

        # Should release old hold and create new one
        mock_inv.release_hold.assert_called_once_with(sample_cart.hold_id)
        mock_db.delete.assert_called_once_with(sample_cart)
        mock_inv.create_hold.assert_called_once()


class TestGetCart:
    async def test_get_cart_not_found(self, sample_user_id):
        mock_db = _mock_db_with_result(None)

        with pytest.raises(CartNotFoundError):
            await get_cart(db=mock_db, user_id=sample_user_id)

    async def test_get_cart_expired(self, sample_cart, sample_user_id):
        # Set hold to expired
        sample_cart.hold_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        mock_db = _mock_db_with_result(sample_cart)

        with pytest.raises(CartExpiredError):
            await get_cart(db=mock_db, user_id=sample_user_id)

        mock_db.delete.assert_called_once_with(sample_cart)
        mock_db.commit.assert_called_once()

    async def test_get_cart_success(self, sample_cart, sample_user_id):
        mock_db = _mock_db_with_result(sample_cart)

        result = await get_cart(db=mock_db, user_id=sample_user_id)

        assert result.hotel_name == "Hotel Test"
        assert result.nights == 2


class TestDeleteCart:
    async def test_delete_cart_not_found(self, sample_user_id):
        mock_db = _mock_db_with_result(None)

        with pytest.raises(CartNotFoundError):
            await delete_cart(db=mock_db, user_id=sample_user_id)

    @patch("app.services.cart_service.inventory_client")
    async def test_delete_cart_success(self, mock_inv, sample_cart, sample_user_id):
        mock_inv.release_hold = AsyncMock()

        mock_db = _mock_db_with_result(sample_cart)

        await delete_cart(db=mock_db, user_id=sample_user_id)

        mock_inv.release_hold.assert_called_once_with(sample_cart.hold_id)
        mock_db.delete.assert_called_once_with(sample_cart)
        mock_db.commit.assert_called_once()
