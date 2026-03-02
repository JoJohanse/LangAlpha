"""Pydantic response models for market insights."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class InsightTopic(BaseModel):
    text: str
    trend: str  # "up", "down", "neutral"


class MarketInsightLatestResponse(BaseModel):
    market_insight_id: str
    type: str
    headline: str
    summary: str
    topics: List[InsightTopic]
    model: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InsightNewsItem(BaseModel):
    title: str
    body: str
    url: Optional[str] = None


class MarketInsightListResponse(BaseModel):
    insights: List[MarketInsightLatestResponse]
    count: int


class MarketInsightDetailResponse(MarketInsightLatestResponse):
    content: Optional[List[InsightNewsItem]] = None
    sources: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
