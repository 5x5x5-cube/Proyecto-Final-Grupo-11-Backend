"""Seed script for inventory_service: hotels, rooms, and availability."""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Availability, Base, Hotel, Room
from app.services.sqs_publisher import sqs_publisher


async def wait_for_sqs(retries: int = 10, delay: int = 3) -> bool:
    """Wait until the SQS queue is available."""
    import boto3
    from botocore.exceptions import ClientError

    client_kwargs = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if settings.aws_endpoint_url:
        client_kwargs["endpoint_url"] = settings.aws_endpoint_url
    client = boto3.client("sqs", **client_kwargs)
    for attempt in range(retries):
        try:
            client.get_queue_url(QueueName="hotel-sync-queue")
            print("SQS queue ready.")
            return True
        except ClientError:
            print(f"SQS not ready, retrying in {delay}s... ({attempt + 1}/{retries})")
            await asyncio.sleep(delay)
    print("SQS queue not available after retries, skipping publish.")
    return False


HOTELS = [
    {
        "id": uuid.UUID("a1000000-0000-0000-0000-000000000001"),
        "name": "Hotel Caribe Plaza",
        "description": "Luxury beachfront hotel in Cartagena with stunning Caribbean views",
        "city": "Cartagena",
        "country": "Colombia",
        "rating": 4.5,
        "rooms": [
            {
                "id": uuid.UUID("b1000000-0000-0000-0000-000000000001"),
                "room_type": "Standard",
                "room_number": "101",
                "capacity": 2,
                "price_per_night": 250000,
                "tax_rate": 0.19,
                "description": "Comfortable room with city view",
                "amenities": {"wifi": True, "ac": True, "tv": True},
                "total_quantity": 5,
            },
            {
                "id": uuid.UUID("b1000000-0000-0000-0000-000000000002"),
                "room_type": "Deluxe",
                "room_number": "201",
                "capacity": 2,
                "price_per_night": 450000,
                "tax_rate": 0.19,
                "description": "Spacious room with ocean view and balcony",
                "amenities": {
                    "wifi": True,
                    "ac": True,
                    "tv": True,
                    "minibar": True,
                    "balcony": True,
                },
                "total_quantity": 3,
            },
            {
                "id": uuid.UUID("b1000000-0000-0000-0000-000000000003"),
                "room_type": "Suite",
                "room_number": "301",
                "capacity": 4,
                "price_per_night": 850000,
                "tax_rate": 0.19,
                "description": "Presidential suite with private terrace and jacuzzi",
                "amenities": {
                    "wifi": True,
                    "ac": True,
                    "tv": True,
                    "minibar": True,
                    "balcony": True,
                    "jacuzzi": True,
                },
                "total_quantity": 1,
            },
        ],
    },
    {
        "id": uuid.UUID("a1000000-0000-0000-0000-000000000002"),
        "name": "Bogota Grand Hotel",
        "description": "Modern business hotel in the heart of Bogota's financial district",
        "city": "Bogota",
        "country": "Colombia",
        "rating": 4.2,
        "rooms": [
            {
                "id": uuid.UUID("b1000000-0000-0000-0000-000000000004"),
                "room_type": "Standard",
                "room_number": "102",
                "capacity": 2,
                "price_per_night": 180000,
                "tax_rate": 0.19,
                "description": "Business-ready room with workspace",
                "amenities": {"wifi": True, "ac": True, "tv": True, "desk": True},
                "total_quantity": 8,
            },
            {
                "id": uuid.UUID("b1000000-0000-0000-0000-000000000005"),
                "room_type": "Deluxe",
                "room_number": "202",
                "capacity": 3,
                "price_per_night": 320000,
                "tax_rate": 0.19,
                "description": "Premium room with mountain view",
                "amenities": {
                    "wifi": True,
                    "ac": True,
                    "tv": True,
                    "minibar": True,
                    "desk": True,
                },
                "total_quantity": 4,
            },
        ],
    },
    {
        "id": uuid.UUID("a1000000-0000-0000-0000-000000000003"),
        "name": "Medellin Eco Resort",
        "description": "Eco-friendly resort surrounded by nature in Medellin's hills",
        "city": "Medellin",
        "country": "Colombia",
        "rating": 4.7,
        "rooms": [
            {
                "id": uuid.UUID("b1000000-0000-0000-0000-000000000006"),
                "room_type": "Cabin",
                "room_number": "C1",
                "capacity": 2,
                "price_per_night": 200000,
                "tax_rate": 0.19,
                "description": "Cozy eco-cabin with garden view",
                "amenities": {"wifi": True, "garden_view": True},
                "total_quantity": 6,
            },
            {
                "id": uuid.UUID("b1000000-0000-0000-0000-000000000007"),
                "room_type": "Villa",
                "room_number": "V1",
                "capacity": 6,
                "price_per_night": 650000,
                "tax_rate": 0.19,
                "description": "Private villa with pool and panoramic views",
                "amenities": {
                    "wifi": True,
                    "private_pool": True,
                    "kitchen": True,
                    "garden_view": True,
                },
                "total_quantity": 2,
            },
        ],
    },
]

AVAILABILITY_DAYS = 60


async def seed(db_url: str | None = None) -> None:
    url = db_url or settings.database_url
    engine = create_async_engine(url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        # Check if data already exists
        result = await db.execute(select(Hotel).limit(1))
        if result.scalar_one_or_none():
            print("Database already contains data. Skipping seed.")
            await engine.dispose()
            return

        sqs_ready = await wait_for_sqs()
        today = date.today()

        for hotel_data in HOTELS:
            hotel = Hotel(
                id=hotel_data["id"],
                name=hotel_data["name"],
                description=hotel_data["description"],
                city=hotel_data["city"],
                country=hotel_data["country"],
                rating=hotel_data["rating"],
            )
            db.add(hotel)
            await db.flush()

            hotel_dict = {
                "id": str(hotel.id),
                "name": hotel.name,
                "description": hotel.description,
                "city": hotel.city,
                "country": hotel.country,
                "rating": hotel.rating,
            }
            if sqs_ready:
                await sqs_publisher.publish_hotel_created(hotel_dict)

            for room_data in hotel_data["rooms"]:
                room = Room(
                    id=room_data["id"],
                    hotel_id=hotel.id,
                    room_type=room_data["room_type"],
                    room_number=room_data["room_number"],
                    capacity=room_data["capacity"],
                    price_per_night=room_data["price_per_night"],
                    tax_rate=room_data["tax_rate"],
                    description=room_data["description"],
                    amenities=room_data["amenities"],
                    total_quantity=room_data["total_quantity"],
                )
                db.add(room)
                await db.flush()

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
                }
                if sqs_ready:
                    await sqs_publisher.publish_room_created(room_dict)

                # Generate availability for each day
                for i in range(AVAILABILITY_DAYS):
                    d = today + timedelta(days=i)
                    avail = Availability(
                        room_id=room.id,
                        date=d,
                        total_quantity=room_data["total_quantity"],
                        available_quantity=room_data["total_quantity"],
                    )
                    db.add(avail)

                    if sqs_ready:
                        await sqs_publisher.publish_availability_created(
                            {
                                "room_id": str(room.id),
                                "date": str(d),
                                "available_quantity": room_data["total_quantity"],
                            }
                        )

        await db.commit()
        print(
            f"Seed complete: {len(HOTELS)} hotels, "
            f"{sum(len(h['rooms']) for h in HOTELS)} rooms, "
            f"{AVAILABILITY_DAYS} days of availability each."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
