"""Backfill Redis search index from inventory-service HTTP API (no SNS)."""

import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.redis_indexer import indexer  # noqa: E402

INVENTORY_BASE = "http://inventory-service/api/v1/inventory"
HOTEL_IDS = [
    "a1000000-0000-0000-0000-000000000001",
    "a1000000-0000-0000-0000-000000000002",
    "a1000000-0000-0000-0000-000000000003",
]
ROOM_IDS = [
    "b1000000-0000-0000-0000-000000000001",
    "b1000000-0000-0000-0000-000000000002",
    "b1000000-0000-0000-0000-000000000003",
    "b1000000-0000-0000-0000-000000000004",
    "b1000000-0000-0000-0000-000000000005",
    "b1000000-0000-0000-0000-000000000006",
    "b1000000-0000-0000-0000-000000000007",
]


def main() -> None:
    today = date.today()
    check_out = today + timedelta(days=60)
    hotels = rooms = avail = 0

    with httpx.Client(timeout=30) as client:
        list_resp = client.get(f"{INVENTORY_BASE}/hotels")
        list_resp.raise_for_status()
        for hotel in list_resp.json():
            hid = hotel["id"]
            indexer.index_hotel(hid, hotel)
            hotels += 1

        for room_id in ROOM_IDS:
            room_resp = client.get(f"{INVENTORY_BASE}/rooms/{room_id}")
            if room_resp.status_code == 404:
                continue
            room_resp.raise_for_status()
            room = room_resp.json()
            indexer.index_room(room_id, room)
            rooms += 1

            avail_resp = client.get(
                f"{INVENTORY_BASE}/rooms/{room_id}/availability",
                params={"checkIn": today.isoformat(), "checkOut": check_out.isoformat()},
            )
            avail_resp.raise_for_status()
            for row in avail_resp.json().get("dates", []):
                indexer.index_availability(
                    room_id,
                    {
                        "room_id": room_id,
                        "date": row["date"],
                        "available_quantity": row["available_quantity"],
                    },
                )
                avail += 1

    print(f"Backfill done: {hotels} hotels, {rooms} rooms, {avail} availability rows.")


if __name__ == "__main__":
    main()
