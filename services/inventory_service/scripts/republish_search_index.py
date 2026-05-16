"""Re-publish inventory data to SNS so search-worker re-indexes Redis.

Use when Postgres has hotels/rooms/availability but Redis search index is stale
(e.g. seed skipped on restart, partial SNS sync, or Redis flush).
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Availability, Hotel, Room, Tariff
from app.services.sns_publisher import sns_publisher
from scripts.seed import wait_for_sns


async def republish() -> None:
    if not await wait_for_sns():
        raise SystemExit("SNS topic not available")

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    hotels_count = rooms_count = avail_count = tariffs_count = 0

    async with session_factory() as db:
        result = await db.execute(select(Hotel))
        hotels = result.scalars().all()

        for hotel in hotels:
            hotel_dict = {
                "id": str(hotel.id),
                "name": hotel.name,
                "description": hotel.description,
                "city": hotel.city,
                "country": hotel.country,
                "rating": float(hotel.rating) if hotel.rating is not None else None,
                "image_url": hotel.image_url,
                "images": hotel.images,
            }
            await sns_publisher.publish_hotel_created(hotel_dict)
            hotels_count += 1

            rooms_result = await db.execute(select(Room).where(Room.hotel_id == hotel.id))
            for room in rooms_result.scalars().all():
                room_dict = {
                    "id": str(room.id),
                    "hotel_id": str(room.hotel_id),
                    "room_type": room.room_type,
                    "room_number": room.room_number,
                    "capacity": room.capacity,
                    "price_per_night": float(room.price_per_night),
                    "tax_rate": float(room.tax_rate),
                    "total_quantity": room.total_quantity,
                    "amenities": room.amenities,
                    "images": room.images,
                }
                await sns_publisher.publish_room_created(room_dict)
                rooms_count += 1

                avail_result = await db.execute(
                    select(Availability).where(Availability.room_id == room.id)
                )
                for avail in avail_result.scalars().all():
                    await sns_publisher.publish_availability_created(
                        {
                            "room_id": str(room.id),
                            "date": str(avail.date),
                            "available_quantity": avail.available_quantity,
                        }
                    )
                    avail_count += 1

                tariff_result = await db.execute(select(Tariff).where(Tariff.room_id == room.id))
                for tariff in tariff_result.scalars().all():
                    await sns_publisher.publish_tariff_upserted(
                        {
                            "id": str(tariff.id),
                            "room_id": str(tariff.room_id),
                            "rate_type": tariff.rate_type,
                            "price_per_night": float(tariff.price_per_night),
                            "start_date": tariff.start_date.isoformat()
                            if tariff.start_date
                            else None,
                            "end_date": tariff.end_date.isoformat() if tariff.end_date else None,
                        }
                    )
                    tariffs_count += 1

    await engine.dispose()
    print(
        f"Republish complete: {hotels_count} hotels, {rooms_count} rooms, "
        f"{avail_count} availability rows, {tariffs_count} tariffs."
    )


if __name__ == "__main__":
    asyncio.run(republish())
