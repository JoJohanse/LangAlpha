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
        _article("a1", "Crude oil price surges on OPEC decision", ["CL"], now),
        _article("a2", "Crude oil price climbs as OPEC signals production cuts", ["CL"], now - timedelta(minutes=40)),
    ]

    clusters = svc._cluster_articles(data)  # noqa: SLF001 - unit-test private behavior
    assert len(clusters) == 1
    assert len(clusters[0].articles) == 2


def test_cluster_splits_different_events():
    svc = EventService.get_instance()
    now = datetime.now(timezone.utc)
    data = [
        _article("a1", "Crude oil price rises on supply concerns", ["CL"], now),
        _article("a2", "Gold futures fall as dollar strengthens", ["GC"], now - timedelta(minutes=10)),
    ]

    clusters = svc._cluster_articles(data)  # noqa: SLF001
    assert len(clusters) == 2


@pytest.mark.asyncio
async def test_persist_clusters_generates_title_and_takeaway_before_upsert():
    svc = EventService.get_instance()
    now = datetime.now(timezone.utc)
    data = [
        _article("a1", "Crude oil price surges on OPEC decision", ["CL"], now),
        _article("a2", "Crude oil price climbs as OPEC signals production cuts", ["CL"], now - timedelta(minutes=40)),
    ]
    clusters = svc._cluster_articles(data)  # noqa: SLF001

    mock_result = (
        "gpt-4o-mini",
        "Oil price surges on OPEC production cut decision",
        "OPEC's decision to cut production drove crude oil prices higher, with markets anticipating tighter supply ahead.",
        True,
    )

    with (
        patch(
            "src.server.services.event_service.EventService._generate_event_interpretation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
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
    assert payload["title"] == "Oil price surges on OPEC production cut decision"
    assert payload["ai_takeaway"] == (
        "OPEC's decision to cut production drove crude oil prices higher, with markets anticipating tighter supply ahead."
    )


@pytest.mark.asyncio
async def test_persist_clusters_does_not_cache_fallback_takeaway_when_generation_fails():
    svc = EventService.get_instance()
    now = datetime.now(timezone.utc)
    data = [
        _article("a1", "Crude oil price surges on OPEC decision", ["CL"], now),
        _article("a2", "Crude oil price climbs as OPEC signals production cuts", ["CL"], now - timedelta(minutes=40)),
    ]
    clusters = svc._cluster_articles(data)  # noqa: SLF001

    mock_result = (
        "gpt-4o-mini",
        "Crude oil price surges on OPEC decision",
        "fallback text that should not be cached",
        False,
    )

    with (
        patch(
            "src.server.services.event_service.EventService._generate_event_interpretation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
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
    assert payload["title"] == "Crude oil price surges on OPEC decision"
    assert payload["ai_takeaway"] is None
