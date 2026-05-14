"""Seed script for inventory_service: hotels, rooms, and availability."""

import asyncio
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Availability, Base, Hotel, Room, Tariff
from app.services.sns_publisher import sns_publisher


async def wait_for_sns(retries: int = 10, delay: int = 3) -> bool:
    """Wait until the SNS topic is available."""
    import boto3
    from botocore.exceptions import ClientError

    client_kwargs = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if settings.aws_endpoint_url:
        client_kwargs["endpoint_url"] = settings.aws_endpoint_url
    client = boto3.client("sns", **client_kwargs)
    for attempt in range(retries):
        try:
            client.get_topic_attributes(TopicArn=settings.sns_topic_arn)
            print("SNS topic ready.")
            return True
        except ClientError:
            print(f"SNS not ready, retrying in {delay}s... ({attempt + 1}/{retries})")
            await asyncio.sleep(delay)
    print("SNS topic not available after retries, skipping publish.")
    return False


HOTELS = [
    {
        "id": uuid.UUID("a1000000-0000-0000-0000-000000000001"),
        "name": "Hotel Caribe Plaza",
        "description": "Luxury beachfront hotel in Cartagena with stunning Caribbean views",
        "city": "Cartagena",
        "country": "Colombia",
        "rating": 4.5,
        "admin_id": "hotel-admin-001",
        "image_url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&h=500&fit=crop",
        "images": [
            "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800&h=500&fit=crop",
        ],
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
                "images": [
                    "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1611892440504-42a792e24d32?w=600&h=400&fit=crop",
                ],
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
                "images": [
                    "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=600&h=400&fit=crop",
                ],
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
                "images": [
                    "https://images.unsplash.com/photo-1591088398332-8a7791972843?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=600&h=400&fit=crop",
                ],
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
        "image_url": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=800&h=500&fit=crop",
        "images": [
            "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1564501049412-61c2a3083791?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?w=800&h=500&fit=crop",
        ],
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
                "images": [
                    "https://images.unsplash.com/photo-1618773928121-c32242e63f39?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1595576508898-0ad5c879a061?w=600&h=400&fit=crop",
                ],
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
                "images": [
                    "https://images.unsplash.com/photo-1609766857041-ed402ea8069a?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1560185007-cde436f6a4d0?w=600&h=400&fit=crop",
                ],
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
        "image_url": "https://images.unsplash.com/photo-1610641818989-c2051b5e2cfd?w=800&h=500&fit=crop",
        "images": [
            "https://images.unsplash.com/photo-1610641818989-c2051b5e2cfd?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1559599238-308793637427?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde?w=800&h=500&fit=crop",
            "https://images.unsplash.com/photo-1505765050516-f72dcac9c60e?w=800&h=500&fit=crop",
        ],
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
                "images": [
                    "https://images.unsplash.com/photo-1595521624992-48a59aef95e3?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1604709177225-055f99402ea3?w=600&h=400&fit=crop",
                ],
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
                "images": [
                    "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=600&h=400&fit=crop",
                ],
                "total_quantity": 2,
            },
        ],
    },
]

AVAILABILITY_DAYS = 60

