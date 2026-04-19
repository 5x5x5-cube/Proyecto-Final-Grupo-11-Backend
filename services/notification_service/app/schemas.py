import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterTokenRequest(BaseModel):
    expo_push_token: str = Field(..., alias="expoPushToken")
    device_id: str = Field(..., alias="deviceId")
    platform: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class RegisterTokenResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID = Field(..., alias="userId")
    expo_push_token: str = Field(..., alias="expoPushToken")
    device_id: str = Field(..., alias="deviceId")
    platform: Optional[str] = None
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID = Field(..., alias="userId")
    booking_id: uuid.UUID = Field(..., alias="bookingId")
    notification_type: str = Field(..., alias="notificationType")
    title: str
    body: str
    sent_at: datetime = Field(..., alias="sentAt")
    delivered: bool

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class NotificationHistoryResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    page: int
    limit: int
