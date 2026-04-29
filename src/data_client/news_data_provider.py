"""Composite news data provider with parallel racing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import NewsDataSource

logger = logging.getLogger(__name__)


class NewsDataProvider:
    """Races all news sources in parallel, returning the first successful result.

    Sources are launched concurrently.  The first one to return successfully
    wins — slow or hanging sources never block fast ones.  When multiple
    sources complete at the same time, priority order (as given in config)
    is used as the tiebreaker.
    """

    def __init__(self, sources: list[tuple[str, NewsDataSource]]) -> None:
        self._sources = sources

    async def get_news(self, **kwargs: Any) -> dict[str, Any]:
        if not self._sources:
            raise RuntimeError("No news sources configured")

        tasks: list[asyncio.Task[dict[str, Any]]] = [
            asyncio.create_task(source.get_news(**kwargs))
            for _, source in self._sources
        ]

        try:
            last_exc: Exception | None = None
            pending = tasks[:]

            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                # Check done tasks in priority order (tasks list is source order)
                for idx, task in enumerate(tasks):
                    if task not in done:
                        continue
                    try:
                        return task.result()
                    except Exception as exc:
                        name = self._sources[idx][0]
                        logger.warning("news.fallback | source=%s err=%s", name, exc)
                        last_exc = exc

            raise last_exc  # type: ignore[misc]
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def get_news_article(
        self, article_id: str, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Race all sources in parallel; return first non-None article."""
        if not self._sources:
            return None

        async def _try_article(name: str, source: NewsDataSource):
            try:
                result = await source.get_news_article(article_id, user_id=user_id)
                if result is not None:
                    return result
            except Exception as exc:
                logger.warning("news.article_fallback | source=%s err=%s", name, exc)
            return None

        tasks = [
            asyncio.create_task(_try_article(name, source))
            for name, source in self._sources
        ]

        try:
            pending = tasks[:]
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for idx, task in enumerate(tasks):
                    if task not in done:
                        continue
                    result = task.result()
                    if result is not None:
                        return result

            return None
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def close(self) -> None:
        for name, source in self._sources:
            try:
                await source.close()
            except Exception:
                logger.warning("news.close | source=%s failed", name, exc_info=True)

    @property
    def source_names(self) -> list[str]:
        return [name for name, _ in self._sources]
