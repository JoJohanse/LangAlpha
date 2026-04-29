"""News APIs: feed, hot rank, tag filters, ask, and interpretation."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.data_client import get_news_data_provider
from src.server.database import news_article_tags as tags_db
from src.server.models.events import InterpretRequest, InterpretResponse
from src.server.models.news import (
    NewsArticle,
    NewsArticleCompact,
    NewsAskRequest,
    NewsAskResponse,
    NewsCompactResponse,
    NewsDeleteRequest,
    NewsHotRankItem,
    NewsHotRankResponse,
    NewsPublisher,
)
from src.server.services.cache.news_cache_service import NewsCacheService
from src.server.services.news_enrichment_service import NewsEnrichmentService
from src.server.utils.api import CurrentUserId, handle_api_exceptions, raise_not_found

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["News"])

_cache = NewsCacheService()
_enrichment = NewsEnrichmentService()
_INVALID_DESC_RE = re.compile(r"^\d+$")


def _build_tag_map(tagged_articles: list[Any]) -> dict[str, dict[str, Any]]:
    return {a.article_id: a.as_dict() for a in tagged_articles}


def _effective_description(article: dict[str, Any]) -> str:
    title = str(article.get("title") or "").strip()
    description = str(article.get("description") or "").strip()
    if not description or _INVALID_DESC_RE.fullmatch(description):
        return title
    return description


def _article_from_snapshot(article_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    published_at = snapshot.get("published_at")
    if isinstance(published_at, datetime):
        published_at_str = published_at.astimezone(timezone.utc).isoformat()
    else:
        published_at_str = datetime.now(timezone.utc).isoformat()
    title = snapshot.get("title") or "Untitled"
    return {
        "id": article_id,
        "title": title,
        "author": None,
        "description": title,
        "published_at": published_at_str,
        "article_url": snapshot.get("article_url") or "",
        "image_url": None,
        "source": {
            "name": snapshot.get("source_name") or "Unknown",
            "logo_url": None,
            "homepage_url": None,
            "favicon_url": None,
        },
        "tickers": snapshot.get("tickers") or [],
        "keywords": snapshot.get("tags") or [],
        "sentiments": [],
    }


async def _persisted_tag_map_from_raw(raw_articles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    ids = [str(a.get("id") or "").strip() for a in raw_articles if str(a.get("id") or "").strip()]
    return await tags_db.list_article_tags_by_ids(ids)


def _compact(article: dict, tag_map: dict[str, dict[str, Any]] | None = None) -> NewsArticleCompact | None:
    title = article.get("title")
    if not title:
        return None
    sentiments = article.get("sentiments")
    article_id = article.get("id")
    source = article.get("source")
    if not article_id or not source:
        return None
    tags = (tag_map or {}).get(article_id, {})
    return NewsArticleCompact(
        id=article_id,
        title=title,
        published_at=article.get("published_at", ""),
        image_url=article.get("image_url"),
        article_url=article.get("article_url"),
        source=NewsPublisher(**source),
        tickers=article.get("tickers", []),
        has_sentiment=bool(sentiments and len(sentiments) > 0),
        sector=tags.get("sector"),
        topic=tags.get("topic"),
        region=tags.get("region"),
        tags=tags.get("tags") or [],
    )


async def _ensure_tags(raw_articles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    tagged = await _enrichment.build_and_store_tags(raw_articles)
    return _build_tag_map(tagged)


@router.get("", response_model=NewsCompactResponse)
async def get_news(
    user_id: CurrentUserId,
    tickers: str | None = Query(None, description="Comma-separated ticker symbols"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="Pagination cursor"),
    published_after: str | None = Query(None, description="ISO 8601 date filter"),
    published_before: str | None = Query(None, description="ISO 8601 date filter"),
    order: str | None = Query(None, description="Sort order: asc or desc"),
    sort: str | None = Query(None, description="Sort field, e.g. published_utc"),
    feed_mode: str = Query("standard", pattern="^(standard|quick)$"),
) -> NewsCompactResponse:
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] if tickers else None

    if not cursor:
        cached = await _cache.get(tickers=ticker_list, limit=limit)
        if cached:
            raw_results = cached.get("results") or []
            tag_map = await _ensure_tags(raw_results)
            persisted_tag_map = await _persisted_tag_map_from_raw(raw_results)
            merged_tag_map = {**tag_map, **persisted_tag_map}
            results = [
                c
                for a in raw_results
                if str(a.get("id") or "").strip() in persisted_tag_map
                and (c := _compact(a, tag_map=merged_tag_map)) is not None
            ]
            if feed_mode == "quick":
                results = sorted(results, key=lambda x: x.published_at, reverse=True)
            return NewsCompactResponse(results=results, count=len(results), next_cursor=cached.get("next_cursor"))

    provider = await get_news_data_provider()
    data = await provider.get_news(
        tickers=ticker_list,
        limit=limit,
        cursor=cursor,
        published_after=published_after,
        published_before=published_before,
        order=order,
        sort=sort,
        user_id=user_id,
    )

    if not cursor:
        await _cache.set(data, tickers=ticker_list, limit=limit)

    raw_results = data.get("results", []) if isinstance(data, dict) else []
    tag_map = await _ensure_tags(raw_results)
    persisted_tag_map = await _persisted_tag_map_from_raw(raw_results)
    merged_tag_map = {**tag_map, **persisted_tag_map}
    results = [
        c
        for a in raw_results
        if str(a.get("id") or "").strip() in persisted_tag_map
        and (c := _compact(a, tag_map=merged_tag_map)) is not None
    ]
    if feed_mode == "quick":
        results = sorted(results, key=lambda x: x.published_at, reverse=True)
    return NewsCompactResponse(results=results, count=len(results), next_cursor=data.get("next_cursor"))


@router.get("/hot-rank", response_model=NewsHotRankResponse)
async def get_news_hot_rank(
    user_id: CurrentUserId,
    limit: int = Query(20, ge=1, le=100),
    window_hours: int = Query(24, ge=1, le=168),
) -> NewsHotRankResponse:
    provider = await get_news_data_provider()
    after_dt = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    data = await provider.get_news(limit=max(50, limit * 2), published_after=after_dt.isoformat(), user_id=user_id)
    raw = data.get("results", []) if isinstance(data, dict) else []
    tagged = await _enrichment.build_and_store_tags(raw)
    persisted_tag_map = await _persisted_tag_map_from_raw(raw)
    tagged = [t for t in tagged if t.article_id in persisted_tag_map]
    ranked = _enrichment.build_hot_rank(tagged_articles=tagged, window_hours=window_hours, limit=limit)
    items = [
        NewsHotRankItem(
            article_id=r["article_id"],
            title=r["title"],
            article_url=r.get("article_url"),
            source_name=r.get("source_name"),
            published_at=r["published_at"].isoformat() if r.get("published_at") else None,
            tickers=r.get("tickers") or [],
            sector=r.get("sector") or "general",
            topic=r.get("topic") or "general",
            region=r.get("region") or "US",
            tags=r.get("tags") or [],
            importance_score=float(r.get("importance_score") or 0),
            recency_score=float(r.get("recency_score") or 0),
            source_count=int(r.get("source_count") or 0),
        )
        for r in ranked
    ]
    return NewsHotRankResponse(results=items, count=len(items), limit=limit)


@router.get("/by-sector/{sector}", response_model=NewsCompactResponse)
async def get_news_by_sector(
    sector: str,
    user_id: CurrentUserId,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> NewsCompactResponse:
    provider = await get_news_data_provider()
    rows = await tags_db.list_articles_by_sector(sector=sector, limit=limit, offset=offset)
    if not rows:
        data = await provider.get_news(limit=max(60, limit * 3), user_id=user_id)
        raw = data.get("results", []) if isinstance(data, dict) else []
        await _ensure_tags(raw)
        rows = await tags_db.list_articles_by_sector(sector=sector, limit=limit, offset=offset)
    results = [
        NewsArticleCompact(
            id=row["article_id"],
            title=row["title"],
            published_at=row["published_at"].isoformat() if row.get("published_at") else "",
            article_url=row.get("article_url"),
            source=NewsPublisher(name=row.get("source_name") or "Unknown"),
            tickers=row.get("tickers") or [],
            has_sentiment=False,
            sector=row.get("sector"),
            topic=row.get("topic"),
            region=row.get("region"),
            tags=row.get("tags") or [],
        )
        for row in rows
    ]
    return NewsCompactResponse(results=results, count=len(results), next_cursor=None)


@router.get("/by-topic/{topic}", response_model=NewsCompactResponse)
async def get_news_by_topic(
    topic: str,
    user_id: CurrentUserId,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> NewsCompactResponse:
    provider = await get_news_data_provider()
    rows = await tags_db.list_articles_by_topic(topic=topic, limit=limit, offset=offset)
    if not rows:
        data = await provider.get_news(limit=max(60, limit * 3), user_id=user_id)
        raw = data.get("results", []) if isinstance(data, dict) else []
        await _ensure_tags(raw)
        rows = await tags_db.list_articles_by_topic(topic=topic, limit=limit, offset=offset)
    results = [
        NewsArticleCompact(
            id=row["article_id"],
            title=row["title"],
            published_at=row["published_at"].isoformat() if row.get("published_at") else "",
            article_url=row.get("article_url"),
            source=NewsPublisher(name=row.get("source_name") or "Unknown"),
            tickers=row.get("tickers") or [],
            has_sentiment=False,
            sector=row.get("sector"),
            topic=row.get("topic"),
            region=row.get("region"),
            tags=row.get("tags") or [],
        )
        for row in rows
    ]
    return NewsCompactResponse(results=results, count=len(results), next_cursor=None)


@router.post("/{article_id}/ask", response_model=NewsAskResponse)
async def ask_about_news_article(
    article_id: str,
    payload: NewsAskRequest,
    user_id: CurrentUserId,
) -> NewsAskResponse:
    provider = await get_news_data_provider()
    article = await provider.get_news_article(article_id, user_id=user_id)
    if article is None:
        snapshot = await tags_db.get_article_tag(article_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Article not found")
        article = _article_from_snapshot(article_id, snapshot)
    ask = _enrichment.build_ask_payload(article, question=payload.question)
    return NewsAskResponse(article_id=article_id, **ask)


@router.get("/{article_id}", response_model=NewsArticle)
async def get_news_article(article_id: str, user_id: CurrentUserId):
    cached = await _cache.get_article_by_id(article_id)
    if cached:
        cached["description"] = _effective_description(cached)
        tag_row = await tags_db.get_article_tag(article_id)
        if tag_row:
            cached.setdefault("sector", tag_row.get("sector"))
            cached.setdefault("topic", tag_row.get("topic"))
            cached.setdefault("region", tag_row.get("region"))
            if not cached.get("tags"):
                cached["tags"] = tag_row.get("tags") or []
        return NewsArticle(**cached)

    provider = await get_news_data_provider()
    article = await provider.get_news_article(article_id, user_id=user_id)
    if article:
        article["description"] = _effective_description(article)
        tagged = _enrichment._tag_article(article)  # noqa: SLF001
        if tagged:
            await tags_db.upsert_news_article_tag(
                {
                    "article_id": tagged.article_id,
                    "title": tagged.title,
                    "article_url": tagged.article_url,
                    "source_name": tagged.source_name,
                    "published_at": tagged.published_at,
                    "tickers": tagged.tickers,
                    "sector": tagged.sector,
                    "topic": tagged.topic,
                    "region": tagged.region,
                    "tags": tagged.tags,
                }
            )
            article["sector"] = tagged.sector
            article["topic"] = tagged.topic
            article["region"] = tagged.region
            article["tags"] = tagged.tags or []
        return NewsArticle(**article)

    snapshot = await tags_db.get_article_tag(article_id)
    if snapshot:
        base = _article_from_snapshot(article_id, snapshot)
        base["sector"] = snapshot.get("sector")
        base["topic"] = snapshot.get("topic")
        base["region"] = snapshot.get("region")
        base["tags"] = snapshot.get("tags") or []
        return NewsArticle(**base)

    raise HTTPException(status_code=404, detail="Article not found")


@router.post("/{article_id}/interpret", response_model=InterpretResponse)
async def interpret_news_article(
    article_id: str, payload: InterpretRequest, user_id: CurrentUserId
):
    from src.server.services.event_service import EventService

    provider = await get_news_data_provider()
    article = await provider.get_news_article(article_id, user_id=user_id)
    if article is None:
        snapshot = await tags_db.get_article_tag(article_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Article not found")
        article = _article_from_snapshot(article_id, snapshot)

    service = EventService.get_instance()
    interpretation, model_name = await service.interpret_article(
        article=article, focus_symbol=payload.focus_symbol
    )
    return InterpretResponse(
        target_type="article",
        target_id=article_id,
        interpretation=interpretation,
        model=model_name,
        cached=False,
        generated_at=datetime.now(timezone.utc),
    )


@router.delete("/{article_id}", status_code=204)
@handle_api_exceptions("delete news article", logger)
async def delete_news_article(article_id: str, user_id: CurrentUserId):
    deleted = await tags_db.delete_news_article(article_id)
    if not deleted:
        raise_not_found("News article")
    return Response(status_code=204)


@router.delete("", status_code=204)
@handle_api_exceptions("delete news articles", logger)
async def delete_news_articles(payload: NewsDeleteRequest, user_id: CurrentUserId):
    await tags_db.delete_news_articles(payload.article_ids)
    return Response(status_code=204)
