import json
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


# ─── ESTRUCTURA DEL ENDPOINT ──────────────────────────────────────────────────


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
    response = client.get("/api/v1/search/hotels")
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
    response = client.get("/api/v1/search/hotels?city=CiudadInexistente")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert "message" in data


# ─── FILTROS DE BÚSQUEDA ──────────────────────────────────────────────────────


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
    response = client.get("/api/v1/search/hotels?city=Bogota")
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
    response = client.get("/api/v1/search/hotels?guests=2")
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
    response = client.get(f"/api/v1/search/hotels?check_in={check_in}&check_out={check_out}")
    assert response.status_code == 200
    call_kwargs = mock_search_service.search_hotels.call_args.kwargs
    assert call_kwargs["check_in"] == check_in
    assert call_kwargs["check_out"] == check_out


def test_search_with_min_rating_filter(mock_redis, mock_search_service):
    """Buscar con rating mínimo llama al servicio con el parámetro correcto"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {"min_rating": 4.0},
    }
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels?min_rating=4.0")
    assert response.status_code == 200
    call_kwargs = mock_search_service.search_hotels.call_args.kwargs
    assert call_kwargs["min_rating"] == 4.0


def test_search_with_pagination(mock_redis, mock_search_service):
    """Buscar con paginación llama al servicio con page y page_size"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 2,
        "page_size": 10,
        "total_pages": 0,
        "filters": {},
    }
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels?page=2&page_size=10")
    assert response.status_code == 200
    call_kwargs = mock_search_service.search_hotels.call_args.kwargs
    assert call_kwargs["page"] == 2
    assert call_kwargs["page_size"] == 10


# ─── VALIDACIONES ─────────────────────────────────────────────────────────────


def test_checkout_before_checkin_returns_400(mock_redis):
    """check_out anterior a check_in debe retornar 400"""
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels?check_in=2026-06-10&check_out=2026-06-05")
    assert response.status_code == 400
    assert "check-out" in response.json()["detail"].lower()


def test_checkin_in_past_returns_400(mock_redis):
    """check_in en el pasado debe retornar 400"""
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels?check_in=2024-01-01&check_out=2024-01-05")
    assert response.status_code == 400
    assert "past" in response.json()["detail"].lower()


def test_guests_zero_returns_400(mock_redis):
    """Número de huéspedes igual a 0 debe retornar 400 o 422"""
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels?guests=0")
    assert response.status_code in (400, 422)


def test_guests_negative_returns_400(mock_redis):
    """Número de huéspedes negativo debe retornar 422"""
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels?guests=-1")
    assert response.status_code == 422


def test_checkin_equals_checkout_returns_400(mock_redis):
    """check_in igual a check_out debe retornar 400"""
    future_date = date.today() + timedelta(days=5)
    client = TestClient(app)
    response = client.get(f"/api/v1/search/hotels?check_in={future_date}&check_out={future_date}")
    assert response.status_code == 400


# ─── SEARCH SERVICE ───────────────────────────────────────────────────────────


def test_search_service_returns_hotels_with_rooms(mock_redis):
    """search_hotels retorna hoteles con habitaciones disponibles"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        # Mock resultado de búsqueda de hoteles
        mock_doc = MagicMock()
        mock_doc.json = json.dumps(
            {"id": "hotel-001", "name": "Hotel Test", "city": "Bogota", "rating": 4.5}
        )
        mock_client.ft().search().docs = [mock_doc]
        mock_client.ft().search().total = 1

        # Mock resultado de búsqueda de rooms
        mock_room_doc = MagicMock()
        mock_room_doc.json = json.dumps(
            {"id": "room-001", "hotel_id": "hotel-001", "price_per_night": 150000, "capacity": 2}
        )

        mock_client.ft().search.side_effect = [
            MagicMock(docs=[mock_doc]),
            MagicMock(docs=[mock_room_doc]),
        ]

        from app.services.search_service import SearchService

        service = SearchService()
        result = service.search_hotels(city="Bogota")

        assert "results" in result
        assert "total" in result
        assert "filters" in result


def test_search_service_handles_redis_error(mock_redis):
    """search_hotels maneja errores de Redis correctamente"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.ft().search.side_effect = Exception("Redis connection error")

        from app.services.search_service import SearchService

        service = SearchService()
        result = service.search_hotels(city="Bogota")

        assert result["total"] == 0
        assert result["results"] == []
        assert "error" in result


