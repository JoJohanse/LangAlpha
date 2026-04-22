from datetime import datetime, timedelta, timezone

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
