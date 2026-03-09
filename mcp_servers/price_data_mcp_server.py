#!/usr/bin/env python3
"""Price Data MCP Server.

Provides normalized OHLCV time series data and short sale analytics via MCP.

Design goals:
- Small, stable tool surface (high PTC value)
- Normalized JSON output (schema stable across providers)
- Can run in sandbox (stdio) for OSS/dev
- Can be deployed externally (http/sse) for production

Tools:
- get_stock_data: stock OHLCV
- get_asset_data: stock/commodity/crypto/forex OHLCV
- get_short_data: short interest (bi-monthly) and short volume (daily)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any, Literal, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from data_client.fmp import get_fmp_client, close_fmp_client


# ---------------------------------------------------------------------------
# Ginlix-data client (optional — for short data)
# ---------------------------------------------------------------------------

_ginlix_http: httpx.AsyncClient | None = None


@asynccontextmanager
async def _lifespan(app):
    global _ginlix_http
    ginlix_url = os.getenv("GINLIX_DATA_URL", "")
    if ginlix_url:
        headers: dict[str, str] = {}
        token = os.getenv("INTERNAL_SERVICE_TOKEN", "")
        if token:
            headers["X-Service-Token"] = token
        _ginlix_http = httpx.AsyncClient(
            base_url=ginlix_url.rstrip("/"),
            headers=headers,
            timeout=30.0,
        )
    try:
        yield
    finally:
        if _ginlix_http:
            await _ginlix_http.aclose()
            _ginlix_http = None
        await close_fmp_client()


mcp = FastMCP("PriceDataMCP", lifespan=_lifespan)


_INTRADAY_INTERVALS_STOCK = {"1min", "5min", "15min", "30min", "1hour", "4hour"}
_INTRADAY_INTERVALS_ASSET = {"1min", "5min", "1hour"}
_DAILY_INTERVALS = {"daily", "1day"}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_date(value: Any) -> str:
    """Return an ISO string usable for sorting and display."""

    if value is None:
        return ""

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    text = str(value)
    # FMP sometimes returns "YYYY-MM-DD" or full ISO datetime.
    return text


def _normalize_ohlcv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for row in rows:
        normalized_row = {
            "date": _normalize_date(row.get("date")),
            "open": _as_float(row.get("open")),
            "high": _as_float(row.get("high")),
            "low": _as_float(row.get("low")),
            "close": _as_float(row.get("close")),
            "volume": _as_float(row.get("volume")),
        }
        normalized.append(normalized_row)

    # Descending (newest first). ISO strings are sortable lexicographically.
    normalized.sort(key=lambda r: r.get("date") or "", reverse=True)
    return normalized


def _default_dates_for_intraday(from_date: str | None, to_date: str | None) -> tuple[str, str]:
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=7)
    return (
        from_date or start_dt.strftime("%Y-%m-%d"),
        to_date or end_dt.strftime("%Y-%m-%d"),
    )


@mcp.tool()
async def get_stock_data(
    symbol: str,
    interval: str = "1day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Get normalized OHLCV for a stock symbol.

    Args:
        symbol: Stock ticker (e.g., AAPL, MSFT, 600519.SS, 0700.HK)
        interval: "1day"/"daily" or intraday: 1min/5min/15min/30min/1hour/4hour
        start_date: YYYY-MM-DD (optional)
        end_date: YYYY-MM-DD (optional)

    Returns:
        dict: {
          "symbol": str,
          "interval": str,
          "count": int,
          "rows": list[dict],
          "source": "fmp"
        }
        rows are normalized: date/open/high/low/close/volume (descending by date).
    """

    interval_lower = interval.lower()

    try:
        client = await get_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}"}

    try:
        if interval_lower in _DAILY_INTERVALS:
            rows = await client.get_stock_price(symbol, from_date=start_date, to_date=end_date)
        else:
            if interval_lower not in _INTRADAY_INTERVALS_STOCK:
                return {
                    "error": "Unsupported interval for stock",
                    "supported": sorted(_DAILY_INTERVALS | _INTRADAY_INTERVALS_STOCK),
                }

            intraday_start, intraday_end = _default_dates_for_intraday(start_date, end_date)
            rows = await client.get_intraday_chart(
                symbol,
                interval_lower,
                from_date=intraday_start,
                to_date=intraday_end,
            )
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

    normalized = _normalize_ohlcv_rows(rows or [])
    return {
        "symbol": symbol,
        "interval": interval_lower,
        "count": len(normalized),
        "rows": normalized,
        "source": "fmp",
    }