def test_get_hotel_rooms_calls_get_available_rooms(mock_redis):
    """get_hotel_rooms llama a _get_available_rooms correctamente"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.ft().search.return_value = MagicMock(docs=[])

        from app.services.search_service import SearchService

        service = SearchService()
        result = service.get_hotel_rooms("hotel-001")
        assert isinstance(result, list)


# ─── DISPONIBILIDAD POR FECHAS ────────────────────────────────────────────────


def test_is_room_available_for_dates_all_available(mock_redis):
    """Habitación disponible en todas las fechas retorna True"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().get.return_value = [2]

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=3)
        assert indexer.is_room_available_for_dates("room-123", check_in, check_out) is True


def test_is_room_available_for_dates_one_day_unavailable(mock_redis):
    """Si un día tiene available_quantity = 0 retorna False"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().get.side_effect = [[1], [0]]

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=3)
        assert indexer.is_room_available_for_dates("room-123", check_in, check_out) is False


def test_is_room_available_no_redis_record(mock_redis):
    """Si no hay registro en Redis retorna False"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().get.return_value = None

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=2)
        assert indexer.is_room_available_for_dates("room-123", check_in, check_out) is False


def test_is_room_available_redis_exception(mock_redis):
    """Si Redis lanza excepción retorna False"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().get.side_effect = Exception("Redis error")

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        check_in = date.today() + timedelta(days=1)
        check_out = date.today() + timedelta(days=2)
        assert indexer.is_room_available_for_dates("room-123", check_in, check_out) is False


# ─── REDIS INDEXER ────────────────────────────────────────────────────────────


def test_index_hotel_success(mock_redis):
    """index_hotel retorna True cuando Redis responde correctamente"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        result = indexer.index_hotel("hotel-001", {"id": "hotel-001", "name": "Test"})
        assert result is True


def test_index_hotel_failure(mock_redis):
    """index_hotel retorna False cuando Redis lanza excepción"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().set.side_effect = Exception("Redis error")

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        result = indexer.index_hotel("hotel-001", {"id": "hotel-001", "name": "Test"})
        assert result is False


def test_delete_hotel_success(mock_redis):
    """delete_hotel retorna True correctamente"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        result = indexer.delete_hotel("hotel-001")
        assert result is True


def test_index_room_success(mock_redis):
    """index_room retorna True correctamente"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        result = indexer.index_room("room-001", {"id": "room-001", "room_number": "101"})
        assert result is True


def test_index_room_failure(mock_redis):
    """index_room retorna False cuando Redis lanza excepción"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().set.side_effect = Exception("Redis error")

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        result = indexer.index_room("room-001", {"id": "room-001"})
        assert result is False


def test_index_availability_success(mock_redis):
    """index_availability retorna True correctamente"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        result = indexer.index_availability(
            "room-001", {"room_id": "room-001", "date": "2026-04-01", "available_quantity": 3}
        )
        assert result is True


def test_delete_availability_success(mock_redis):
    """delete_availability retorna True correctamente"""
    with patch("app.services.redis_indexer.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        from app.services.redis_indexer import RedisIndexer

        indexer = RedisIndexer()
        result = indexer.delete_availability("room-001", "2026-04-01")
        assert result is True


# ─── SQS CONSUMER ─────────────────────────────────────────────────────────────


def test_sqs_consumer_processes_hotel_created():
    """El consumer procesa correctamente un evento de hotel created"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.index_hotel.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "created",
                "entity_type": "hotel",
                "data": {"hotel": {"id": "hotel-001", "name": "Hotel Test"}},
            }
        )
        assert consumer.process_message(message) is True
        mock_indexer.index_hotel.assert_called_once()


def test_sqs_consumer_processes_hotel_updated():
    """El consumer procesa correctamente un evento de hotel updated"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.update_hotel.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "updated",
                "entity_type": "hotel",
                "data": {"hotel": {"id": "hotel-001", "name": "Hotel Test"}},
            }
        )
        assert consumer.process_message(message) is True


def test_sqs_consumer_processes_hotel_deleted():
    """El consumer procesa correctamente un evento de hotel deleted"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.delete_hotel.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "deleted",
                "entity_type": "hotel",
                "data": {"hotel": {"id": "hotel-001"}},
            }
        )
        assert consumer.process_message(message) is True


