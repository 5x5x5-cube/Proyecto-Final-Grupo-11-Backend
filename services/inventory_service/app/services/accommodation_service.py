from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.accommodation import Accommodation
from app.services.sqs_publisher import sqs_publisher


class AccommodationService:
    
    @staticmethod
    async def create_accommodation(db: AsyncSession, accommodation_data: dict) -> Accommodation:
        db_accommodation = Accommodation(**accommodation_data)
        db.add(db_accommodation)
        await db.commit()
        await db.refresh(db_accommodation)
        
        accommodation_dict = {
            "id": str(db_accommodation.id),
            "external_id": db_accommodation.external_id,
            "provider": db_accommodation.provider,
            "title": db_accommodation.title,
            "description": db_accommodation.description,
            "accommodation_type": db_accommodation.accommodation_type.value,
            "location": db_accommodation.location,
            "pricing": db_accommodation.pricing,
            "capacity": db_accommodation.capacity,
            "rating": db_accommodation.rating,
            "popularity": db_accommodation.popularity,
            "amenities": db_accommodation.amenities,
            "images": db_accommodation.images,
            "availability": db_accommodation.availability,
            "policies": db_accommodation.policies,
            "status": db_accommodation.status.value,
            "created_at": db_accommodation.created_at.isoformat(),
            "updated_at": db_accommodation.updated_at.isoformat(),
        }
        
        await sqs_publisher.publish_accommodation_created(accommodation_dict)
        
        return db_accommodation

    @staticmethod
    async def get_accommodation(db: AsyncSession, accommodation_id: UUID) -> Optional[Accommodation]:
        result = await db.execute(
            select(Accommodation).where(Accommodation.id == accommodation_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_accommodation_by_external_id(
        db: AsyncSession,
        external_id: str,
        provider: str
    ) -> Optional[Accommodation]:
        result = await db.execute(
            select(Accommodation).where(
                Accommodation.external_id == external_id,
                Accommodation.provider == provider
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_accommodations(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        provider: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Accommodation]:
        query = select(Accommodation)
        
        if provider:
            query = query.where(Accommodation.provider == provider)
        if status:
            query = query.where(Accommodation.status == status)
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_accommodation(
        db: AsyncSession,
        accommodation_id: UUID,
        update_data: dict
    ) -> Optional[Accommodation]:
        accommodation = await AccommodationService.get_accommodation(db, accommodation_id)
        if not accommodation:
            return None
        
        previous_state = {
            "id": str(accommodation.id),
            "title": accommodation.title,
            "pricing": accommodation.pricing,
            "status": accommodation.status.value,
        }
        
        for key, value in update_data.items():
            if value is not None and hasattr(accommodation, key):
                setattr(accommodation, key, value)
        
        await db.commit()
        await db.refresh(accommodation)
        
        accommodation_dict = {
            "id": str(accommodation.id),
            "external_id": accommodation.external_id,
            "provider": accommodation.provider,
            "title": accommodation.title,
            "description": accommodation.description,
            "accommodation_type": accommodation.accommodation_type.value,
            "location": accommodation.location,
            "pricing": accommodation.pricing,
            "capacity": accommodation.capacity,
            "rating": accommodation.rating,
            "popularity": accommodation.popularity,
            "amenities": accommodation.amenities,
            "images": accommodation.images,
            "availability": accommodation.availability,
            "policies": accommodation.policies,
            "status": accommodation.status.value,
            "created_at": accommodation.created_at.isoformat(),
            "updated_at": accommodation.updated_at.isoformat(),
        }
        
        await sqs_publisher.publish_accommodation_updated(accommodation_dict, previous_state)
        
        return accommodation

    @staticmethod
    async def update_popularity(
        db: AsyncSession,
        accommodation_id: UUID,
        views: Optional[int] = None,
        bookings: Optional[int] = None,
        favorites: Optional[int] = None
    ) -> Optional[Accommodation]:
        accommodation = await AccommodationService.get_accommodation(db, accommodation_id)
        if not accommodation:
            return None
        
        popularity = accommodation.popularity or {}
        
        if views is not None:
            popularity['views_count'] = popularity.get('views_count', 0) + views
        if bookings is not None:
            popularity['bookings_count'] = popularity.get('bookings_count', 0) + bookings
        if favorites is not None:
            popularity['favorites_count'] = popularity.get('favorites_count', 0) + favorites
        
        views_count = popularity.get('views_count', 0)
        bookings_count = popularity.get('bookings_count', 0)
        favorites_count = popularity.get('favorites_count', 0)
        popularity['popularity_score'] = (bookings_count * 10) + (favorites_count * 5) + (views_count * 0.1)
        
        accommodation.popularity = popularity
        await db.commit()
        await db.refresh(accommodation)
        
        return accommodation

    @staticmethod
    async def delete_accommodation(db: AsyncSession, accommodation_id: UUID) -> bool:
        accommodation = await AccommodationService.get_accommodation(db, accommodation_id)
        if not accommodation:
            return False
        
        accommodation_dict = {
            "id": str(accommodation.id),
            "external_id": accommodation.external_id,
            "provider": accommodation.provider,
        }
        
        await db.delete(accommodation)
        await db.commit()
        
        await sqs_publisher.publish_accommodation_deleted(accommodation_dict)
        
        return True
