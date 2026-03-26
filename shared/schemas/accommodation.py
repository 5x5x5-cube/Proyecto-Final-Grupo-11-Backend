from datetime import datetime
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator


class AccommodationType(str, Enum):
    HOTEL = "hotel"
    HOSTEL = "hostel"
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    CABIN = "cabin"


class CancellationPolicy(str, Enum):
    FLEXIBLE = "flexible"
    MODERATE = "moderate"
    STRICT = "strict"


class AccommodationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class Coordinates(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class Location(BaseModel):
    city: str
    country: str
    address: str
    postal_code: Optional[str] = None
    coordinates: Coordinates


class Pricing(BaseModel):
    base_price: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    cleaning_fee: float = Field(default=0, ge=0)
    service_fee: float = Field(default=0, ge=0)
    total_price: Optional[float] = None

    @validator('total_price', always=True)
    def calculate_total_price(cls, v, values):
        if v is None:
            return (
                values.get('base_price', 0) +
                values.get('cleaning_fee', 0) +
                values.get('service_fee', 0)
            )
        return v


class Capacity(BaseModel):
    max_guests: int = Field(..., gt=0)
    bedrooms: int = Field(..., ge=0)
    beds: int = Field(..., ge=0)
    bathrooms: float = Field(..., ge=0)


class RatingBreakdown(BaseModel):
    cleanliness: float = Field(..., ge=0, le=5)
    accuracy: float = Field(..., ge=0, le=5)
    communication: float = Field(..., ge=0, le=5)
    location: float = Field(..., ge=0, le=5)
    check_in: float = Field(..., ge=0, le=5)
    value: float = Field(..., ge=0, le=5)


class Rating(BaseModel):
    average: float = Field(default=0, ge=0, le=5)
    count: int = Field(default=0, ge=0)
    breakdown: Optional[RatingBreakdown] = None


class Popularity(BaseModel):
    views_count: int = Field(default=0, ge=0)
    bookings_count: int = Field(default=0, ge=0)
    favorites_count: int = Field(default=0, ge=0)
    popularity_score: Optional[float] = None

    @validator('popularity_score', always=True)
    def calculate_popularity_score(cls, v, values):
        if v is None:
            views = values.get('views_count', 0)
            bookings = values.get('bookings_count', 0)
            favorites = values.get('favorites_count', 0)
            return (bookings * 10) + (favorites * 5) + (views * 0.1)
        return v


class Image(BaseModel):
    url: str
    is_primary: bool = False
    order: int = 0


class Availability(BaseModel):
    is_available: bool = True
    available_from: Optional[datetime] = None
    available_to: Optional[datetime] = None
    minimum_nights: int = Field(default=1, ge=1)
    maximum_nights: Optional[int] = None


class Policies(BaseModel):
    cancellation_policy: CancellationPolicy = CancellationPolicy.MODERATE
    check_in_time: str = "15:00"
    check_out_time: str = "11:00"
    house_rules: List[str] = []


class AccommodationBase(BaseModel):
    external_id: str
    provider: str
    title: str
    description: str
    accommodation_type: AccommodationType
    location: Location
    pricing: Pricing
    capacity: Capacity
    rating: Rating = Field(default_factory=Rating)
    popularity: Popularity = Field(default_factory=Popularity)
    amenities: List[str] = []
    images: List[Image] = []
    availability: Availability = Field(default_factory=Availability)
    policies: Policies = Field(default_factory=Policies)


class AccommodationCreate(AccommodationBase):
    pass


class AccommodationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    accommodation_type: Optional[AccommodationType] = None
    location: Optional[Location] = None
    pricing: Optional[Pricing] = None
    capacity: Optional[Capacity] = None
    rating: Optional[Rating] = None
    popularity: Optional[Popularity] = None
    amenities: Optional[List[str]] = None
    images: Optional[List[Image]] = None
    availability: Optional[Availability] = None
    policies: Optional[Policies] = None
    status: Optional[AccommodationStatus] = None


class AccommodationInDB(AccommodationBase):
    id: str
    status: AccommodationStatus = AccommodationStatus.ACTIVE
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccommodationResponse(AccommodationInDB):
    pass


class PopularityUpdate(BaseModel):
    views: Optional[int] = None
    bookings: Optional[int] = None
    favorites: Optional[int] = None