REVIEWS = {
    uuid.UUID("a1000000-0000-0000-0000-000000000001"): [
        {
            "name": "María García",
            "initial": "M",
            "date": "Marzo 2026",
            "stars": 5,
            "text": "Hotel espectacular, la vista al mar es increíble. El servicio fue impecable y la habitación muy cómoda. Definitivamente volvería.",
        },
        {
            "name": "Carlos Mendoza",
            "initial": "C",
            "date": "Febrero 2026",
            "stars": 4,
            "text": "Muy buena ubicación en Cartagena, cerca de la ciudad amurallada. La piscina es hermosa. Solo el desayuno podría mejorar.",
        },
        {
            "name": "Ana Rodríguez",
            "initial": "A",
            "date": "Enero 2026",
            "stars": 5,
            "text": "La suite presidencial es un sueño. El jacuzzi privado y la terraza con vista al Caribe hacen que valga cada peso.",
        },
        {
            "name": "David López",
            "initial": "D",
            "date": "Diciembre 2025",
            "stars": 4,
            "text": "Excelente hotel para vacaciones en familia. Las habitaciones son amplias y el personal muy amable.",
        },
    ],
    uuid.UUID("a1000000-0000-0000-0000-000000000002"): [
        {
            "name": "Laura Martínez",
            "initial": "L",
            "date": "Marzo 2026",
            "stars": 4,
            "text": "Perfecto para viajes de negocios. El escritorio en la habitación y el WiFi rápido son un plus. Buena ubicación en el centro financiero.",
        },
        {
            "name": "Roberto Sánchez",
            "initial": "R",
            "date": "Febrero 2026",
            "stars": 3,
            "text": "Hotel correcto para el precio. La habitación estándar es un poco pequeña pero limpia. El restaurante del hotel es bueno.",
        },
        {
            "name": "Patricia Torres",
            "initial": "P",
            "date": "Enero 2026",
            "stars": 5,
            "text": "La habitación Deluxe con vista a las montañas es preciosa. El servicio de transporte al aeropuerto fue muy conveniente.",
        },
    ],
    uuid.UUID("a1000000-0000-0000-0000-000000000003"): [
        {
            "name": "Fernando Ruiz",
            "initial": "F",
            "date": "Marzo 2026",
            "stars": 5,
            "text": "El eco-resort es un paraíso. Despertar rodeado de naturaleza y escuchar los pájaros no tiene precio. La villa con piscina privada es increíble.",
        },
        {
            "name": "Camila Herrera",
            "initial": "C",
            "date": "Febrero 2026",
            "stars": 5,
            "text": "Una experiencia única en Medellín. Las cabañas son acogedoras y el jardín es hermoso. Perfecto para desconectarse.",
        },
        {
            "name": "Andrés Vargas",
            "initial": "A",
            "date": "Enero 2026",
            "stars": 4,
            "text": "Muy buen concepto eco-friendly. La comida orgánica del restaurante es deliciosa. Solo faltaría mejor señal de celular.",
        },
        {
            "name": "Valentina Díaz",
            "initial": "V",
            "date": "Diciembre 2025",
            "stars": 5,
            "text": "Las vistas panorámicas desde la villa son espectaculares. El mejor hotel en el que me he hospedado en Colombia.",
        },
    ],
}


