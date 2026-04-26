from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class HotelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    city: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    address: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    admin_id: Optional[UUID] = None


class HotelCreate(HotelBase):
    pass


class HotelResponse(HotelBase):
    id: UUID

    class Config:
        from_attributes = True