def test_sqs_consumer_hotel_missing_id():
    """El consumer retorna False si falta id en el mensaje de hotel"""
    with patch("app.services.sqs_consumer.indexer"):
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "created",
                "entity_type": "hotel",
                "data": {"hotel": {"name": "Hotel sin ID"}},
            }
        )
        assert consumer.process_message(message) is False


def test_sqs_consumer_processes_room_created():
    """El consumer procesa correctamente un evento de room created"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.index_room.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "created",
                "entity_type": "room",
                "data": {"room": {"id": "room-001", "hotel_id": "hotel-001"}},
            }
        )
        assert consumer.process_message(message) is True


def test_sqs_consumer_processes_room_deleted():
    """El consumer procesa correctamente un evento de room deleted"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.delete_room.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {"event_type": "deleted", "entity_type": "room", "data": {"room": {"id": "room-001"}}}
        )
        assert consumer.process_message(message) is True


def test_sqs_consumer_room_missing_id():
    """El consumer retorna False si falta id en el mensaje de room"""
    with patch("app.services.sqs_consumer.indexer"):
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "created",
                "entity_type": "room",
                "data": {"room": {"hotel_id": "hotel-001"}},
            }
        )
        assert consumer.process_message(message) is False


def test_sqs_consumer_unknown_entity_type():
    """El consumer retorna False para entity_type desconocido"""
    with patch("app.services.sqs_consumer.indexer"):
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps({"event_type": "created", "entity_type": "unknown", "data": {}})
        assert consumer.process_message(message) is False


def test_sqs_consumer_invalid_json():
    """El consumer retorna False para JSON inválido"""
    with patch("app.services.sqs_consumer.indexer"):
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        assert consumer.process_message("esto no es json") is False


def test_sqs_consumer_processes_availability_created():
    """El consumer procesa correctamente un evento de availability created"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.index_availability.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "created",
                "entity_type": "availability",
                "data": {
                    "availability": {
                        "room_id": "room-123",
                        "date": "2026-06-01",
                        "available_quantity": 3,
                    }
                },
            }
        )
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
        message = json.dumps(
            {
                "event_type": "updated",
                "entity_type": "availability",
                "data": {
                    "availability": {
                        "room_id": "room-123",
                        "date": "2026-06-01",
                        "available_quantity": 1,
                    }
                },
            }
        )
        assert consumer.process_message(message) is True


def test_sqs_consumer_processes_availability_deleted():
    """El consumer procesa correctamente un evento de availability deleted"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.delete_availability.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "deleted",
                "entity_type": "availability",
                "data": {
                    "availability": {
                        "room_id": "room-123",
                        "date": "2026-06-01",
                        "available_quantity": 0,
                    }
                },
            }
        )
        result = consumer.process_message(message)
        assert result is True
        mock_indexer.delete_availability.assert_called_once_with("room-123", "2026-06-01")


def test_sqs_consumer_availability_missing_room_id():
    """El consumer retorna False si falta room_id en el mensaje de availability"""
    with patch("app.services.sqs_consumer.indexer"):
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "created",
                "entity_type": "availability",
                "data": {"availability": {"date": "2026-06-01", "available_quantity": 3}},
            }
        )
        assert consumer.process_message(message) is False


# ─── POLL MESSAGES ────────────────────────────────────────────────────────────


