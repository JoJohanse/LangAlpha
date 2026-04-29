"""Pydantic models for the news API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NewsPublisher(BaseModel):
    name: str
    logo_url: str | None = None
    homepage_url: str | None = None
    favicon_url: str | None = None


class NewsSentiment(BaseModel):
    ticker: str
    sentiment: str | None = None
    reasoning: str | None = None


class NewsArticle(BaseModel):
    id: str
    title: str
    author: str | None = None
    description: str | None = None
    published_at: str  # ISO 8601
    article_url: str
    image_url: str | None = None
    source: NewsPublisher
    tickers: list[str] = []
    keywords: list[str] = []
    sentiments: list[NewsSentiment] | None = None
    sector: str | None = None
    topic: str | None = None
    region: str | None = None
    tags: list[str] = []


class NewsResponse(BaseModel):
    results: list[NewsArticle]
    count: int
    next_cursor: str | None = None


class NewsArticleCompact(BaseModel):
    id: str
    title: str
    published_at: str
    image_url: str | None = None
    article_url: str | None = None
    source: NewsPublisher
    tickers: list[str] = []
    has_sentiment: bool = False
    sector: str | None = None
    topic: str | None = None
    region: str | None = None
    tags: list[str] = []


class NewsCompactResponse(BaseModel):
    results: list[NewsArticleCompact]
    count: int
    next_cursor: str | None = None


class NewsTag(BaseModel):
    article_id: str
    sector: str = "general"
    topic: str = "general"
    region: str = "US"
    tags: list[str] = []


class NewsHotRankItem(BaseModel):
    article_id: str
    title: str
    article_url: str | None = None
    source_name: str | None = None
    published_at: str | None = None
    tickers: list[str] = []
    sector: str = "general"
    topic: str = "general"
    region: str = "US"
    tags: list[str] = []
    importance_score: float = 0
    recency_score: float = 0
    source_count: int = 0


class NewsHotRankResponse(BaseModel):
    results: list[NewsHotRankItem]
    count: int
    limit: int


class NewsDeleteRequest(BaseModel):
    article_ids: list[str] = Field(min_length=1, max_length=200)


class NewsAskRequest(BaseModel):
    question: str | None = None
    focus_symbol: str | None = None


class NewsAskResponse(BaseModel):
    article_id: str
    thread_initial_message: str
    fallback_message: str
    additional_context: list[dict]
