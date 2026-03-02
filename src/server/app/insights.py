"""API routes for AI market insights."""

import logging

from fastapi import APIRouter

from src.server.database import market_insight as market_insight_db
from src.server.models.market_insight import (
    MarketInsightDetailResponse,
    MarketInsightListResponse,
)
from src.server.utils.api import (
    CurrentUserId,
    handle_api_exceptions,
    raise_not_found,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Insights"])


@router.get("/insights/today", response_model=MarketInsightListResponse)
@handle_api_exceptions("get today's insights", logger)
async def get_todays_insights(user_id: CurrentUserId):
    rows = await market_insight_db.get_todays_market_insights()
    return {"insights": rows, "count": len(rows)}


@router.get(
    "/insights/{market_insight_id}",
    response_model=MarketInsightDetailResponse,
)
@handle_api_exceptions("get insight detail", logger)
async def get_insight_detail(market_insight_id: str, user_id: CurrentUserId):
    row = await market_insight_db.get_market_insight(market_insight_id)
    if not row:
        raise_not_found("Market Insight")
    return row
