import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.exceptions import InventoryServiceError
from app.services.inventory_client import check_hold, create_hold, get_room, release_hold


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_check_hold_not_held(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"held": False, "holder_id": None, "hold_id": None}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = await check_hold(
        room_id=uuid.uuid4(),
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        user_id=uuid.uuid4(),
    )
    assert result["held"] is False


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_check_hold_error_raises(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    with pytest.raises(InventoryServiceError):
        await check_hold(
            room_id=uuid.uuid4(),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 3),
            user_id=uuid.uuid4(),
        )


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_create_hold_success(mock_client_cls):
    hold_id = str(uuid.uuid4())
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": hold_id,
        "room_id": str(uuid.uuid4()),
        "status": "active",
        "price_per_night": 250000,
        "tax_rate": 0.19,
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = await create_hold(
        room_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
    )
    assert result["id"] == hold_id


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_create_hold_conflict_raises(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 409
    mock_resp.json.return_value = {"message": "Room unavailable or held"}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    with pytest.raises(InventoryServiceError) as exc_info:
        await create_hold(
            room_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 3),
        )
    assert exc_info.value.status_code == 409


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_release_hold_success(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 204

    mock_client = AsyncMock()
    mock_client.delete.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    # Should not raise
    await release_hold(uuid.uuid4())


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_release_hold_handles_failure_gracefully(mock_client_cls):
    mock_client = AsyncMock()
    mock_client.delete.side_effect = Exception("Connection refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    # Should NOT raise — compensation is best-effort
    await release_hold(uuid.uuid4())


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_get_room_success(mock_client_cls):
    room_id = uuid.uuid4()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": str(room_id),
        "room_type": "Standard",
        "price_per_night": 250000,
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = await get_room(room_id)
    assert result["room_type"] == "Standard"


@patch("app.services.inventory_client.httpx.AsyncClient")
async def test_get_room_not_found(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    with pytest.raises(InventoryServiceError) as exc_info:
        await get_room(uuid.uuid4())
    assert exc_info.value.status_code == 404