@mcp.tool()
async def get_asset_data(
    symbol: str,
    asset_type: str,
    interval: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    """Get normalized OHLCV for stock/commodity/crypto/forex.

    Args:
        symbol: Asset symbol (e.g., GCUSD, BTCUSD, EURUSD, AAPL)
        asset_type: one of stock/commodity/crypto/forex
        interval: daily/1day or intraday
          - stock: 1min/5min/15min/30min/1hour/4hour
          - commodity/crypto/forex: 1min/5min/1hour
        from_date: YYYY-MM-DD (optional)
        to_date: YYYY-MM-DD (optional)

    Returns:
        dict with symbol, asset_type, interval, count, rows (descending), source.
    """

    at = asset_type.lower().strip()
    interval_lower = interval.lower()

    if at not in {"stock", "commodity", "crypto", "forex"}:
        return {"error": "Invalid asset_type", "supported": ["stock", "commodity", "crypto", "forex"]}

    try:
        client = await get_fmp_client()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Failed to initialize FMP client: {e}"}

    try:
        if at == "stock":
            if interval_lower in _DAILY_INTERVALS:
                rows = await client.get_stock_price(symbol, from_date=from_date, to_date=to_date)
            else:
                if interval_lower not in _INTRADAY_INTERVALS_STOCK:
                    return {
                        "error": "Unsupported interval for stock",
                        "supported": sorted(_DAILY_INTERVALS | _INTRADAY_INTERVALS_STOCK),
                    }

                intraday_start, intraday_end = _default_dates_for_intraday(from_date, to_date)
                rows = await client.get_intraday_chart(
                    symbol,
                    interval_lower,
                    from_date=intraday_start,
                    to_date=intraday_end,
                )

        else:
            if interval_lower in _DAILY_INTERVALS:
                if at == "commodity":
                    rows = await client.get_commodity_price(symbol, from_date=from_date, to_date=to_date)
                elif at == "crypto":
                    rows = await client.get_crypto_price(symbol, from_date=from_date, to_date=to_date)
                else:
                    rows = await client.get_forex_price(symbol, from_date=from_date, to_date=to_date)

            else:
                if interval_lower not in _INTRADAY_INTERVALS_ASSET:
                    return {
                        "error": "Unsupported interval for commodity/crypto/forex",
                        "supported": sorted(_DAILY_INTERVALS | _INTRADAY_INTERVALS_ASSET),
                    }

                intraday_start, intraday_end = _default_dates_for_intraday(from_date, to_date)
                if at == "commodity":
                    rows = await client.get_commodity_intraday_chart(
                        symbol,
                        interval_lower,
                        from_date=intraday_start,
                        to_date=intraday_end,
                    )
                elif at == "crypto":
                    rows = await client.get_crypto_intraday_chart(
                        symbol,
                        interval_lower,
                        from_date=intraday_start,
                        to_date=intraday_end,
                    )
                else:
                    rows = await client.get_forex_intraday_chart(
                        symbol,
                        interval_lower,
                        from_date=intraday_start,
                        to_date=intraday_end,
                    )

    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

    normalized = _normalize_ohlcv_rows(rows or [])
    return {
        "symbol": symbol,
        "asset_type": at,
        "interval": interval_lower,
        "count": len(normalized),
        "rows": normalized,
        "source": "fmp",
    }


@mcp.tool()
async def get_short_data(
    symbol: str,
    data_type: Literal["short_interest", "short_volume", "both"] = "both",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Get short interest and/or short volume data for a stock.

    Short interest is reported bi-monthly by FINRA (settlement_date).
    Short volume is reported daily from off-exchange venues (date).

    Args:
        symbol: Stock ticker (e.g., AAPL, GME, AMC)
        data_type: "short_interest", "short_volume", or "both" (default)
        from_date: YYYY-MM-DD start date filter (optional)
        to_date: YYYY-MM-DD end date filter (optional)
        limit: Max records per type (default 20, max 50000)

    Returns:
        dict with short_interest and/or short_volume arrays (newest first).
        short_interest fields: ticker, settlement_date, short_interest, avg_daily_volume, days_to_cover
        short_volume fields: ticker, date, short_volume, total_volume, short_volume_ratio, exempt_volume, non_exempt_volume
    """
    if _ginlix_http is None:
        return {"error": "Short data requires ginlix-data. Set GINLIX_DATA_URL to enable."}

    result: dict[str, Any] = {"symbol": symbol, "source": "ginlix-data"}

    if data_type in ("short_interest", "both"):
        params: dict[str, Any] = {
            "ticker": symbol, "limit": limit, "sort": "settlement_date.desc",
        }
        if from_date:
            params["settlement_date.gte"] = from_date
        if to_date:
            params["settlement_date.lte"] = to_date
        try:
            resp = await _ginlix_http.get(
                "/api/v1/data/stocks/short-interest", params=params,
            )
            resp.raise_for_status()
            body = resp.json()
            result["short_interest"] = body.get("results", [])
        except Exception as e:  # noqa: BLE001
            result["short_interest_error"] = str(e)

    if data_type in ("short_volume", "both"):
        params = {
            "ticker": symbol, "limit": limit, "sort": "date.desc",
        }
        if from_date:
            params["date.gte"] = from_date
        if to_date:
            params["date.lte"] = to_date
        try:
            resp = await _ginlix_http.get(
                "/api/v1/data/stocks/short-volume", params=params,
            )
            resp.raise_for_status()
            body = resp.json()
            result["short_volume"] = body.get("results", [])
        except Exception as e:  # noqa: BLE001
            result["short_volume_error"] = str(e)

    return result


if __name__ == "__main__":
    mcp.run()