def test_poll_messages_no_messages():
    """poll_messages retorna 0 cuando no hay mensajes en la cola"""
    with patch("app.services.sqs_consumer.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        mock_client.receive_message.return_value = {"Messages": []}

        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer()
        result = consumer.poll_messages()
        assert result == 0


def test_poll_messages_processes_and_deletes():
    """poll_messages procesa mensajes y los borra de la cola"""
    with patch("app.services.sqs_consumer.boto3") as mock_boto:
        with patch("app.services.sqs_consumer.indexer") as mock_indexer:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client
            mock_indexer.index_hotel.return_value = True

            mock_client.receive_message.return_value = {
                "Messages": [
                    {
                        "Body": json.dumps(
                            {
                                "event_type": "created",
                                "entity_type": "hotel",
                                "data": {"hotel": {"id": "hotel-001", "name": "Test"}},
                            }
                        ),
                        "ReceiptHandle": "receipt-001",
                    }
                ]
            }

            from app.services.sqs_consumer import SQSConsumer

            consumer = SQSConsumer()
            result = consumer.poll_messages()
            assert result == 1
            mock_client.delete_message.assert_called_once()


def test_poll_messages_failed_processing():
    """poll_messages no borra mensaje si el procesamiento falla"""
    with patch("app.services.sqs_consumer.boto3") as mock_boto:
        with patch("app.services.sqs_consumer.indexer") as mock_indexer:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client
            mock_indexer.index_hotel.return_value = False

            mock_client.receive_message.return_value = {
                "Messages": [
                    {
                        "Body": json.dumps(
                            {
                                "event_type": "created",
                                "entity_type": "hotel",
                                "data": {"hotel": {"id": "hotel-001", "name": "Test"}},
                            }
                        ),
                        "ReceiptHandle": "receipt-001",
                    }
                ]
            }

            from app.services.sqs_consumer import SQSConsumer

            consumer = SQSConsumer()
            result = consumer.poll_messages()
            assert result == 0
            mock_client.delete_message.assert_not_called()


def test_poll_messages_client_error():
    """poll_messages retorna 0 cuando SQS lanza ClientError"""
    with patch("app.services.sqs_consumer.boto3") as mock_boto:
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        mock_client.receive_message.side_effect = ClientError(
            {"Error": {"Code": "QueueDoesNotExist", "Message": "Queue not found"}}, "ReceiveMessage"
        )

        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer()
        result = consumer.poll_messages()
        assert result == 0


def test_sqs_consumer_process_message_exception():
    """process_message retorna False cuando ocurre una excepción inesperada"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.index_hotel.side_effect = Exception("Unexpected error")
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "created",
                "entity_type": "hotel",
                "data": {"hotel": {"id": "hotel-001", "name": "Test"}},
            }
        )
        assert consumer.process_message(message) is False


def test_sqs_consumer_processes_room_updated():
    """El consumer procesa correctamente un evento de room updated"""
    with patch("app.services.sqs_consumer.indexer") as mock_indexer:
        mock_indexer.update_room.return_value = True
        from app.services.sqs_consumer import SQSConsumer

        consumer = SQSConsumer.__new__(SQSConsumer)
        message = json.dumps(
            {
                "event_type": "updated",
                "entity_type": "room",
                "data": {"room": {"id": "room-001", "hotel_id": "hotel-001"}},
            }
        )
        assert consumer.process_message(message) is True
        mock_indexer.update_room.assert_called_once()


# ─── ROUTES ───────────────────────────────────────────────────────────────────


def test_search_returns_results_with_hotels(mock_redis, mock_search_service):
    """Cuando hay resultados no retorna mensaje"""
    mock_search_service.search_hotels.return_value = {
        "results": [{"id": "hotel-001", "name": "Hotel Test"}],
        "total": 1,
        "page": 1,
        "page_size": 20,
        "total_pages": 1,
        "filters": {},
    }
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "message" not in data


def test_get_hotel_rooms_with_results(mock_redis, mock_search_service):
    """get_hotel_rooms retorna habitaciones cuando existen"""
    mock_search_service.get_hotel_rooms.return_value = [
        {"id": "room-001", "hotel_id": "hotel-001", "price_per_night": 150000}
    ]
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels/hotel-001/rooms")
    assert response.status_code == 200
    data = response.json()
    assert data["hotel_id"] == "hotel-001"
    assert data["total"] == 1
    assert len(data["rooms"]) == 1


def test_get_hotel_rooms_no_results(mock_redis, mock_search_service):
    """get_hotel_rooms retorna mensaje cuando no hay habitaciones"""
    mock_search_service.get_hotel_rooms.return_value = []
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels/hotel-001/rooms")
    assert response.status_code == 200
    data = response.json()
    assert data["rooms"] == []
    assert "message" in data


# ─── DESTINOS ─────────────────────────────────────────────────────────────────


def test_get_destinations_endpoint_existe(mock_redis, mock_search_service):
    """El endpoint /search/destinations responde con 200"""
    mock_search_service.get_destinations.return_value = []
    client = TestClient(app)
    response = client.get("/api/v1/search/destinations")
    assert response.status_code == 200


def test_get_destinations_estructura_respuesta(mock_redis, mock_search_service):
    """La respuesta incluye los campos 'destinations' y 'total'"""
    mock_search_service.get_destinations.return_value = []
    client = TestClient(app)
    response = client.get("/api/v1/search/destinations")
    data = response.json()
    assert "destinations" in data
    assert "total" in data


def test_get_destinations_retorna_lista_de_ciudades(mock_redis, mock_search_service):
    """Retorna la lista de destinos cuando hay hoteles indexados"""
    mock_search_service.get_destinations.return_value = [
        {"city": "Bogotá", "country": "Colombia"},
        {"city": "Cartagena", "country": "Colombia"},
    ]
    client = TestClient(app)
    response = client.get("/api/v1/search/destinations")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["destinations"]) == 2


def test_get_destinations_cada_destino_tiene_city_y_country(mock_redis, mock_search_service):
    """Cada destino en la respuesta tiene los campos 'city' y 'country'"""
    mock_search_service.get_destinations.return_value = [
        {"city": "Medellín", "country": "Colombia"},
    ]
    client = TestClient(app)
    response = client.get("/api/v1/search/destinations")
    destino = response.json()["destinations"][0]
    assert "city" in destino
    assert "country" in destino


def test_get_destinations_lista_vacia_cuando_no_hay_hoteles(mock_redis, mock_search_service):
    """Retorna lista vacía cuando no hay hoteles indexados en Redis"""
    mock_search_service.get_destinations.return_value = []
    client = TestClient(app)
    response = client.get("/api/v1/search/destinations")
    data = response.json()
    assert data["destinations"] == []
    assert data["total"] == 0


def test_get_destinations_total_coincide_con_lista(mock_redis, mock_search_service):
    """El campo 'total' siempre coincide con la longitud de 'destinations'"""
    destinos = [
        {"city": "Lima", "country": "Perú"},
        {"city": "Ciudad de México", "country": "México"},
        {"city": "Santiago", "country": "Chile"},
    ]
    mock_search_service.get_destinations.return_value = destinos
    client = TestClient(app)
    response = client.get("/api/v1/search/destinations")
    data = response.json()
    assert data["total"] == len(data["destinations"])


def test_get_destinations_servicio_llama_get_destinations(mock_redis, mock_search_service):
    """El router llama exactamente una vez a search_service.get_destinations()"""
    mock_search_service.get_destinations.return_value = []
    client = TestClient(app)
    client.get("/api/v1/search/destinations")
    mock_search_service.get_destinations.assert_called_once()


def test_get_destinations_service_deduplicacion(mock_redis):
    """get_destinations no repite ciudades aunque haya varios hoteles en la misma ciudad"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        # Dos hoteles en Bogotá y uno en Medellín
        hotel_bogota_1 = json.dumps({"id": "h1", "city": "Bogotá", "country": "Colombia"})
        hotel_bogota_2 = json.dumps({"id": "h2", "city": "Bogotá", "country": "Colombia"})
        hotel_medellin = json.dumps({"id": "h3", "city": "Medellín", "country": "Colombia"})

        doc1, doc2, doc3 = MagicMock(), MagicMock(), MagicMock()
        doc1.json = hotel_bogota_1
        doc2.json = hotel_bogota_2
        doc3.json = hotel_medellin

        mock_client.ft().search.return_value = MagicMock(docs=[doc1, doc2, doc3])

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_destinations()

        # Bogotá debe aparecer solo una vez
        ciudades = [d["city"] for d in resultado]
        assert ciudades.count("Bogotá") == 1
        assert len(resultado) == 2


def test_get_destinations_service_ordenados_alfabeticamente(mock_redis):
    """get_destinations retorna los destinos ordenados alfabéticamente por ciudad"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        doc_lima = MagicMock()
        doc_lima.json = json.dumps({"id": "h1", "city": "Lima", "country": "Perú"})
        doc_bogota = MagicMock()
        doc_bogota.json = json.dumps({"id": "h2", "city": "Bogotá", "country": "Colombia"})
        doc_cdmx = MagicMock()
        doc_cdmx.json = json.dumps({"id": "h3", "city": "Ciudad de México", "country": "México"})

        mock_client.ft().search.return_value = MagicMock(docs=[doc_lima, doc_bogota, doc_cdmx])

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_destinations()
        ciudades = [d["city"] for d in resultado]

        assert ciudades == sorted(ciudades)


def test_get_destinations_service_ignora_ciudades_vacias(mock_redis):
    """get_destinations ignora hoteles sin campo 'city' o con city vacío"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        doc_valido = MagicMock()
        doc_valido.json = json.dumps({"id": "h1", "city": "Cartagena", "country": "Colombia"})
        doc_sin_ciudad = MagicMock()
        doc_sin_ciudad.json = json.dumps({"id": "h2", "city": "", "country": "Colombia"})
        doc_sin_campo = MagicMock()
        doc_sin_campo.json = json.dumps({"id": "h3", "country": "Colombia"})

        mock_client.ft().search.return_value = MagicMock(
            docs=[doc_valido, doc_sin_ciudad, doc_sin_campo]
        )

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_destinations()

        assert len(resultado) == 1
        assert resultado[0]["city"] == "Cartagena"


def test_get_destinations_service_maneja_error_redis(mock_redis):
    """get_destinations retorna lista vacía si Redis lanza una excepción"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.ft().search.side_effect = Exception("Redis no disponible")

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_destinations()

        assert resultado == []


# ─── DETALLE DE HOTEL ─────────────────────────────────────────────────────────


def test_get_hotel_detail_retorna_hotel_existente(mock_redis, mock_search_service):
    """El endpoint retorna los datos del hotel cuando existe en Redis"""
    hotel_data = {
        "id": "hotel-001",
        "name": "Hotel El Caribe",
        "city": "Cartagena",
        "country": "Colombia",
        "rating": 4.5,
        "description": "Hotel frente al mar",
    }
    mock_search_service.get_hotel_by_id.return_value = hotel_data
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels/hotel-001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "hotel-001"
    assert data["name"] == "Hotel El Caribe"


def test_get_hotel_detail_retorna_404_si_no_existe(mock_redis, mock_search_service):
    """El endpoint retorna 404 cuando el hotel no existe en Redis"""
    mock_search_service.get_hotel_by_id.return_value = None
    client = TestClient(app)
    response = client.get("/api/v1/search/hotels/hotel-inexistente")
    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"].lower()


def test_get_hotel_detail_llama_al_servicio_con_id_correcto(mock_redis, mock_search_service):
    """El router pasa el hotel_id correcto al servicio"""
    mock_search_service.get_hotel_by_id.return_value = {"id": "abc-123"}
    client = TestClient(app)
    client.get("/api/v1/search/hotels/abc-123")
    mock_search_service.get_hotel_by_id.assert_called_once_with("abc-123")


def test_get_hotel_detail_no_interfiere_con_rooms(mock_redis, mock_search_service):
    """GET /hotels/{id} y GET /hotels/{id}/rooms son rutas independientes"""
    mock_search_service.get_hotel_by_id.return_value = {"id": "hotel-001"}
    mock_search_service.get_hotel_rooms.return_value = [{"id": "room-001"}]
    client = TestClient(app)

    resp_detail = client.get("/api/v1/search/hotels/hotel-001")
    resp_rooms = client.get("/api/v1/search/hotels/hotel-001/rooms")

    assert resp_detail.status_code == 200
    assert resp_rooms.status_code == 200
    # Cada endpoint llama a su propio método del servicio
    mock_search_service.get_hotel_by_id.assert_called_once()
    mock_search_service.get_hotel_rooms.assert_called_once()


def test_get_hotel_by_id_lee_desde_redis(mock_redis):
    """get_hotel_by_id lee el JSON del hotel desde la key hotel:{id} en Redis"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client

        hotel_data = {"id": "hotel-001", "name": "Test Hotel", "city": "Bogotá"}
        # json().get con "$" retorna lista con el objeto raíz
        mock_client.json().get.return_value = [hotel_data]

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_hotel_by_id("hotel-001")

        mock_client.json().get.assert_called_once_with("hotel:hotel-001", "$")
        assert resultado == hotel_data


def test_get_hotel_by_id_retorna_none_si_key_no_existe(mock_redis):
    """get_hotel_by_id retorna None cuando la key no existe en Redis"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().get.return_value = None

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_hotel_by_id("hotel-inexistente")

        assert resultado is None


def test_get_hotel_by_id_retorna_none_si_lista_vacia(mock_redis):
    """get_hotel_by_id retorna None cuando Redis retorna lista vacía"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().get.return_value = []

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_hotel_by_id("hotel-001")

        assert resultado is None


def test_get_hotel_by_id_retorna_none_ante_error_redis(mock_redis):
    """get_hotel_by_id retorna None si Redis lanza una excepción"""
    with patch("app.services.search_service.redis_client") as mock_rc:
        mock_client = MagicMock()
        mock_rc.get_client.return_value = mock_client
        mock_client.json().get.side_effect = Exception("Redis no disponible")

        from app.services.search_service import SearchService

        servicio = SearchService()
        resultado = servicio.get_hotel_by_id("hotel-001")

        assert resultado is None