async def seed(db_url: str | None = None) -> None:
    url = db_url or settings.database_url
    engine = create_async_engine(url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Always seed reviews and sync images to Redis (idempotent)
    try:
        import json

        import redis as redis_lib

        r = redis_lib.from_url(settings.redis_url, decode_responses=True)

        # Reviews
        for hotel_id, hotel_reviews in REVIEWS.items():
            r.set(f"reviews:{hotel_id}", json.dumps(hotel_reviews))
        print(f"Reviews seeded into Redis: {len(REVIEWS)} hotels")

        # Sync hotel images to Redis (patch existing JSON objects)
        for hotel_data in HOTELS:
            key = f"hotel:{hotel_data['id']}"
            if r.exists(key):
                try:
                    r.json().set(key, "$.image_url", hotel_data.get("image_url"))
                    r.json().set(key, "$.images", hotel_data.get("images", []))
                except Exception:
                    # Fallback: read, merge, write
                    raw = r.get(key)
                    if raw:
                        obj = json.loads(raw)
                        obj["image_url"] = hotel_data.get("image_url")
                        obj["images"] = hotel_data.get("images", [])
                        r.set(key, json.dumps(obj))
            for room_data in hotel_data["rooms"]:
                rkey = f"room:{room_data['id']}"
                if r.exists(rkey):
                    try:
                        r.json().set(rkey, "$.images", room_data.get("images", []))
                    except Exception:
                        raw = r.get(rkey)
                        if raw:
                            obj = json.loads(raw)
                            obj["images"] = room_data.get("images", [])
                            r.set(rkey, json.dumps(obj))
        print("Hotel/room images synced to Redis")
    except Exception as e:
        print(f"WARNING: Could not seed to Redis: {e}")

    try:
        async with session_factory() as db:
            # Check if data already exists
            result = await db.execute(select(Hotel).limit(1))
            if result.scalar_one_or_none():
                print("Database already contains data. Skipping seed.")
                return

            sqs_ready = await wait_for_sns()
            today = date.today()

            for hotel_data in HOTELS:
                hotel = Hotel(
                    id=hotel_data["id"],
                    name=hotel_data["name"],
                    description=hotel_data["description"],
                    city=hotel_data["city"],
                    country=hotel_data["country"],
                    rating=hotel_data["rating"],
                    image_url=hotel_data.get("image_url"),
                    images=hotel_data.get("images"),
                    admin_id=hotel_data.get("admin_id"),
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
                    "image_url": hotel.image_url,
                    "images": hotel.images,
                }
                if sqs_ready:
                    await sns_publisher.publish_hotel_created(hotel_dict)

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
                        images=room_data.get("images"),
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
                        "images": room.images,
                    }
                    if sqs_ready:
                        await sns_publisher.publish_room_created(room_dict)

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
                            await sns_publisher.publish_availability_created(
                                {
                                    "room_id": str(room.id),
                                    "date": str(d),
                                    "available_quantity": room_data["total_quantity"],
                                }
                            )

            # Seed tariffs for Hotel Caribe Plaza
            tariffs_data = [
                {
                    "id": uuid.UUID("c1000000-0000-0000-0000-000000000001"),
                    "room_id": uuid.UUID("b1000000-0000-0000-0000-000000000001"),
                    "rate_type": "standard",
                    "price_per_night": 350000,
                    "start_date": None,
                    "end_date": None,
                },
                {
                    "id": uuid.UUID("c1000000-0000-0000-0000-000000000002"),
                    "room_id": uuid.UUID("b1000000-0000-0000-0000-000000000001"),
                    "rate_type": "weekend",
                    "price_per_night": 420000,
                    "start_date": None,
                    "end_date": None,
                },
                {
                    "id": uuid.UUID("c1000000-0000-0000-0000-000000000003"),
                    "room_id": uuid.UUID("b1000000-0000-0000-0000-000000000002"),
                    "rate_type": "standard",
                    "price_per_night": 500000,
                    "start_date": None,
                    "end_date": None,
                },
                {
                    "id": uuid.UUID("c1000000-0000-0000-0000-000000000004"),
                    "room_id": uuid.UUID("b1000000-0000-0000-0000-000000000002"),
                    "rate_type": "weekend",
                    "price_per_night": 600000,
                    "start_date": None,
                    "end_date": None,
                },
                {
                    "id": uuid.UUID("c1000000-0000-0000-0000-000000000005"),
                    "room_id": uuid.UUID("b1000000-0000-0000-0000-000000000003"),
                    "rate_type": "standard",
                    "price_per_night": 850000,
                    "start_date": None,
                    "end_date": None,
                },
                {
                    "id": uuid.UUID("c1000000-0000-0000-0000-000000000006"),
                    "room_id": uuid.UUID("b1000000-0000-0000-0000-000000000003"),
                    "rate_type": "season",
                    "price_per_night": 1100000,
                    "start_date": date(2026, 12, 20),
                    "end_date": date(2027, 1, 10),
                },
            ]
            for t in tariffs_data:
                db.add(
                    Tariff(
                        id=t["id"],
                        room_id=t["room_id"],
                        rate_type=t["rate_type"],
                        price_per_night=t["price_per_night"],
                        start_date=t["start_date"],
                        end_date=t["end_date"],
                    )
                )
                if sqs_ready:
                    await sns_publisher.publish_tariff_upserted(
                        {
                            "id": str(t["id"]),
                            "room_id": str(t["room_id"]),
                            "rate_type": t["rate_type"],
                            "price_per_night": float(t["price_per_night"]),
                            "start_date": t["start_date"].isoformat() if t["start_date"] else None,
                            "end_date": t["end_date"].isoformat() if t["end_date"] else None,
                        }
                    )

            await db.commit()
            print(
                f"Seed complete: {len(HOTELS)} hotels, "
                f"{sum(len(h['rooms']) for h in HOTELS)} rooms, "
                f"{AVAILABILITY_DAYS} days of availability each, "
                f"{len(tariffs_data)} tariffs."
            )
    except IntegrityError:
        # Another pod seeded concurrently — data already present, nothing to do.
        print("Seed skipped: data already inserted by another instance.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
