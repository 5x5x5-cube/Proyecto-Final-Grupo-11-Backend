import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .database import Base


class PushToken(Base):
    __tablename__ = "push_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    expo_push_token = Column(String(255), nullable=False)
    device_id = Column(String(255), unique=True, nullable=False, index=True)
    platform = Column(String(10), nullable=True)  # 'ios' | 'android'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_used_at = Column(DateTime(timezone=True), nullable=True)


Index("idx_push_tokens_user_id", PushToken.user_id)
Index("idx_push_tokens_device_id", PushToken.device_id)


class NotificationHistory(Base):
    __tablename__ = "notification_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    booking_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    delivered = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    extra_data = Column(JSONB, nullable=True)


Index("idx_notification_history_user_id", NotificationHistory.user_id)
Index("idx_notification_history_booking_id", NotificationHistory.booking_id)
