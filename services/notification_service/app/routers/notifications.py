import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import NotificationHistory, PushToken
from ..schemas import (
    NotificationHistoryResponse,
    NotificationResponse,
    RegisterTokenRequest,
    RegisterTokenResponse,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def get_user_id(request: Request) -> uuid.UUID:
    """Extract and validate the X-User-Id header."""
    raw = request.headers.get("X-User-Id")
    if not raw:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-User-Id header is not a valid UUID")


@router.post("/register-token", response_model=RegisterTokenResponse, status_code=201)
async def register_push_token(
    body: RegisterTokenRequest,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Register or update an Expo push token for a user's device.

    If a token for the same device_id already exists, it will be updated.
    """
    # Check if token already exists for this device
    result = await db.execute(select(PushToken).where(PushToken.device_id == body.device_id))
    existing_token = result.scalar_one_or_none()

    if existing_token:
        # Update existing token
        existing_token.expo_push_token = body.expo_push_token
        existing_token.platform = body.platform
        existing_token.user_id = user_id  # Update user_id in case device changed hands
        await db.commit()
        await db.refresh(existing_token)
        return RegisterTokenResponse.model_validate(existing_token)

    # Create new token
    new_token = PushToken(
        user_id=user_id,
        expo_push_token=body.expo_push_token,
        device_id=body.device_id,
        platform=body.platform,
    )
    db.add(new_token)
    await db.commit()
    await db.refresh(new_token)

    return RegisterTokenResponse.model_validate(new_token)


@router.delete("/token/{device_id}", status_code=204)
async def delete_push_token(
    device_id: str,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a push token for a specific device.

    Used when user logs out or uninstalls the app.
    """
    result = await db.execute(
        select(PushToken).where(PushToken.device_id == device_id, PushToken.user_id == user_id)
    )
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    await db.delete(token)
    await db.commit()
    return None


@router.get("/history", response_model=NotificationHistoryResponse)
async def get_notification_history(
    user_id: uuid.UUID = Depends(get_user_id),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get notification history for the authenticated user.

    Returns paginated list of notifications sent to the user.
    """
    # Count total
    count_result = await db.execute(
        select(func.count())
        .select_from(NotificationHistory)
        .where(NotificationHistory.user_id == user_id)
    )
    total = count_result.scalar_one()

    # Get paginated results
    offset = (page - 1) * limit
    result = await db.execute(
        select(NotificationHistory)
        .where(NotificationHistory.user_id == user_id)
        .order_by(NotificationHistory.sent_at.desc())
        .offset(offset)
        .limit(limit)
    )
    notifications = result.scalars().all()

    return NotificationHistoryResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        page=page,
        limit=limit,
    )
