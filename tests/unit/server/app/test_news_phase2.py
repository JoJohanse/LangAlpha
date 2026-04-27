"""Phase 2-B regression tests for news detail completeness, source stability, and insight session."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


# ---------------------------------------------------------------------------
# B1 — News detail completeness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_news_article_includes_sector_topic_region_tags(client):
    """B1: detail endpoint attaches sector/topic/region/tags from the tag system."""
    provider = SimpleNamespace(
        get_news_article=AsyncMock(
            return_value={
                "id": "n10",
                "title": "AAPL hits new high",
                "description": "Apple shares surged",
                "article_url": "https://example.com/n10",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "tickers": ["AAPL"],
                "keywords": [],
                "sentiments": [],
                "source": {"name": "Reuters"},
            }
        )
    )
    tagged = SimpleNamespace(
        article_id="n10",
        title="AAPL hits new high",
        article_url="https://example.com/n10",
        source_name="Reuters",
        published_at=datetime.now(timezone.utc),
        tickers=["AAPL"],
        sector="technology",
        topic="earnings",
        region="US",
        tags=["technology", "earnings"],
    )
    with (
        patch("src.server.app.news._cache.get_article_by_id", AsyncMock(return_value=None)),
        patch("src.server.app.news.get_news_data_provider", AsyncMock(return_value=provider)),
        patch("src.server.app.news._enrichment._tag_article", return_value=tagged),
        patch("src.server.app.news.tags_db.upsert_news_article_tag", AsyncMock()),
        patch("src.server.app.news.tags_db.get_article_tag", AsyncMock(return_value=None)),
    ):
        resp = await client.get("/api/v1/news/n10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sector"] == "technology"
    assert body["topic"] == "earnings"
    assert body["region"] == "US"
    assert "technology" in body["tags"]


@pytest.mark.asyncio
async def test_get_news_article_snapshot_fallback_includes_tags(client):
    """B1: snapshot fallback path also includes sector/topic/region/tags."""
    snapshot = {
        "article_id": "n11",
        "title": "Snapshot headline",
        "article_url": "https://example.com/n11",
        "source_name": "SnapshotSource",
        "published_at": datetime.now(timezone.utc),
        "tickers": ["TSLA"],
        "sector": "consumer",
        "topic": "automotive",
        "region": "US",
        "tags": ["consumer", "automotive"],
    }
    provider = SimpleNamespace(get_news_article=AsyncMock(return_value=None))
    with (
        patch("src.server.app.news._cache.get_article_by_id", AsyncMock(return_value=None)),
        patch("src.server.app.news.get_news_data_provider", AsyncMock(return_value=provider)),
        patch("src.server.app.news.tags_db.get_article_tag", AsyncMock(return_value=snapshot)),
    ):
        resp = await client.get("/api/v1/news/n11")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sector"] == "consumer"
    assert body["topic"] == "automotive"
    assert "automotive" in body["tags"]


@pytest.mark.asyncio
async def test_get_news_article_cached_enriched_with_tags(client):
    """B1: cached article also gets sector/topic/region/tags from db if present."""
    cached_article = {
        "id": "n12",
        "title": "Cached news",
        "description": "Some content",
        "article_url": "https://example.com/n12",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "tickers": ["AMZN"],
        "keywords": [],
        "sentiments": [],
        "source": {"name": "WSJ"},
    }
    tag_row = {
        "sector": "retail",
        "topic": "ecommerce",
        "region": "US",
        "tags": ["retail"],
    }
    with (
        patch("src.server.app.news._cache.get_article_by_id", AsyncMock(return_value=cached_article)),
        patch("src.server.app.news.tags_db.get_article_tag", AsyncMock(return_value=tag_row)),
    ):
        resp = await client.get("/api/v1/news/n12")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sector"] == "retail"
    assert body["topic"] == "ecommerce"


@pytest.mark.asyncio
async def test_get_news_article_falls_back_to_title_when_description_invalid(client):
    """B1: description that is purely numeric gets replaced with the article title."""
    provider = SimpleNamespace(
        get_news_article=AsyncMock(
            return_value={
                "id": "n6",
                "title": "Market headline fallback",
                "description": "6654416",
                "article_url": "https://example.com/n6",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "tickers": ["TSLA"],
                "keywords": [],
                "sentiments": [],
                "source": {"name": "Reuters"},
            }
        )
    )
    with (
        patch("src.server.app.news._cache.get_article_by_id", AsyncMock(return_value=None)),
        patch("src.server.app.news.get_news_data_provider", AsyncMock(return_value=provider)),
        patch("src.server.app.news._enrichment._tag_article", return_value=None),
        patch("src.server.app.news.tags_db.get_article_tag", AsyncMock(return_value=None)),
        patch("src.server.app.news.tags_db.upsert_news_article_tag", AsyncMock()),
    ):
        resp = await client.get("/api/v1/news/n6")
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "Market headline fallback"


@pytest.mark.asyncio
async def test_get_news_article_404_when_not_found(client):
    """B1: 404 returned when neither provider nor snapshot has the article."""
    provider = SimpleNamespace(get_news_article=AsyncMock(return_value=None))
    with (
        patch("src.server.app.news._cache.get_article_by_id", AsyncMock(return_value=None)),
        patch("src.server.app.news.get_news_data_provider", AsyncMock(return_value=provider)),
        patch("src.server.app.news.tags_db.get_article_tag", AsyncMock(return_value=None)),
    ):
        resp = await client.get("/api/v1/news/missing-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# B1 — Other existing endpoint tests
# ---------------------------------------------------------------------------


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
        patch("src.server.app.news.tags_db.list_article_tags_by_ids", AsyncMock(return_value={"n1": {"article_id": "n1"}})),
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


@pytest.mark.asyncio
async def test_news_ask_fallback_to_snapshot_when_provider_misses(client):
    provider = SimpleNamespace(get_news_article=AsyncMock(return_value=None))
    snapshot = {
        "article_id": "n9",
        "title": "Fallback title",
        "article_url": "https://example.com/n9",
        "source_name": "SnapshotSource",
        "published_at": datetime.now(timezone.utc),
        "tickers": ["NVDA"],
        "tags": ["ai"],
    }
    with (
        patch("src.server.app.news.get_news_data_provider", AsyncMock(return_value=provider)),
        patch("src.server.app.news.tags_db.get_article_tag", AsyncMock(return_value=snapshot)),
    ):
        resp = await client.post("/api/v1/news/n9/ask", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["article_id"] == "n9"
    assert len(body["additional_context"]) == 1


# ---------------------------------------------------------------------------
# B2 — Pobo proxy: single-article endpoint attempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pobo_get_news_article_uses_single_endpoint_when_available():
    """B2: get_news_article should try /news/{id} before falling back to list scan."""
    import httpx
    from src.data_client.pobo_proxy.news_source import PoboProxyNewsSource

    single_response = {
        "InfoID": "12345",
        "InfoTitle": "Single fetch article",
        "Summary": "Summary from single endpoint",
        "CreateTime": "2024-06-01T10:00:00",
        "URL": "https://example.com/pobo-12345",
        "Source": "PB",
        "InfoType": "021",
    }

    class FakeTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/news/12345":
                return httpx.Response(200, json=single_response)
            # Should not reach the list endpoint
            return httpx.Response(200, json={"items": []})

    source = PoboProxyNewsSource(transport=FakeTransport())
    result = await source.get_news_article("pobo-12345")
    assert result is not None
    assert result["id"] == "pobo-12345"
    assert result["title"] == "Single fetch article"


@pytest.mark.asyncio
async def test_pobo_get_news_article_falls_back_to_list_when_single_endpoint_fails():
    """B2: falls back to list scan when /news/{id} returns 404 or unexpected response."""
    import httpx
    from src.data_client.pobo_proxy.news_source import PoboProxyNewsSource

    list_response = {
        "items": [
            {
                "InfoID": "99999",
                "InfoTitle": "List fallback article",
                "Summary": "Found via list",
                "CreateTime": "2024-06-01T10:00:00",
                "URL": "https://example.com/pobo-99999",
                "Source": "PB",
                "InfoType": "021",
            }
        ]
    }

    class FakeTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if "/news/99999" in request.url.path:
                return httpx.Response(404)
            return httpx.Response(200, json=list_response)

    source = PoboProxyNewsSource(transport=FakeTransport())
    result = await source.get_news_article("pobo-99999")
    assert result is not None
    assert result["id"] == "pobo-99999"
    assert result["title"] == "List fallback article"


@pytest.mark.asyncio
async def test_pobo_get_news_article_returns_none_when_not_found():
    """B2: returns None cleanly when article is absent from both paths."""
    import httpx
    from src.data_client.pobo_proxy.news_source import PoboProxyNewsSource

    class FakeTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": []})

    source = PoboProxyNewsSource(transport=FakeTransport())
    result = await source.get_news_article("pobo-00000")
    assert result is None


# ---------------------------------------------------------------------------
# B2 — Pobo proxy: async availability check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pobo_proxy_available_async_is_awaitable():
    """B2: _pobo_proxy_available_async must be a coroutine (non-blocking)."""
    import inspect
    from src.data_client.registry import _pobo_proxy_available_async

    assert inspect.iscoroutinefunction(_pobo_proxy_available_async)


# ---------------------------------------------------------------------------
# B4 — Insight brief_session inference
# ---------------------------------------------------------------------------


def test_attach_brief_session_pre_market_is_morning():
    """B4: pre_market type maps to morning session."""
    from src.server.app.insights import _attach_brief_session

    result = _attach_brief_session({"type": "pre_market"})
    assert result["brief_session"] == "morning"


def test_attach_brief_session_post_market_is_evening():
    """B4: post_market type maps to evening session."""
    from src.server.app.insights import _attach_brief_session

    result = _attach_brief_session({"type": "post_market"})
    assert result["brief_session"] == "evening"


def test_attach_brief_session_market_update_morning_inferred():
    """B4: market_update insight completed at 00:00 UTC (08:00 Shanghai) → morning."""
    from src.server.app.insights import _attach_brief_session

    result = _attach_brief_session({"type": "market_update", "completed_at": "2024-06-01T00:00:00+00:00"})
    # 00:00 UTC = 08:00 Asia/Shanghai → morning
    assert result["brief_session"] == "morning"


def test_attach_brief_session_market_update_evening_inferred():
    """B4: market_update insight completed at 10:00 UTC (18:00 Shanghai) → evening."""
    from src.server.app.insights import _attach_brief_session

    result = _attach_brief_session({"type": "market_update", "completed_at": "2024-06-01T10:00:00+00:00"})
    # 10:00 UTC = 18:00 Asia/Shanghai → evening
    assert result["brief_session"] == "evening"


def test_attach_brief_session_personalized_uses_time_of_day():
    """B4: personalized insight infers session from completed_at in Shanghai time."""
    from src.server.app.insights import _attach_brief_session

    # 15:00 UTC = 23:00 Shanghai → evening
    result = _attach_brief_session({"type": "personalized", "completed_at": "2024-06-01T15:00:00+00:00"})
    assert result["brief_session"] == "evening"

    # 01:00 UTC = 09:00 Shanghai → morning
    result2 = _attach_brief_session({"type": "personalized", "completed_at": "2024-06-01T01:00:00+00:00"})
    assert result2["brief_session"] == "morning"


def test_attach_brief_session_no_completed_at_is_none():
    """B4: when completed_at is absent for a non-mapped type, brief_session is None."""
    from src.server.app.insights import _attach_brief_session

    result = _attach_brief_session({"type": "market_update"})
    assert result["brief_session"] is None


# ---------------------------------------------------------------------------
# B1 — NewsArticle model fields
# ---------------------------------------------------------------------------


def test_news_article_model_includes_tag_fields():
    """B1: NewsArticle model exposes sector, topic, region, tags with correct defaults."""
    from src.server.models.news import NewsArticle

    article = NewsArticle(
        id="test",
        title="Test article",
        published_at="2024-01-01T00:00:00Z",
        article_url="https://example.com",
        source={"name": "Reuters"},
    )
    assert article.sector is None
    assert article.topic is None
    assert article.region is None
    assert article.tags == []


def test_news_article_model_stores_tag_fields():
    """B1: NewsArticle model correctly stores provided sector, topic, region, tags."""
    from src.server.models.news import NewsArticle

    article = NewsArticle(
        id="test",
        title="Test article",
        published_at="2024-01-01T00:00:00Z",
        article_url="https://example.com",
        source={"name": "Reuters"},
        sector="technology",
        topic="ai",
        region="US",
        tags=["technology", "ai"],
    )
    assert article.sector == "technology"
    assert article.topic == "ai"
    assert article.region == "US"
    assert article.tags == ["technology", "ai"]
