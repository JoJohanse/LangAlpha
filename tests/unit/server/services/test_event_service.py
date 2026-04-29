from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.server.services.event_service import EventService


def _article(
    article_id: str,
    title: str,
    tickers: list[str],
    published_at: datetime,
):
    return {
        "id": article_id,
        "title": title,
        "published_at": published_at.isoformat(),
        "tickers": tickers,
        "source": {"name": "Reuters"},
        "sentiments": [{"ticker": tickers[0], "sentiment": "positive"}] if tickers else [],
    }


def test_cluster_merges_similar_news_into_one_event():
    svc = EventService.get_instance()
    now = datetime.now(timezone.utc)
    data = [
        _article("a1", "Apple launches new AI iPhone strategy", ["AAPL"], now),
        _article("a2", "Apple unveils AI strategy for iPhone lineup", ["AAPL"], now - timedelta(minutes=40)),
    ]

    clusters = svc._cluster_articles(data)  # noqa: SLF001 - unit-test private behavior
    assert len(clusters) == 1
    assert len(clusters[0].articles) == 2


def test_cluster_splits_different_events():
    svc = EventService.get_instance()
    now = datetime.now(timezone.utc)
    data = [
        _article("a1", "Apple launches new AI iPhone strategy", ["AAPL"], now),
        _article("a2", "Tesla recalls vehicles after brake report", ["TSLA"], now - timedelta(minutes=10)),
    ]

    clusters = svc._cluster_articles(data)  # noqa: SLF001
    assert len(clusters) == 2


@pytest.mark.asyncio
async def test_persist_clusters_generates_title_and_takeaway_before_upsert():
    svc = EventService.get_instance()
    now = datetime.now(timezone.utc)
    data = [
        _article("a1", "Apple launches new AI iPhone strategy", ["AAPL"], now),
        _article("a2", "Apple unveils AI strategy for iPhone lineup", ["AAPL"], now - timedelta(minutes=40)),
    ]
    clusters = svc._cluster_articles(data)  # noqa: SLF001

    generated = (
        None,
        "Apple AI handset strategy expansion",
        "Apple kept releasing AI handset updates, and the market is watching the read-through for hardware demand and suppliers.",
        True,
    )

    with (
        patch.object(svc, "_generate_event_interpretation", new=AsyncMock(return_value=generated)),
        patch(
            "src.server.services.event_service.market_event_db.upsert_market_event",
            new_callable=AsyncMock,
            return_value={"event_id": "evt-1"},
        ) as upsert_mock,
        patch("src.server.services.event_service.market_event_db.replace_event_articles", new_callable=AsyncMock),
        patch("src.server.services.event_service.market_event_db.replace_symbol_links", new_callable=AsyncMock),
    ):
        await svc._persist_clusters(clusters)  # noqa: SLF001

    payload = upsert_mock.await_args.args[0]
    assert payload["title"] == "Apple AI handset strategy expansion"
    assert payload["ai_takeaway"] == (
        "Apple kept releasing AI handset updates, and the market is watching "
        "the read-through for hardware demand and suppliers."
    )


@pytest.mark.asyncio
async def test_persist_clusters_does_not_cache_fallback_takeaway_when_generation_fails():
    svc = EventService.get_instance()
    now = datetime.now(timezone.utc)
    data = [
        _article("a1", "Apple launches new AI iPhone strategy", ["AAPL"], now),
        _article("a2", "Apple unveils AI strategy for iPhone lineup", ["AAPL"], now - timedelta(minutes=40)),
    ]
    clusters = svc._cluster_articles(data)  # noqa: SLF001

    generated = (
        None,
        "Apple launches new AI iPhone strategy",
        "fallback text that should not be cached",
        False,
    )

    with (
        patch.object(svc, "_generate_event_interpretation", new=AsyncMock(return_value=generated)),
        patch(
            "src.server.services.event_service.market_event_db.upsert_market_event",
            new_callable=AsyncMock,
            return_value={"event_id": "evt-1"},
        ) as upsert_mock,
        patch("src.server.services.event_service.market_event_db.replace_event_articles", new_callable=AsyncMock),
        patch("src.server.services.event_service.market_event_db.replace_symbol_links", new_callable=AsyncMock),
    ):
        await svc._persist_clusters(clusters)  # noqa: SLF001

    payload = upsert_mock.await_args.args[0]
    assert payload["title"] == "Apple launches new AI iPhone strategy"
    assert payload["ai_takeaway"] is None
