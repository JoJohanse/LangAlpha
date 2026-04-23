from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.conftest import create_test_app


@pytest_asyncio.fixture
async def client():
    from src.server.app.events import router

    app = create_test_app(router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_get_events_returns_list(client):
    row = {
        "event_id": "a0f4a8a8-8f5e-4a1a-a6f2-6ad329",
        "title": "AAPL event",
        "short_summary": "summary",
        "importance_score": 75.5,
        "sentiment": "positive",
        "start_time": datetime.now(timezone.utc),
        "primary_symbol": "AAPL",
        "symbols": ["AAPL"],
        "tags": ["ai"],
        "article_count": 2,
        "ai_takeaway": None,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    with (
        patch("src.server.app.events.market_event_db.list_events", new_callable=AsyncMock, return_value=[row]),
        patch("src.server.app.events.market_event_db.count_events", new_callable=AsyncMock, return_value=1),
    ):
        resp = await client.get("/api/v1/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["title"] == "AAPL event"


@pytest.mark.asyncio
async def test_interpret_event_uses_service(client):
    mock_service = MagicMock()
    mock_service.interpret_event = AsyncMock(return_value=("Interpretation", "model-x", False))
    with patch("src.server.app.events.EventService.get_instance", return_value=mock_service):
        resp = await client.post("/api/v1/events/evt-1/interpret", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_type"] == "event"
    assert body["target_id"] == "evt-1"
    assert body["interpretation"] == "Interpretation"


@pytest.mark.asyncio
async def test_get_event_detail_reads_related_articles_from_db_snapshot(client):
    row = {
        "event_id": "a0f4a8a8-8f5e-4a1a-a6f2-6ad329",
        "title": "GOOGL event",
        "short_summary": "summary",
        "importance_score": 70.0,
        "sentiment": "positive",
        "start_time": datetime.now(timezone.utc),
        "primary_symbol": "GOOGL",
        "symbols": ["GOOGL"],
        "tags": ["ai"],
        "article_count": 1,
        "ai_takeaway": None,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    links = [
        {
            "article_id": "fcf27a12-7d0c-33c9-8909-8e8c169c5042",
            "relevance_score": 1.0,
            "is_primary": True,
            "title": "Google-backed AI update",
            "article_url": "https://example.com/news/google-ai",
            "source_name": "Reuters",
            "published_at": datetime.now(timezone.utc),
        }
    ]
    with (
        patch("src.server.app.events.market_event_db.get_event", new_callable=AsyncMock, return_value=row),
        patch("src.server.app.events.market_event_db.list_event_article_links", new_callable=AsyncMock, return_value=links),
    ):
        resp = await client.get("/api/v1/events/a0f4a8a8-8f5e-4a1a-a6f2-6ad329")
    assert resp.status_code == 200
    body = resp.json()
    assert body["related_articles"][0]["article_id"] == "fcf27a12-7d0c-33c9-8909-8e8c169c5042"
    assert body["related_articles"][0]["title"] == "Google-backed AI update"
    assert body["related_articles"][0]["article_url"] == "https://example.com/news/google-ai"
