#!/usr/bin/env python3
"""Options Data MCP Server.

Provides options contracts, OHLCV price data, and real-time snapshots via MCP.

Design goals:
- Raw JSON output for programmatic analysis in sandbox
- Complements native get_options_chain tool (which returns pre-formatted markdown)
- ginlix-data only (no FMP fallback)

Tools:
- get_options_chain: list options contracts with filters
- get_options_prices: historical OHLCV bars for an options contract
- get_options_snapshot: real-time bid/ask, last trade, session data
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from mcp.server.fastmcp import FastMCP

from data_client.ginlix_data import (
    close_ginlix_mcp_client,
    get_ginlix_mcp_client,
)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_ginlix = get_ginlix_mcp_client()


@asynccontextmanager
async def _lifespan(app):
    try:
        yield
    finally:
        await close_ginlix_mcp_client()


# ---------------------------------------------------------------------------
# MCP server + tools
# ---------------------------------------------------------------------------

mcp = FastMCP("OptionsMCP", lifespan=_lifespan)


@mcp.tool()
async def get_options_chain(
    underlying_ticker: str,
    contract_type: Optional[str] = None,
    expiration_date_gte: Optional[str] = None,
    expiration_date_lte: Optional[str] = None,
    strike_price_gte: Optional[float] = None,
    strike_price_lte: Optional[float] = None,
    limit: int = 50,
) -> dict:
    """List options contracts for an underlying ticker with full metadata.

    Use cases:
    - Discover all available call/put contracts for a stock
    - Filter contracts by expiration range and strike range
    - Get full contract metadata for options strategy construction

    Args:
        underlying_ticker: Underlying stock ticker (e.g., AAPL, TSLA, MSFT)
        contract_type: "call" or "put" (default: both)
        expiration_date_gte: Minimum expiration date YYYY-MM-DD
        expiration_date_lte: Maximum expiration date YYYY-MM-DD
        strike_price_gte: Minimum strike price
        strike_price_lte: Maximum strike price
        limit: Max contracts to return (default 50, max 1000)

    Returns:
        dict with underlying_ticker, count, data (list of contract dicts), source.
        Each contract: ticker, underlying_ticker, contract_type, exercise_style,
        expiration_date, strike_price, shares_per_contract, primary_exchange.
    """
    result = await _ginlix.fetch_options_chain(
        underlying_ticker,
        contract_type=contract_type,
        expiration_date_gte=expiration_date_gte,
        expiration_date_lte=expiration_date_lte,
        strike_price_gte=strike_price_gte,
        strike_price_lte=strike_price_lte,
        limit=limit,
    )
    if "error" in result:
        return result
    results = result.get("results", [])
    return {
        "underlying_ticker": underlying_ticker,
        "count": len(results),
        "data": results,
        "source": "ginlix-data",
    }


@mcp.tool()
async def get_options_prices(
    options_ticker: str,
    from_date: str,
    to_date: str,
    interval: str = "1day",
) -> dict:
    """Get historical OHLCV bars for a specific options contract.

    Use cases:
    - Chart option price movements over time
    - Analyze intraday option trading patterns
    - Build options pricing models and backtest strategies

    Args:
        options_ticker: Options contract ticker (e.g., O:AAPL260618C00220000)
        from_date: Start date YYYY-MM-DD (required)
        to_date: End date YYYY-MM-DD (required)
        interval: 1day/daily, 1min, 5min, 15min, 30min, 1hour, 4hour

    Returns:
        dict with symbol, interval, count, rows (normalized OHLCV), source.
        rows: date, open, high, low, close, volume (descending by date).
    """
    result = await _ginlix.fetch_options_prices(
        options_ticker,
        from_date=from_date,
        to_date=to_date,
        interval=interval,
    )
    if isinstance(result, dict):
        return result  # error dict
    return {
        "symbol": options_ticker,
        "interval": interval.lower(),
        "count": len(result),
        "rows": result,
        "source": "ginlix-data",
    }


@mcp.tool()
async def get_options_snapshot(
    options_tickers: str,
) -> dict:
    """Get real-time snapshot data for options contracts.

    Includes session OHLCV, bid/ask quotes, and last trade info. Session data
    is always available; bid/ask and last trade populate during market hours.

    Use cases:
    - Get current bid/ask spreads for options pricing
    - Check real-time session data (close, change%, volume)
    - Assess liquidity across multiple contracts for strategy selection

    Args:
        options_tickers: One or more options tickers, comma-separated
            (e.g., "O:AAPL260618C00220000" or "O:AAPL260618C00220000,O:AAPL260618C00230000")

    Returns:
        dict with count, data (list of snapshot dicts), source.
        Each snapshot: ticker, name, market_status, session (OHLCV + change),
        last_quote (bid/ask/midpoint), last_trade (price/size).
    """
    tickers = [t.strip() for t in options_tickers.split(",") if t.strip()]
    if not tickers:
        return {"error": "No tickers provided."}
    return await _ginlix.fetch_options_snapshot(tickers)


if __name__ == "__main__":
    mcp.run()
