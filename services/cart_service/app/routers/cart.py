from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import CartResponse, UpsertCartRequest
from ..services import cart_service

router = APIRouter(prefix="/api/v1", tags=["cart"])


def get_user_id(request: Request) -> uuid.UUID:
    """Extract and validate X-User-Id header."""
    user_id_header = request.headers.get("X-User-Id")
    if not user_id_header:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    try:
        return uuid.UUID(user_id_header)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid X-User-Id header")


@router.put("/cart", response_model=CartResponse)
async def upsert_cart_endpoint(
    body: UpsertCartRequest,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await cart_service.upsert_cart(
        db=db,
        user_id=user_id,
        room_id=body.room_id,
        hotel_id=body.hotel_id,
        check_in=body.check_in,
        check_out=body.check_out,
        guests=body.guests,
    )


@router.get("/cart", response_model=CartResponse)
async def get_cart_endpoint(
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await cart_service.get_cart(db=db, user_id=user_id)


@router.patch("/cart/complete", status_code=200)
async def complete_cart_endpoint(
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    await cart_service.complete_cart(db=db, user_id=user_id)
    return {"message": "Cart completed"}


@router.delete("/cart", status_code=204)
async def delete_cart_endpoint(
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    await cart_service.delete_cart(db=db, user_id=user_id)
