import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..database import get_db
from ..models import Hotel, Room, Tariff
from ..schemas import AdminRoomResponse, TariffCreate, TariffResponse, TariffUpdate
from ..services.sns_publisher import sns_publisher

router = APIRouter(prefix="", tags=["inventory"])


def _build_tariff_response(tariff: Tariff, room: Room, hotel: Hotel) -> TariffResponse:
    return TariffResponse(
        id=tariff.id,
        room_id=tariff.room_id,
        room_name=room.room_type,
        room_location=hotel.city or hotel.address or "",
        rate_type=tariff.rate_type,
        price_per_night=float(tariff.price_per_night),
        start_date=tariff.start_date,
        end_date=tariff.end_date,
        created_at=tariff.created_at,
    )


async def _get_hotel_uuid(hotel_id_header: str | None) -> uuid.UUID:
    if not hotel_id_header:
        raise HTTPException(status_code=400, detail="X-Hotel-Id header is required")
    try:
        return uuid.UUID(hotel_id_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Hotel-Id format")


# --- Rooms for hotel admin ---


@router.get("/rooms", response_model=list[AdminRoomResponse])
async def list_hotel_rooms(
    x_hotel_id: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    hotel_uuid = await _get_hotel_uuid(x_hotel_id)
    result = await db.execute(select(Room).where(Room.hotel_id == hotel_uuid))
    rooms = result.scalars().all()

    hotel_result = await db.execute(select(Hotel).where(Hotel.id == hotel_uuid))
    hotel = hotel_result.scalar_one_or_none()
    location = hotel.city if hotel else ""

    return [AdminRoomResponse(id=r.id, name=r.room_type, location=location) for r in rooms]


# --- Tariffs CRUD ---


@router.get("/tariffs", response_model=list[TariffResponse])
async def list_tariffs(
    x_hotel_id: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    hotel_uuid = await _get_hotel_uuid(x_hotel_id)
    result = await db.execute(
        select(Tariff)
        .join(Room, Tariff.room_id == Room.id)
        .where(Room.hotel_id == hotel_uuid)
        .options(joinedload(Tariff.room).joinedload(Room.hotel))
    )
    tariffs = result.scalars().all()
    return [_build_tariff_response(t, t.room, t.room.hotel) for t in tariffs]


@router.post("/tariffs", response_model=TariffResponse, status_code=201)
async def create_tariff(
    body: TariffCreate,
    db: AsyncSession = Depends(get_db),
):
    room_result = await db.execute(
        select(Room).where(Room.id == body.room_id).options(joinedload(Room.hotel))
    )
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    tariff = Tariff(
        room_id=body.room_id,
        rate_type=body.rate_type,
        price_per_night=body.price_per_night,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(tariff)
    await db.commit()
    await db.refresh(tariff)
    await sns_publisher.publish_tariff_upserted(
        {
            "id": str(tariff.id),
            "room_id": str(tariff.room_id),
            "rate_type": tariff.rate_type,
            "price_per_night": float(tariff.price_per_night),
            "start_date": tariff.start_date.isoformat() if tariff.start_date else None,
            "end_date": tariff.end_date.isoformat() if tariff.end_date else None,
        }
    )
    return _build_tariff_response(tariff, room, room.hotel)


@router.put("/tariffs/{tariff_id}", response_model=TariffResponse)
async def update_tariff(
    tariff_id: uuid.UUID,
    body: TariffUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Tariff)
        .where(Tariff.id == tariff_id)
        .options(joinedload(Tariff.room).joinedload(Room.hotel))
    )
    tariff = result.scalar_one_or_none()
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    if body.rate_type is not None:
        tariff.rate_type = body.rate_type
    if body.price_per_night is not None:
        tariff.price_per_night = body.price_per_night
    if body.start_date is not None:
        tariff.start_date = body.start_date
    if body.end_date is not None:
        tariff.end_date = body.end_date

    await db.commit()
    await db.refresh(tariff)
    await sns_publisher.publish_tariff_upserted(
        {
            "id": str(tariff.id),
            "room_id": str(tariff.room_id),
            "rate_type": tariff.rate_type,
            "price_per_night": float(tariff.price_per_night),
            "start_date": tariff.start_date.isoformat() if tariff.start_date else None,
            "end_date": tariff.end_date.isoformat() if tariff.end_date else None,
        },
        is_update=True,
    )
    return _build_tariff_response(tariff, tariff.room, tariff.room.hotel)


@router.delete("/tariffs/{tariff_id}", status_code=204)
async def delete_tariff(
    tariff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tariff).where(Tariff.id == tariff_id))
    tariff = result.scalar_one_or_none()
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")
    tariff_data = {
        "id": str(tariff.id),
        "room_id": str(tariff.room_id),
    }
    await db.delete(tariff)
    await db.commit()
    await sns_publisher.publish_tariff_deleted(tariff_data)
