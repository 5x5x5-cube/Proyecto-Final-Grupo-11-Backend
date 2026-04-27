from datetime import date, timedelta
from typing import Any, Dict

from app.redis_client import redis_client


class RedisIndexer:
    def __init__(self):
        self.rc = redis_client

    def index_hotel(self, hotel_id: str, hotel_data: Dict[str, Any]) -> bool:
        """Guarda el JSON del hotel en Redis con key hotel:{id}"""
        try:
            key = f"hotel:{hotel_id}"
            self.rc.json_set(key, hotel_data)
            print(f"Indexed hotel: {hotel_id} - {hotel_data.get('name')}")
            return True
        except Exception as e:
            print(f"Error indexing hotel {hotel_id}: {e}")
            return False

    def update_hotel(self, hotel_id: str, hotel_data: Dict[str, Any]) -> bool:
        """Actualiza el hotel — sobreescribe el JSON existente."""
        return self.index_hotel(hotel_id, hotel_data)

    def delete_hotel(self, hotel_id: str) -> bool:
        """Elimina el hotel del índice de Redis."""
        try:
            key = f"hotel:{hotel_id}"
            self.rc.json_delete(key)
            print(f"Deleted hotel from index: {hotel_id}")
            return True
        except Exception as e:
            print(f"Error deleting hotel {hotel_id}: {e}")
            return False

    def index_room(self, room_id: str, room_data: Dict[str, Any]) -> bool:
        """Guarda el JSON de la habitación en Redis con key room:{id}"""
        try:
            key = f"room:{room_id}"
            self.rc.json_set(key, room_data)
            print(f"Indexed room: {room_id} - {room_data.get('room_number')}")
            return True
        except Exception as e:
            print(f"Error indexing room {room_id}: {e}")
            return False

    def update_room(self, room_id: str, room_data: Dict[str, Any]) -> bool:
        """Actualiza la habitación — sobreescribe el JSON existente."""
        return self.index_room(room_id, room_data)

    def delete_room(self, room_id: str) -> bool:
        """Elimina la habitación del índice de Redis."""
        try:
            key = f"room:{room_id}"
            self.rc.json_delete(key)
            print(f"Deleted room from index: {room_id}")
            return True
        except Exception as e:
            print(f"Error deleting room {room_id}: {e}")
            return False

    def index_availability(self, room_id: str, availability_data: Dict[str, Any]) -> bool:
        """
        Guarda la disponibilidad de una habitación para un día específico.
        Key format: availability:{room_id}:{date}
        Stores: room_id, date, available_quantity

        Este método es llamado cuando el inventory-service publica un evento
        de disponibilidad a SQS y el consumer lo recibe.
        """
        try:
            avail_date = availability_data.get("date")
            available_quantity = availability_data.get("available_quantity", 0)

            key = f"availability:{room_id}:{avail_date}"
            self.rc.json_set(
                key,
                {
                    "room_id": room_id,
                    "date": avail_date,
                    "available_quantity": available_quantity,
                },
            )
            print(
                f"Indexed availability: room={room_id} date={avail_date} qty={available_quantity}"
            )
            return True
        except Exception as e:
            print(f"Error indexing availability for room {room_id}: {e}")
            return False

    def update_availability(self, room_id: str, availability_data: Dict[str, Any]) -> bool:
        """
        Actualiza la disponibilidad de un día — sobreescribe el registro existente.
        Se llama cuando el inventory-service actualiza el available_quantity
        (ej: alguien hizo una reserva o la canceló).
        """
        return self.index_availability(room_id, availability_data)

    def delete_availability(self, room_id: str, avail_date: str) -> bool:
        """
        Elimina la disponibilidad de una habitación para un día específico.
        Se llama cuando el inventory-service elimina un registro de disponibilidad.
        """
        try:
            key = f"availability:{room_id}:{avail_date}"
            self.rc.json_delete(key)
            print(f"Deleted availability: room={room_id} date={avail_date}")
            return True
        except Exception as e:
            print(f"Error deleting availability for room {room_id} date {avail_date}: {e}")
            return False

    def is_room_available_for_dates(self, room_id: str, check_in: date, check_out: date) -> bool:
        """
        Verifica si una habitación tiene available_quantity > 0 para TODOS
        los días del rango [check_in, check_out) — check_out no se incluye
        porque el huésped se va ese día, no lo ocupa.

        Ejemplo: check_in=2026-04-01, check_out=2026-04-03
        → verifica 2026-04-01 y 2026-04-02

        Retorna False si:
        - Algún día no tiene registro en Redis (nunca fue indexado)
        - Algún día tiene available_quantity <= 0 (sin stock)
        """
        days = (check_out - check_in).days
        dates = [check_in + timedelta(days=i) for i in range(days)]

        for d in dates:
            key = f"availability:{room_id}:{d}"
            try:
                qty = self.rc.json_get(key, "$.available_quantity")
                if not qty or qty <= 0:
                    return False
            except Exception:
                return False

        return True

    def upsert_tariff(self, room_id: str, tariff: Dict[str, Any]) -> bool:
        """Guarda o actualiza una tarifa en la lista tariffs:{room_id}"""
        try:
            key = f"tariffs:{room_id}"
            tariffs = self.get_tariffs(room_id)
            tariffs = [t for t in tariffs if t.get("id") != tariff.get("id")]
            tariffs.append(tariff)
            self.rc.json_set(key, tariffs)
            print(f"Upserted tariff {tariff.get('id')} for room {room_id}")
            return True
        except Exception as e:
            print(f"Error upserting tariff for room {room_id}: {e}")
            return False

    def delete_tariff(self, room_id: str, tariff_id: str) -> bool:
        """Elimina una tarifa de la lista tariffs:{room_id}"""
        try:
            key = f"tariffs:{room_id}"
            tariffs = self.get_tariffs(room_id)
            tariffs = [t for t in tariffs if t.get("id") != tariff_id]
            self.rc.json_set(key, tariffs)
            print(f"Deleted tariff {tariff_id} for room {room_id}")
            return True
        except Exception as e:
            print(f"Error deleting tariff {tariff_id} for room {room_id}: {e}")
            return False

    def get_tariffs(self, room_id: str) -> list:
        """Lee las tarifas de una habitación desde Redis"""
        try:
            key = f"tariffs:{room_id}"
            result = self.rc.json_get(key)
            if isinstance(result, list):
                return result[0] if result and isinstance(result[0], list) else result
            return []
        except Exception:
            return []


indexer = RedisIndexer()
