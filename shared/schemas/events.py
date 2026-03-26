from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class EventType(str, Enum):
    ACCOMMODATION_CREATED = "accommodation.created"
    ACCOMMODATION_UPDATED = "accommodation.updated"
    ACCOMMODATION_DELETED = "accommodation.deleted"


class EventMetadata(BaseModel):
    retry_count: int = 0
    correlation_id: str
    source_service: str = "inventory-service"


class AccommodationEvent(BaseModel):
    event_id: str
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    previous_state: Optional[Dict[str, Any]] = None
    metadata: EventMetadata

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
