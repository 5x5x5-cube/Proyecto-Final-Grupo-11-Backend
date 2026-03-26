import uuid
from datetime import date

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..redis_client import get_redis
from ..schemas import CreateHoldRequest, HoldCheckResponse, HoldResponse
from ..services.hold_service import check_hold, create_hold, get_hold, release_hold

router = APIRouter(prefix="/holds", tags=["holds"])


@router.post("", response_model=HoldResponse, status_code=201)
async def create_hold_endpoint(
    request: CreateHoldRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    hold = await create_hold(
        db=db,
        redis=redis,
        room_id=request.room_id,
        user_id=request.user_id,
        check_in=request.check_in,
        check_out=request.check_out,
    )
    return HoldResponse(
        id=hold.id,
        room_id=hold.room_id,
        user_id=hold.user_id,
        check_in=hold.check_in,
        check_out=hold.check_out,
        status=hold.status,
        expires_at=hold.expires_at,
        created_at=hold.created_at,
        price_per_night=hold.price_per_night,
        tax_rate=hold.tax_rate,
        room_type=hold.room_type,
    )


@router.delete("/{hold_id}", status_code=204)
async def release_hold_endpoint(
    hold_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await release_hold(db=db, redis=redis, hold_id=hold_id)


@router.get("/{hold_id}")
async def get_hold_endpoint(
    hold_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    data = await get_hold(db=db, redis=redis, hold_id=hold_id)
    hold = data["hold"]
    return {
        "id": hold.id,
        "room_id": hold.room_id,
        "user_id": hold.user_id,
        "check_in": hold.check_in,
        "check_out": hold.check_out,
        "status": hold.status,
        "expires_at": hold.expires_at,
        "ttl_seconds": data["ttl"],
    }


@router.get("/check/{room_id}", response_model=HoldCheckResponse)
async def check_hold_endpoint(
    room_id: uuid.UUID,
    check_in: date = Query(..., alias="checkIn"),
    check_out: date = Query(..., alias="checkOut"),
    user_id: uuid.UUID = Query(..., alias="userId"),
    redis: aioredis.Redis = Depends(get_redis),
):
    result = await check_hold(
        redis=redis,
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
        user_id=user_id,
    )
    return HoldCheckResponse(
        held=result["held"],
        holder_id=result.get("holder_id"),
        hold_id=result.get("hold_id"),
    )
