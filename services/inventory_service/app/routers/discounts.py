import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..database import get_db
from ..models import Discount, Room, Tariff
from ..schemas import DiscountCreate, DiscountResponse, DiscountUpdate
from ..services.sns_publisher import sns_publisher

router = APIRouter(prefix="/discounts", tags=["inventory"])


async def _republish_tariff(tariff: Tariff, db: AsyncSession, is_update: bool = True) -> None:
    """Recalculate effective price and republish tariff event to SNS."""
    today = date.today()
    print(f"[republish] tariff={tariff.id} rate_type={tariff.rate_type} base={tariff.price_per_night}")
    result = await db.execute(
        select(Discount).where(
            Discount.tariff_id == tariff.id,
            Discount.start_date <= today,
            Discount.end_date >= today,
        )
    )
    discounts = result.scalars().all()
    print(f"[republish] active discounts found: {len(discounts)}")
    base = float(tariff.price_per_night)
    effective = base
    for d in discounts:
        if d.discount_type == "percentage":
            candidate = base * (1 - float(d.value) / 100)
        else:
            candidate = base - float(d.value)
        effective = min(effective, candidate)
    effective = max(0.0, effective)
    print(f"[republish] effective price={effective}, publishing to SNS...")

    await sns_publisher.publish_tariff_upserted(
        {
            "id": str(tariff.id),
            "room_id": str(tariff.room_id),
            "rate_type": tariff.rate_type,
            "price_per_night": effective,
            "start_date": tariff.start_date.isoformat() if tariff.start_date else None,
            "end_date": tariff.end_date.isoformat() if tariff.end_date else None,
        },
        is_update=is_update,
    )


def _compute_status(start_date: date, end_date: date) -> str:
    today = date.today()
    return "active" if start_date <= today <= end_date else "inactive"


def _build_discount_response(discount: Discount) -> DiscountResponse:
    return DiscountResponse(
        id=discount.id,
        tariff_id=discount.tariff_id,
        name=discount.name,
        discount_type=discount.discount_type,
        value=float(discount.value),
        start_date=discount.start_date,
        end_date=discount.end_date,
        status=_compute_status(discount.start_date, discount.end_date),
        created_at=discount.created_at,
    )


async def _get_hotel_uuid(hotel_id_header: str | None) -> uuid.UUID:
    if not hotel_id_header:
        raise HTTPException(status_code=400, detail="X-Hotel-Id header is required")
    try:
        return uuid.UUID(hotel_id_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Hotel-Id format")


@router.get("", response_model=list[DiscountResponse])
async def list_discounts(
    x_hotel_id: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    hotel_uuid = await _get_hotel_uuid(x_hotel_id)
    result = await db.execute(
        select(Discount)
        .join(Tariff, Discount.tariff_id == Tariff.id)
        .join(Room, Tariff.room_id == Room.id)
        .where(Room.hotel_id == hotel_uuid)
        .options(joinedload(Discount.tariff))
    )
    discounts = result.scalars().all()
    return [_build_discount_response(d) for d in discounts]


@router.post("", response_model=DiscountResponse, status_code=201)
async def create_discount(
    body: DiscountCreate,
    db: AsyncSession = Depends(get_db),
):
    tariff_result = await db.execute(select(Tariff).where(Tariff.id == body.tariff_id))
    tariff = tariff_result.scalar_one_or_none()
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    discount = Discount(
        tariff_id=body.tariff_id,
        name=body.name,
        discount_type=body.discount_type,
        value=body.value,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    await _republish_tariff(tariff, db)
    return _build_discount_response(discount)


@router.put("/{discount_id}", response_model=DiscountResponse)
async def update_discount(
    discount_id: uuid.UUID,
    body: DiscountUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Discount).where(Discount.id == discount_id))
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")

    if body.name is not None:
        discount.name = body.name
    if body.discount_type is not None:
        discount.discount_type = body.discount_type
    if body.value is not None:
        discount.value = body.value
    if body.start_date is not None:
        discount.start_date = body.start_date
    if body.end_date is not None:
        discount.end_date = body.end_date

    await db.commit()
    await db.refresh(discount)
    tariff_result = await db.execute(select(Tariff).where(Tariff.id == discount.tariff_id))
    tariff = tariff_result.scalar_one_or_none()
    if tariff:
        await _republish_tariff(tariff, db)
    return _build_discount_response(discount)


@router.delete("/{discount_id}", status_code=204)
async def delete_discount(
    discount_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Discount).where(Discount.id == discount_id))
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    tariff_result = await db.execute(select(Tariff).where(Tariff.id == discount.tariff_id))
    tariff = tariff_result.scalar_one_or_none()
    await db.delete(discount)
    await db.commit()
    if tariff:
        await _republish_tariff(tariff, db)
