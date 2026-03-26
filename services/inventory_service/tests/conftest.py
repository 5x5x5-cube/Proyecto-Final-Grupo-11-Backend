import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def mock_sqs_publisher():
    with patch('app.services.sqs_publisher.sqs_publisher') as mock:
        mock.publish_accommodation_created = AsyncMock(return_value=True)
        mock.publish_accommodation_updated = AsyncMock(return_value=True)
        mock.publish_accommodation_deleted = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
async def async_db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def override_get_db(async_db_session):
    async def _override_get_db():
        yield async_db_session
    
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
