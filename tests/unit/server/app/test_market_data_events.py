from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.conftest import create_test_app


@pytest_asyncio.fixture
async def client():
    from src.server.app.market_data import router

    app = create_test_app(router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_get_stock_event_markers(client):
    rows = [
        {
            "event_id": "evt-1",
            "symbol": "AAPL",
            "event_time": datetime.now(timezone.utc),
            "impact_direction": "up",
            "impact_score": 82.5,
            "display_title": "Apple event",
        }
    ]
    with patch(
        "src.server.app.market_data.market_event_db.get_symbol_event_markers",
        new_callable=AsyncMock,
        return_value=rows,
    ):
        resp = await client.get("/api/v1/market-data/stocks/AAPL/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["count"] == 1
    assert body["markers"][0]["event_id"] == "evt-1"
