import uuid
from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import RoomNotFoundError, RoomUnavailableError
from ..models import Availability, Room


async def get_room(db: AsyncSession, room_id: uuid.UUID) -> Room:
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise RoomNotFoundError(str(room_id))
    return room


async def check_availability(
    db: AsyncSession, room_id: uuid.UUID, check_in: date, check_out: date
) -> list[Availability]:
    """Check availability for a room across a date range. Returns availability rows."""
    dates = _date_range(check_in, check_out)
    result = await db.execute(
        select(Availability).where(
            and_(Availability.room_id == room_id, Availability.date.in_(dates))
        )
    )
    rows = list(result.scalars().all())

    # Check all dates have available quantity > 0
    available_dates = {row.date for row in rows if row.available_quantity > 0}
    missing_or_unavailable = [d for d in dates if d not in available_dates]

    if missing_or_unavailable:
        # Check if missing dates have no row (means never seeded) vs quantity=0
        existing_dates = {row.date for row in rows}
        truly_missing = [d for d in dates if d not in existing_dates]
        if truly_missing:
            # Dates not seeded yet — validate room exists (raises RoomNotFoundError if not)
            await get_room(db, room_id)
            # Only unavailable if explicitly quantity=0
            zero_dates = [d for d in dates if d in existing_dates and d not in available_dates]
            if zero_dates:
                raise RoomUnavailableError(str(room_id), [d.isoformat() for d in zero_dates])
        else:
            raise RoomUnavailableError(
                str(room_id),
                [d.isoformat() for d in missing_or_unavailable],
            )

    return rows


async def reserve_dates(
    db: AsyncSession, room_id: uuid.UUID, check_in: date, check_out: date
) -> None:
    """
    Decrement available_quantity for each date in range using SELECT FOR UPDATE.
    Ported from experiment's reserve_room pattern.
    Must be called within a transaction.
    """
    room = await get_room(db, room_id)
    dates = _date_range(check_in, check_out)

    for d in dates:
        # SELECT FOR UPDATE — pessimistic DB lock per row
        result = await db.execute(
            select(Availability)
            .where(and_(Availability.room_id == room_id, Availability.date == d))
            .with_for_update()
        )
        avail = result.scalar_one_or_none()

        if not avail:
            # Lazy-init: create availability row if not seeded
            avail = Availability(
                room_id=room_id,
                date=d,
                total_quantity=room.total_quantity,
                available_quantity=room.total_quantity,
            )
            db.add(avail)
            await db.flush()
            # Re-lock the newly created row
            result = await db.execute(
                select(Availability)
                .where(and_(Availability.room_id == room_id, Availability.date == d))
                .with_for_update()
            )
            avail = result.scalar_one()

        if avail.available_quantity <= 0:
            raise RoomUnavailableError(str(room_id), [d.isoformat()])

        avail.available_quantity -= 1

    await db.flush()


async def release_dates(
    db: AsyncSession, room_id: uuid.UUID, check_in: date, check_out: date
) -> None:
    """
    Increment available_quantity for each date in range using SELECT FOR UPDATE.
    Ported from experiment's release_room pattern.
    """
    dates = _date_range(check_in, check_out)

    for d in dates:
        result = await db.execute(
            select(Availability)
            .where(and_(Availability.room_id == room_id, Availability.date == d))
            .with_for_update()
        )
        avail = result.scalar_one_or_none()

        if avail:
            # Get room to check total_quantity cap
            room_result = await db.execute(select(Room).where(Room.id == room_id))
            room = room_result.scalar_one_or_none()
            if room and avail.available_quantity < room.total_quantity:
                avail.available_quantity += 1

    await db.flush()


def _date_range(check_in: date, check_out: date) -> list[date]:
    """Generate list of dates from check_in to check_out (exclusive)."""
    days = (check_out - check_in).days
    return [check_in + timedelta(days=i) for i in range(days)]
