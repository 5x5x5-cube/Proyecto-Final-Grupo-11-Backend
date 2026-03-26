import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture
def mock_redis_client():
    with patch('app.redis_client.redis_client') as mock:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.ft.return_value.search.return_value.docs = []
        mock_client.ft.return_value.search.return_value.total = 0
        mock.get_client.return_value = mock_client
        yield mock


@pytest.fixture
def mock_search_service():
    with patch('app.services.search_service.search_service') as mock:
        mock.search.return_value = {
            "results": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
            "filters_applied": {},
            "sort": {"by": "popularity", "order": "desc"}
        }
        mock.get_suggestions.return_value = {
            "cities": [],
            "accommodations": []
        }
        yield mock


@pytest.fixture
def mock_indexer():
    with patch('app.services.redis_indexer.indexer') as mock:
        mock.get_accommodation.return_value = None
        mock.index_accommodation.return_value = True
        mock.update_accommodation.return_value = True
        mock.delete_accommodation.return_value = True
        yield mock
