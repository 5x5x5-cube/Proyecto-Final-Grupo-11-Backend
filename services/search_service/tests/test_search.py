from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def mock_redis():
    with patch("app.redis_client.redis.from_url") as mock:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_search_service():
    with patch("app.routes.search.search_service") as mock:
        yield mock

def test_search_hotels_endpoint_exists(mock_redis, mock_search_service):
    """El endpoint retorna la estructura esperada"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {},
    }
    client = TestClient(app)
    response = client.get("/search/hotels")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data


def test_search_no_results_returns_message(mock_redis, mock_search_service):
    """Si no hay resultados debe retornar mensaje amigable"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {},
    }
    client = TestClient(app)
    response = client.get("/search/hotels?city=CiudadInexistente")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert "message" in data


def test_search_with_city_filter(mock_redis, mock_search_service):
    """Buscar por ciudad llama al servicio con el parámetro correcto"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {"city": "Bogota"},
    }
    client = TestClient(app)
    response = client.get("/search/hotels?city=Bogota")
    assert response.status_code == 200
    mock_search_service.search_hotels.assert_called_once()
    call_kwargs = mock_search_service.search_hotels.call_args.kwargs
    assert call_kwargs["city"] == "Bogota"


def test_search_with_guests_filter(mock_redis, mock_search_service):
    """Buscar con número de huéspedes llama al servicio con el parámetro correcto"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {"guests": 2},
    }
    client = TestClient(app)
    response = client.get("/search/hotels?guests=2")
    assert response.status_code == 200
    call_kwargs = mock_search_service.search_hotels.call_args.kwargs
    assert call_kwargs["guests"] == 2


def test_search_with_dates_filter(mock_redis, mock_search_service):
    """Buscar con fechas llama al servicio con check_in y check_out"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {},
    }
    check_in = date.today() + timedelta(days=1)
    check_out = date.today() + timedelta(days=3)
    client = TestClient(app)
    response = client.get(f"/search/hotels?check_in={check_in}&check_out={check_out}")
    assert response.status_code == 200
    call_kwargs = mock_search_service.search_hotels.call_args.kwargs
    assert call_kwargs["check_in"] == check_in
    assert call_kwargs["check_out"] == check_out


def test_checkout_before_checkin_returns_400(mock_redis):
    """check_out anterior a check_in debe retornar 400"""
    client = TestClient(app)
    response = client.get("/search/hotels?check_in=2026-06-10&check_out=2026-06-05")
    assert response.status_code == 400
    assert "check-out" in response.json()["detail"].lower()


def test_checkin_in_past_returns_400(mock_redis):
    """check_in en el pasado debe retornar 400"""
    client = TestClient(app)
    response = client.get("/search/hotels?check_in=2024-01-01&check_out=2024-01-05")
    assert response.status_code == 400
    assert "past" in response.json()["detail"].lower()


def test_guests_zero_returns_400(mock_redis):
    """Número de huéspedes igual a 0 debe retornar 400"""
    client = TestClient(app)
    response = client.get("/search/hotels?guests=0")
    assert response.status_code == 400


def test_guests_negative_returns_400(mock_redis):
    """Número de huéspedes negativo debe retornar 400"""
    client = TestClient(app)
    response = client.get("/search/hotels?guests=-1")
    assert response.status_code == 422  # FastAPI valida ge=1 automáticamente


def test_checkin_equals_checkout_returns_400(mock_redis):
    """check_in igual a check_out debe retornar 400"""
    future_date = date.today() + timedelta(days=5)
    client = TestClient(app)
    response = client.get(f"/search/hotels?check_in={future_date}&check_out={future_date}")
    assert response.status_code == 400


def test_is_room_available_for_dates_all_available(mock_redis):
    """Habitación disponible en todas las fechas del rango retorna True"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        # Simula que todos los días tienen available_quantity = 2
        mock_client.json().get.return_value = [2]

        from app.services.redis_indexer import RedisIndexer
        indexer = RedisIndexer()
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=3)
        result = indexer.is_room_available_for_dates("room-123", check_in, check_out)
        assert result is True


def test_is_room_available_for_dates_one_day_unavailable(mock_redis):
    """Si un día tiene available_quantity = 0 retorna False"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        # Primer día disponible, segundo día sin disponibilidad
        mock_client.json().get.side_effect = [[1], [0]]

        from app.services.redis_indexer import RedisIndexer
        indexer = RedisIndexer()
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=3)
        result = indexer.is_room_available_for_dates("room-123", check_in, check_out)
        assert result is False


def test_is_room_available_no_redis_record(mock_redis):
    """Si no hay registro en Redis para una fecha retorna False"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        # No hay registro en Redis (retorna None)
        mock_client.json().get.return_value = None

        from app.services.redis_indexer import RedisIndexer
        indexer = RedisIndexer()
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=2)
        result = indexer.is_room_available_for_dates("room-123", check_in, check_out)
        assert result is False

def test_sqs_consumer_processes_availability_created():
    """El consumer procesa correctamente un evento de availability created"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.index_availability.return_value = True

        from app.services.sqs_consumer import SQSConsumer
        consumer = SQSConsumer.__new__(SQSConsumer)

        import json
        message = json.dumps({
            "event_type": "created",
            "entity_type": "availability",
            "data": {
                "availability": {
                    "room_id": "room-123",
                    "date": "2026-06-01",
                    "available_quantity": 3,
                }
            }
        })

        result = consumer.process_message(message)
        assert result is True
        mock_indexer.index_availability.assert_called_once_with(
            "room-123", {"room_id": "room-123", "date": "2026-06-01", "available_quantity": 3}
        )


def test_sqs_consumer_processes_availability_updated():
    """El consumer procesa correctamente un evento de availability updated"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.index_availability.return_value = True

        from app.services.sqs_consumer import SQSConsumer
        consumer = SQSConsumer.__new__(SQSConsumer)

        import json
        message = json.dumps({
            "event_type": "updated",
            "entity_type": "availability",
            "data": {
                "availability": {
                    "room_id": "room-123",
                    "date": "2026-06-01",
                    "available_quantity": 1,
                }
            }
        })

        result = consumer.process_message(message)
        assert result is True
        mock_indexer.index_availability.assert_called_once()


def test_sqs_consumer_processes_availability_deleted():
    """El consumer procesa correctamente un evento de availability deleted"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.delete_availability.return_value = True

        from app.services.sqs_consumer import SQSConsumer
        consumer = SQSConsumer.__new__(SQSConsumer)

        import json
        message = json.dumps({
            "event_type": "deleted",
            "entity_type": "availability",
            "data": {
                "availability": {
                    "room_id": "room-123",
                    "date": "2026-06-01",
                    "available_quantity": 0,
                }
            }
        })

        result = consumer.process_message(message)
        assert result is True
        mock_indexer.delete_availability.assert_called_once_with("room-123", "2026-06-01")


def test_sqs_consumer_availability_missing_room_id():
    """El consumer retorna False si falta room_id en el mensaje de availability"""
    with patch("app.services.sqs_consumer.indexer"):
        from app.services.sqs_consumer import SQSConsumer
        consumer = SQSConsumer.__new__(SQSConsumer)

        import json
        message = json.dumps({
            "event_type": "created",
            "entity_type": "availability",
            "data": {
                "availability": {
                    "date": "2026-06-01",
                    "available_quantity": 3,
                }
            }
        })

        result = consumer.process_message(message)
        assert result is False
