import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import BookingNotFoundError
from ..models import Booking
from ..redis_client import get_redis
from ..schemas import BookingListResponse, BookingResponse, CreateBookingRequest
from ..services.booking_service import create_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingResponse, status_code=201)
async def create_booking_endpoint(
    request: CreateBookingRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await create_booking(db=db, redis=redis, request=request)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_detail(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise BookingNotFoundError(str(booking_id))
    return BookingResponse(
        id=booking.id,
        code=booking.code,
        userId=booking.user_id,
        hotelId=booking.hotel_id,
        roomId=booking.room_id,
        holdId=booking.hold_id,
        checkIn=booking.check_in,
        checkOut=booking.check_out,
        guests=booking.guests,
        status=booking.status,
        totalPrice=float(booking.total_price),
        currency=booking.currency,
        priceBreakdown=None,
        holdExpiresAt=None,
        createdAt=booking.created_at,
    )


@router.get("", response_model=BookingListResponse)
async def list_bookings(
    user_id: uuid.UUID = Query(..., alias="userId"),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    query = select(Booking).where(Booking.user_id == user_id)
    count_query = select(func.count()).select_from(Booking).where(Booking.user_id == user_id)

    if status:
        query = query.where(Booking.status == status)
        count_query = count_query.where(Booking.status == status)

    query = query.order_by(Booking.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    bookings = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return BookingListResponse(
        data=[
            BookingResponse(
                id=b.id,
                code=b.code,
                userId=b.user_id,
                hotelId=b.hotel_id,
                roomId=b.room_id,
                holdId=b.hold_id,
                checkIn=b.check_in,
                checkOut=b.check_out,
                guests=b.guests,
                status=b.status,
                totalPrice=float(b.total_price),
                currency=b.currency,
                priceBreakdown=None,
                holdExpiresAt=None,
                createdAt=b.created_at,
            )
            for b in bookings
        ],
        total=total,
        page=page,
        limit=limit,
    )
