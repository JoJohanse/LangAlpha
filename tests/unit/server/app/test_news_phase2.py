from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.conftest import create_test_app


@pytest_asyncio.fixture
async def client():
    from src.server.app.news import router

    app = create_test_app(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_news_hot_rank(client):
    provider = SimpleNamespace(
        get_news=AsyncMock(
            return_value={
                "results": [
                    {
                        "id": "n1",
                        "title": "AI rally",
                        "article_url": "https://example.com/n1",
                        "published_at": datetime.now(timezone.utc).isoformat(),
                        "tickers": ["AAPL"],
                        "source": {"name": "Reuters"},
                    }
                ]
            }
        )
    )
    tagged = [
        SimpleNamespace(
            article_id="n1",
            as_dict=lambda: {"article_id": "n1", "sector": "technology", "topic": "ai", "region": "US", "tags": ["technology", "ai"]},
        )
    ]
    ranked = [
        {
            "article_id": "n1",
            "title": "AI rally",
            "article_url": "https://example.com/n1",
            "source_name": "Reuters",
            "published_at": datetime.now(timezone.utc),
            "tickers": ["AAPL"],
            "sector": "technology",
            "topic": "ai",
            "region": "US",
            "tags": ["technology", "ai"],
            "importance_score": 88.0,
            "recency_score": 91.0,
            "source_count": 1,
        }
    ]
    with (
        patch("src.server.app.news.get_news_data_provider", AsyncMock(return_value=provider)),
        patch("src.server.app.news._enrichment.build_and_store_tags", AsyncMock(return_value=tagged)),
        patch("src.server.app.news._enrichment.build_hot_rank", return_value=ranked),
    ):
        resp = await client.get("/api/v1/news/hot-rank?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["article_id"] == "n1"
    assert body["results"][0]["importance_score"] == 88.0


@pytest.mark.asyncio
async def test_get_news_by_sector(client):
    rows = [
        {
            "article_id": "n2",
            "title": "Bank earnings beat",
            "article_url": "https://example.com/n2",
            "source_name": "Bloomberg",
            "published_at": datetime.now(timezone.utc),
            "tickers": ["JPM"],
            "sector": "finance",
            "topic": "earnings",
            "region": "US",
            "tags": ["finance", "earnings"],
        }
    ]
    with patch("src.server.app.news.tags_db.list_articles_by_sector", AsyncMock(return_value=rows)):
        resp = await client.get("/api/v1/news/by-sector/finance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["sector"] == "finance"


@pytest.mark.asyncio
async def test_get_news_by_topic(client):
    rows = [
        {
            "article_id": "n3",
            "title": "Fed signals cuts",
            "article_url": "https://example.com/n3",
            "source_name": "WSJ",
            "published_at": datetime.now(timezone.utc),
            "tickers": ["SPY"],
            "sector": "general",
            "topic": "macro",
            "region": "US",
            "tags": ["macro"],
        }
    ]
    with patch("src.server.app.news.tags_db.list_articles_by_topic", AsyncMock(return_value=rows)):
        resp = await client.get("/api/v1/news/by-topic/macro")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["topic"] == "macro"


@pytest.mark.asyncio
async def test_news_ask_returns_chat_payload(client):
    provider = SimpleNamespace(
        get_news_article=AsyncMock(
            return_value={
                "id": "n5",
                "title": "Tesla shipment update",
                "description": "Quarterly delivery data released",
                "article_url": "https://example.com/n5",
                "tickers": ["TSLA"],
                "source": {"name": "Reuters"},
            }
        )
    )
    with patch("src.server.app.news.get_news_data_provider", AsyncMock(return_value=provider)):
        resp = await client.post("/api/v1/news/n5/ask", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["article_id"] == "n5"
    assert "thread_initial_message" in body
    assert len(body["additional_context"]) == 1
