"""API routes for market events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.server.database import market_event as market_event_db
from src.server.models.events import (
    EventArticle,
    EventAskRequest,
    EventAskResponse,
    EventDeleteRequest,
    EventDetail,
    EventListResponse,
    EventListItem,
    InterpretRequest,
    InterpretResponse,
)
from src.server.services.event_service import EventService
from src.server.utils.api import CurrentUserId, handle_api_exceptions, raise_not_found

router = APIRouter(prefix="/api/v1/events", tags=["Events"])
logger = logging.getLogger(__name__)


def _to_event_item(row: dict) -> EventListItem:
    return EventListItem(**row)


def _build_event_ask_payload(
    event_row: dict,
    related_articles: list[dict],
    question: str | None = None,
    focus_symbol: str | None = None,
) -> dict:
    symbols = [str(s).upper() for s in (event_row.get("symbols") or []) if str(s).strip()]
    primary_symbol = str(event_row.get("primary_symbol") or "").strip().upper() or None
    summary = (
        str(event_row.get("ai_takeaway") or "").strip()
        or str(event_row.get("short_summary") or "").strip()
        or str(event_row.get("title") or "").strip()
    )
    article_context = []
    for article in related_articles[:5]:
        article_id = str(article.get("article_id") or "").strip()
        if not article_id:
            continue
        article_title = str(article.get("title") or "").strip() or article_id
        article_source = str(article.get("source_name") or "").strip()
        article_url = str(article.get("article_url") or "").strip()
        published_at = (
            article.get("published_at").isoformat()
            if getattr(article.get("published_at"), "isoformat", None)
            else article.get("published_at")
        )
        part = f"- {article_title}"
        if article_source:
            part += f" | source={article_source}"
        if published_at:
            part += f" | time={published_at}"
        if article_url:
            part += f" | url={article_url}"
        article_context.append(part)

    ask_message = (question or "").strip()
    if not ask_message:
        if focus_symbol:
            ask_message = f"Please analyze this market event and its impact on {focus_symbol.upper()}."
        elif primary_symbol:
            ask_message = f"Please analyze this market event and its impact on {primary_symbol}."
        else:
            ask_message = "Please analyze this market event and its broader market impact."

    directive_lines = [
        "Use the following event context when answering the user's question.",
        f"Event title: {event_row.get('title')}",
        f"Summary: {summary or event_row.get('title')}",
        f"Importance score: {event_row.get('importance_score') or 0}",
        f"Primary symbol: {primary_symbol or 'N/A'}",
        f"Symbols: {', '.join(symbols) if symbols else 'N/A'}",
    ]
    start_time = (
        event_row.get("start_time").isoformat()
        if getattr(event_row.get("start_time"), "isoformat", None)
        else event_row.get("start_time")
    )
    if start_time:
        directive_lines.append(f"Event time: {start_time}")
    tags = event_row.get("tags") or []
    if tags:
        directive_lines.append(f"Tags: {', '.join([str(t) for t in tags])}")
    if article_context:
        directive_lines.append("Related news:")
        directive_lines.extend(article_context)
    additional_context = [{"type": "directive", "content": "\n".join(directive_lines)}]
    return {
        "thread_initial_message": ask_message,
        "additional_context": additional_context,
        "fallback_message": ask_message,
    }


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
    related_articles = [
        EventArticle(
            article_id=str(link.get("article_id") or ""),
            relevance_score=link.get("relevance_score"),
            is_primary=bool(link.get("is_primary", False)),
            title=link.get("title"),
            article_url=link.get("article_url"),
            source_name=link.get("source_name"),
            published_at=link.get("published_at"),
        )
        for link in links[:20]
    ]
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


@router.post("/{event_id}/ask", response_model=EventAskResponse)
async def ask_about_event(
    event_id: str,
    payload: EventAskRequest,
    user_id: CurrentUserId,
) -> EventAskResponse:
    row = await market_event_db.get_event(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    related_articles = await market_event_db.list_event_article_links(event_id)
    ask = _build_event_ask_payload(
        row,
        related_articles=related_articles,
        question=payload.question,
        focus_symbol=payload.focus_symbol,
    )
    return EventAskResponse(event_id=event_id, **ask)


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


@router.delete("/{event_id}", status_code=204)
@handle_api_exceptions("delete event", logger)
async def delete_event(event_id: str, user_id: CurrentUserId):
    deleted = await market_event_db.delete_event(event_id)
    if not deleted:
        raise_not_found("Event")
    return Response(status_code=204)


@router.delete("", status_code=204)
@handle_api_exceptions("delete events", logger)
async def delete_events(payload: EventDeleteRequest, user_id: CurrentUserId):
    await market_event_db.delete_events(payload.event_ids)
    return Response(status_code=204)
