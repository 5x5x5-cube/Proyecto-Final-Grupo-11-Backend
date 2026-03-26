import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import enum


class AccommodationTypeEnum(str, enum.Enum):
    HOTEL = "hotel"
    HOSTEL = "hostel"
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    CABIN = "cabin"


class AccommodationStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class Accommodation(Base):
    __tablename__ = "accommodations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    
    title = Column(String, nullable=False)
    description = Column(String)
    accommodation_type = Column(SQLEnum(AccommodationTypeEnum), nullable=False, index=True)
    
    location = Column(JSON, nullable=False)
    pricing = Column(JSON, nullable=False)
    capacity = Column(JSON, nullable=False)
    rating = Column(JSON, nullable=False, default={})
    popularity = Column(JSON, nullable=False, default={})
    
    amenities = Column(JSON, default=[])
    images = Column(JSON, default=[])
    availability = Column(JSON, nullable=False)
    policies = Column(JSON, nullable=False)
    
    status = Column(
        SQLEnum(AccommodationStatusEnum),
        default=AccommodationStatusEnum.ACTIVE,
        nullable=False,
        index=True
    )
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Accommodation {self.title} ({self.external_id})>"
