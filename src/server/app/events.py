"""API routes for market events."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from src.server.database import market_event as market_event_db
from src.server.models.events import (
    EventArticle,
    EventDetail,
    EventListResponse,
    EventListItem,
    InterpretRequest,
    InterpretResponse,
)
from src.server.services.event_service import EventService
from src.server.utils.api import CurrentUserId

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


def _to_event_item(row: dict) -> EventListItem:
    return EventListItem(**row)


@router.get("", response_model=EventListResponse)
async def get_events(
    user_id: CurrentUserId,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> EventListResponse:
    rows = await market_event_db.list_events(limit=limit, offset=offset)
    total = await market_event_db.count_events()
    return EventListResponse(
        results=[_to_event_item(r) for r in rows],
        count=total,
        limit=limit,
        offset=offset,
    )


@router.get("/hot", response_model=EventListResponse)
async def get_hot_events(
    user_id: CurrentUserId,
    limit: int = Query(10, ge=1, le=100),
) -> EventListResponse:
    rows = await market_event_db.list_hot_events(limit=limit)
    return EventListResponse(
        results=[_to_event_item(r) for r in rows],
        count=len(rows),
        limit=limit,
        offset=0,
    )


@router.get("/{event_id}", response_model=EventDetail)
async def get_event_detail(event_id: str, user_id: CurrentUserId) -> EventDetail:
    row = await market_event_db.get_event(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    links = await market_event_db.list_event_article_links(event_id)
    related_articles: list[EventArticle] = []
    if links:
        from src.data_client import get_news_data_provider

        provider = await get_news_data_provider()
        for link in links[:20]:
            article = await provider.get_news_article(link["article_id"], user_id=user_id)
            related_articles.append(
                EventArticle(
                    article_id=link["article_id"],
                    relevance_score=link.get("relevance_score"),
                    is_primary=bool(link.get("is_primary", False)),
                    title=(article or {}).get("title"),
                    article_url=(article or {}).get("article_url"),
                    source_name=((article or {}).get("source") or {}).get("name"),
                    published_at=(article or {}).get("published_at"),
                )
            )
    return EventDetail(**row, related_articles=related_articles)


@router.get("/by-symbol/{symbol}", response_model=EventListResponse)
async def get_events_by_symbol(
    symbol: str,
    user_id: CurrentUserId,
    limit: int = Query(20, ge=1, le=100),
) -> EventListResponse:
    rows = await market_event_db.list_events_by_symbol(symbol=symbol, limit=limit)
    return EventListResponse(
        results=[_to_event_item(r) for r in rows],
        count=len(rows),
        limit=limit,
        offset=0,
    )


@router.post("/{event_id}/interpret", response_model=InterpretResponse)
async def interpret_event(
    event_id: str, payload: InterpretRequest, user_id: CurrentUserId
) -> InterpretResponse:
    service = EventService.get_instance()
    try:
        interpretation, model_name, cached = await service.interpret_event(
            event_id=event_id,
            focus_symbol=payload.focus_symbol,
            refresh=payload.refresh,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return InterpretResponse(
        target_type="event",
        target_id=event_id,
        interpretation=interpretation,
        model=model_name,
        cached=cached,
        generated_at=datetime.now(timezone.utc),
    )
