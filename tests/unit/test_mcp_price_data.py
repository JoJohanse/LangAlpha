"""Tests for price_data_mcp_server: get_stock_data, get_asset_data, get_short_data."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_MOD = "mcp_servers.price_data_mcp_server"

# ---------------------------------------------------------------------------
# Canned data
# ---------------------------------------------------------------------------

_OHLCV_ROWS = [
    {"date": "2025-01-02", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
    {"date": "2025-01-03", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1200},
]

_SHORT_INTEREST = {
    "results": [
        {"ticker": "AAPL", "settlement_date": "2025-03-14", "short_interest": 133_000_000,
         "avg_daily_volume": 59_000_000, "days_to_cover": 2.25},
    ],
    "status": "OK",
}

_SHORT_VOLUME = {
    "results": [
        {"ticker": "AAPL", "date": "2025-03-25", "short_volume": 181_219,
         "total_volume": 574_084, "short_volume_ratio": 31.57},
    ],
    "status": "OK",
}


def _make_fmp_client(**overrides) -> MagicMock:
    client = AsyncMock()
    client.get_stock_price = AsyncMock(return_value=overrides.get("stock_price", _OHLCV_ROWS))
    client.get_intraday_chart = AsyncMock(return_value=overrides.get("intraday", _OHLCV_ROWS))
    client.get_commodity_price = AsyncMock(return_value=overrides.get("commodity", _OHLCV_ROWS))
    client.get_crypto_price = AsyncMock(return_value=overrides.get("crypto", _OHLCV_ROWS))
    client.get_forex_price = AsyncMock(return_value=overrides.get("forex", _OHLCV_ROWS))
    client.get_commodity_intraday_chart = AsyncMock(return_value=overrides.get("commodity_intra", _OHLCV_ROWS))
    client.get_crypto_intraday_chart = AsyncMock(return_value=overrides.get("crypto_intra", _OHLCV_ROWS))
    client.get_forex_intraday_chart = AsyncMock(return_value=overrides.get("forex_intra", _OHLCV_ROWS))
    return client


# ---------------------------------------------------------------------------
# get_stock_data
# ---------------------------------------------------------------------------

class TestGetStockData:
    @pytest.mark.asyncio
    async def test_daily(self):
        from mcp_servers.price_data_mcp_server import get_stock_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_stock_data("AAPL", interval="1day")

        assert result["symbol"] == "AAPL"
        assert result["interval"] == "1day"
        assert result["count"] == 2
        assert result["source"] == "fmp"
        # Rows should be descending
        assert result["rows"][0]["date"] >= result["rows"][1]["date"]
        client.get_stock_price.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_intraday(self):
        from mcp_servers.price_data_mcp_server import get_stock_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_stock_data("AAPL", interval="5min")

        assert result["interval"] == "5min"
        client.get_intraday_chart.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unsupported_interval(self):
        from mcp_servers.price_data_mcp_server import get_stock_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_stock_data("AAPL", interval="2min")

        assert "error" in result
        assert "supported" in result

    @pytest.mark.asyncio
    async def test_fmp_init_error(self):
        from mcp_servers.price_data_mcp_server import get_stock_data

        with patch(f"{_MOD}.get_fmp_client", side_effect=RuntimeError("no key")):
            result = await get_stock_data("AAPL")

        assert "error" in result
        assert "FMP" in result["error"]

    @pytest.mark.asyncio
    async def test_api_error(self):
        from mcp_servers.price_data_mcp_server import get_stock_data

        client = _make_fmp_client()
        client.get_stock_price = AsyncMock(side_effect=Exception("timeout"))
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_stock_data("AAPL")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_rows(self):
        from mcp_servers.price_data_mcp_server import get_stock_data

        client = _make_fmp_client(stock_price=[])
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_stock_data("AAPL")

        assert result["count"] == 0
        assert result["rows"] == []

    @pytest.mark.asyncio
    async def test_ohlcv_normalization(self):
        from mcp_servers.price_data_mcp_server import get_stock_data

        raw = [{"date": "2025-01-01", "open": "10", "high": None, "low": 9, "close": 10, "volume": 100}]
        client = _make_fmp_client(stock_price=raw)
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_stock_data("AAPL")

        row = result["rows"][0]
        assert row["open"] == 10.0  # string → float
        assert row["high"] is None  # None preserved
        assert row["date"] == "2025-01-01"


# ---------------------------------------------------------------------------
# get_asset_data
# ---------------------------------------------------------------------------

class TestGetAssetData:
    @pytest.mark.asyncio
    async def test_commodity_daily(self):
        from mcp_servers.price_data_mcp_server import get_asset_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_asset_data("GCUSD", asset_type="commodity")

        assert result["asset_type"] == "commodity"
        assert result["count"] == 2
        client.get_commodity_price.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_crypto_intraday(self):
        from mcp_servers.price_data_mcp_server import get_asset_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_asset_data("BTCUSD", asset_type="crypto", interval="5min")

        assert result["interval"] == "5min"
        client.get_crypto_intraday_chart.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_forex_daily(self):
        from mcp_servers.price_data_mcp_server import get_asset_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_asset_data("EURUSD", asset_type="forex")

        client.get_forex_price.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_asset_type(self):
        from mcp_servers.price_data_mcp_server import get_asset_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_asset_data("X", asset_type="bond")

        assert "error" in result
        assert "supported" in result

    @pytest.mark.asyncio
    async def test_unsupported_intraday_for_commodity(self):
        from mcp_servers.price_data_mcp_server import get_asset_data

        client = _make_fmp_client()
        with patch(f"{_MOD}.get_fmp_client", return_value=client):
            result = await get_asset_data("GCUSD", asset_type="commodity", interval="30min")

        assert "error" in result


# ---------------------------------------------------------------------------
# get_short_data
# ---------------------------------------------------------------------------

class TestGetShortData:
    @pytest.mark.asyncio
    async def test_no_ginlix_client(self):
        """When GINLIX_DATA_URL is not set, should return an error."""
        import mcp_servers.price_data_mcp_server as mod

        original = mod._ginlix_http
        mod._ginlix_http = None
        try:
            result = await mod.get_short_data("AAPL")
            assert "error" in result
            assert "ginlix-data" in result["error"]
        finally:
            mod._ginlix_http = original

    @pytest.mark.asyncio
    async def test_both_data_types(self):
        """Default data_type='both' should fetch SI and SV."""
        import mcp_servers.price_data_mcp_server as mod

        mock_http = AsyncMock()
        si_resp = MagicMock()
        si_resp.json.return_value = _SHORT_INTEREST
        si_resp.raise_for_status = MagicMock()
        sv_resp = MagicMock()
        sv_resp.json.return_value = _SHORT_VOLUME
        sv_resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(side_effect=[si_resp, sv_resp])

        original = mod._ginlix_http
        mod._ginlix_http = mock_http
        try:
            result = await mod.get_short_data("AAPL")
        finally:
            mod._ginlix_http = original

        assert result["symbol"] == "AAPL"
        assert result["source"] == "ginlix-data"
        assert len(result["short_interest"]) == 1
        assert result["short_interest"][0]["short_interest"] == 133_000_000
        assert len(result["short_volume"]) == 1
        assert result["short_volume"][0]["short_volume_ratio"] == 31.57

    @pytest.mark.asyncio
    async def test_short_interest_only(self):
        import mcp_servers.price_data_mcp_server as mod

        mock_http = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = _SHORT_INTEREST
        resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=resp)

        original = mod._ginlix_http
        mod._ginlix_http = mock_http
        try:
            result = await mod.get_short_data("AAPL", data_type="short_interest")
        finally:
            mod._ginlix_http = original

        assert "short_interest" in result
        assert "short_volume" not in result
        # Verify correct API path
        call_args = mock_http.get.call_args
        assert "short-interest" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_short_volume_only(self):
        import mcp_servers.price_data_mcp_server as mod

        mock_http = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = _SHORT_VOLUME
        resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=resp)

        original = mod._ginlix_http
        mod._ginlix_http = mock_http
        try:
            result = await mod.get_short_data("AAPL", data_type="short_volume")
        finally:
            mod._ginlix_http = original

        assert "short_volume" in result
        assert "short_interest" not in result

    @pytest.mark.asyncio
    async def test_date_filters(self):
        """from_date/to_date should be passed as query params."""
        import mcp_servers.price_data_mcp_server as mod

        mock_http = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = _SHORT_INTEREST
        resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=resp)

        original = mod._ginlix_http
        mod._ginlix_http = mock_http
        try:
            await mod.get_short_data(
                "AAPL", data_type="short_interest",
                from_date="2025-01-01", to_date="2025-03-31",
            )
        finally:
            mod._ginlix_http = original

        call_kwargs = mock_http.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["settlement_date.gte"] == "2025-01-01"
        assert params["settlement_date.lte"] == "2025-03-31"
        assert params["sort"] == "settlement_date.desc"

    @pytest.mark.asyncio
    async def test_api_error_captured(self):
        """HTTP errors should be captured in *_error keys, not raise."""
        import mcp_servers.price_data_mcp_server as mod

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock(),
        ))

        original = mod._ginlix_http
        mod._ginlix_http = mock_http
        try:
            result = await mod.get_short_data("AAPL")
        finally:
            mod._ginlix_http = original

        assert "short_interest_error" in result or "short_volume_error" in result

    @pytest.mark.asyncio
    async def test_custom_limit(self):
        import mcp_servers.price_data_mcp_server as mod

        mock_http = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = {"results": []}
        resp.raise_for_status = MagicMock()
        mock_http.get = AsyncMock(return_value=resp)

        original = mod._ginlix_http
        mod._ginlix_http = mock_http
        try:
            await mod.get_short_data("GME", data_type="short_interest", limit=100)
        finally:
            mod._ginlix_http = original

        call_kwargs = mock_http.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["limit"] == 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_normalize_ohlcv_descending(self):
        from mcp_servers.price_data_mcp_server import _normalize_ohlcv_rows

        rows = [
            {"date": "2025-01-01", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
            {"date": "2025-01-03", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 200},
        ]
        result = _normalize_ohlcv_rows(rows)
        assert result[0]["date"] == "2025-01-03"
        assert result[1]["date"] == "2025-01-01"

    def test_normalize_date_handles_none(self):
        from mcp_servers.price_data_mcp_server import _normalize_date

        assert _normalize_date(None) == ""
        assert _normalize_date("2025-01-01") == "2025-01-01"

    def test_as_float_handles_edge_cases(self):
        from mcp_servers.price_data_mcp_server import _as_float

        assert _as_float(None) is None
        assert _as_float("10.5") == 10.5
        assert _as_float("not_a_number") is None
        assert _as_float(42) == 42.0
