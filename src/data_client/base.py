"""Abstract data source protocols.

All OHLCV data sources (FMP, ginlix-data) implement :class:`MarketDataSource`
so that cache services and routes are backend-agnostic.

News sources implement :class:`NewsDataSource` for the news feed layer.
"""

from __future__ import annotations

from typing import Any, Protocol


class MarketDataSource(Protocol):
    """Unified interface for OHLCV price data fetching."""

    async def get_intraday(
        self,
        symbol: str,
        interval: str,
        from_date: str | None = None,
        to_date: str | None = None,
        is_index: bool = False,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return intraday OHLCV bars.

        Each dict has: ``{date, open, high, low, close, volume}``.
        *user_id* is forwarded to the upstream service for access-control.
        """
        ...

    async def get_daily(
        self,
        symbol: str,
        from_date: str | None = None,
        to_date: str | None = None,
        is_index: bool = False,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return daily OHLCV bars.

        Each dict has: ``{date, open, high, low, close, volume}``.
        *user_id* is forwarded to the upstream service for access-control.
        """
        ...

    async def close(self) -> None:
        """Release resources held by the data source."""
        ...


class NewsDataSource(Protocol):
    """Unified interface for news article fetching."""

    async def get_news(
        self,
        tickers: list[str] | None = None,
        limit: int = 20,
        published_after: str | None = None,
        published_before: str | None = None,
        cursor: str | None = None,
        order: str | None = None,
        sort: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Return ``{results: list[dict], count: int, next_cursor: str|None}``."""
        ...

    async def get_news_article(
        self, article_id: str, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Return a single article by ID, or ``None`` if not found."""
        ...

    async def close(self) -> None:
        """Release resources held by the data source."""
        ...


# Backward-compatible alias
PriceDataProvider = MarketDataSource
