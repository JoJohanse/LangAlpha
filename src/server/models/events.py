"""Pydantic models for event APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventListItem(BaseModel):
    event_id: str
    title: str
    short_summary: str | None = None
    importance_score: float = 0
    sentiment: str | None = None
    start_time: datetime | None = None
    primary_symbol: str | None = None
    symbols: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    article_count: int = 0
    ai_takeaway: str | None = None


class EventListResponse(BaseModel):
    results: list[EventListItem]
    count: int
    limit: int
    offset: int


class EventArticle(BaseModel):
    article_id: str
    relevance_score: float | None = None
    is_primary: bool = False
    title: str | None = None
    article_url: str | None = None
    source_name: str | None = None
    published_at: datetime | None = None


class EventDetail(EventListItem):
    related_articles: list[EventArticle] = Field(default_factory=list)


class EventMarker(BaseModel):
    event_id: str
    symbol: str
    event_time: datetime
    impact_direction: str | None = None
    impact_score: float | None = None
    display_title: str | None = None


class EventMarkerResponse(BaseModel):
    symbol: str
    markers: list[EventMarker]
    count: int


class InterpretRequest(BaseModel):
    focus_symbol: str | None = Field(default=None, description="Optional symbol focus")
    refresh: bool = Field(default=False, description="Force regenerate interpretation")


class InterpretResponse(BaseModel):
    target_type: str
    target_id: str
    interpretation: str
    model: str | None = None
    cached: bool = False
    generated_at: datetime
