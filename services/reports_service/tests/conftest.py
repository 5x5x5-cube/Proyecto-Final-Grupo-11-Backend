import os

import pytest

# Set test environment variables before importing app
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"


@pytest.fixture
def anyio_backend():
    return "asyncio"
