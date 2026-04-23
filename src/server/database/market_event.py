"""Database operations for market events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.server.database.conversation import get_db_connection


EVENT_COLUMNS = (
    "event_id::text, title, short_summary, importance_score, sentiment, start_time, "
    "primary_symbol, symbols, tags, article_count, ai_takeaway, status, created_at, updated_at"
)


async def upsert_market_event(event: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"""
                INSERT INTO market_events (
                    event_id, title, short_summary, importance_score, sentiment, start_time,
                    primary_symbol, symbols, tags, article_count, ai_takeaway, status, created_at, updated_at
                ) VALUES (
                    %(event_id)s, %(title)s, %(short_summary)s, %(importance_score)s, %(sentiment)s, %(start_time)s,
                    %(primary_symbol)s, %(symbols)s, %(tags)s, %(article_count)s, %(ai_takeaway)s, %(status)s, %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (event_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    short_summary = EXCLUDED.short_summary,
                    importance_score = EXCLUDED.importance_score,
                    sentiment = EXCLUDED.sentiment,
                    start_time = EXCLUDED.start_time,
                    primary_symbol = EXCLUDED.primary_symbol,
                    symbols = EXCLUDED.symbols,
                    tags = EXCLUDED.tags,
                    article_count = EXCLUDED.article_count,
                    ai_takeaway = COALESCE(EXCLUDED.ai_takeaway, market_events.ai_takeaway),
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                RETURNING {EVENT_COLUMNS}
                """,
                {
                    **event,
                    "symbols": Json(event.get("symbols") or []),
                    "tags": Json(event.get("tags") or []),
                    "ai_takeaway": event.get("ai_takeaway"),
                    "created_at": event.get("created_at") or now,
                    "updated_at": now,
                    "status": event.get("status") or "active",
                },
            )
            row = await cur.fetchone()
            return dict(row)


async def replace_event_articles(
    event_id: str, articles: list[dict[str, Any]]
) -> None:
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM market_event_articles WHERE event_id = %s",
                (event_id,),
            )
            for article in articles:
                try:
                    await cur.execute(
                        """
                        INSERT INTO market_event_articles (
                            event_id, article_id, relevance_score, is_primary,
                            title, article_url, source_name, published_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (event_id, article_id)
                        DO UPDATE SET
                            relevance_score = EXCLUDED.relevance_score,
                            is_primary = EXCLUDED.is_primary,
                            title = EXCLUDED.title,
                            article_url = EXCLUDED.article_url,
                            source_name = EXCLUDED.source_name,
                            published_at = EXCLUDED.published_at
                        """,
                        (
                            event_id,
                            article["article_id"],
                            article.get("relevance_score"),
                            bool(article.get("is_primary", False)),
                            article.get("title"),
                            article.get("article_url"),
                            article.get("source_name"),
                            article.get("published_at"),
                        ),
                    )
                except Exception as exc:
                    # Backward compatibility for DBs not yet migrated to revision 011.
                    if getattr(exc, "sqlstate", None) != "42703":
                        raise
                    await cur.execute(
                        """
                        INSERT INTO market_event_articles (
                            event_id, article_id, relevance_score, is_primary
                        ) VALUES (%s, %s, %s, %s)
                        ON CONFLICT (event_id, article_id)
                        DO UPDATE SET
                            relevance_score = EXCLUDED.relevance_score,
                            is_primary = EXCLUDED.is_primary
                        """,
                        (
                            event_id,
                            article["article_id"],
                            article.get("relevance_score"),
                            bool(article.get("is_primary", False)),
                        ),
                    )


async def replace_symbol_links(
    event_id: str, links: list[dict[str, Any]]
) -> None:
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM symbol_event_links WHERE event_id = %s",
                (event_id,),
            )
            for link in links:
                await cur.execute(
                    """
                    INSERT INTO symbol_event_links (
                        event_id, symbol, event_time, impact_direction, impact_score, display_title
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id, symbol)
                    DO UPDATE SET
                        event_time = EXCLUDED.event_time,
                        impact_direction = EXCLUDED.impact_direction,
                        impact_score = EXCLUDED.impact_score,
                        display_title = EXCLUDED.display_title
                    """,
                    (
                        event_id,
                        link["symbol"],
                        link["event_time"],
                        link.get("impact_direction"),
                        link.get("impact_score"),
                        link.get("display_title"),
                    ),
                )


async def list_events(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"""
                SELECT {EVENT_COLUMNS}
                FROM market_events
                WHERE status = 'active'
                ORDER BY start_time DESC NULLS LAST, updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            return [dict(row) for row in await cur.fetchall()]


async def count_events() -> int:
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM market_events WHERE status = 'active'"
            )
            row = await cur.fetchone()
            return int(row[0] if row else 0)


async def list_hot_events(limit: int = 10) -> list[dict[str, Any]]:
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"""
                SELECT {EVENT_COLUMNS}
                FROM market_events
                WHERE status = 'active'
                ORDER BY importance_score DESC, start_time DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in await cur.fetchall()]


async def get_event(event_id: str) -> dict[str, Any] | None:
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"""
                SELECT {EVENT_COLUMNS}
                FROM market_events
                WHERE event_id = %s
                """,
                (event_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None


async def list_event_article_links(event_id: str) -> list[dict[str, Any]]:
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            try:
                await cur.execute(
                    """
                    SELECT
                        article_id,
                        relevance_score,
                        is_primary,
                        title,
                        article_url,
                        source_name,
                        published_at
                    FROM market_event_articles
                    WHERE event_id = %s
                    ORDER BY is_primary DESC, relevance_score DESC NULLS LAST, created_at DESC
                    """,
                    (event_id,),
                )
            except Exception as exc:
                # Backward compatibility for DBs not yet migrated to revision 011.
                if getattr(exc, "sqlstate", None) != "42703":
                    raise
                await cur.execute(
                    """
                    SELECT
                        article_id,
                        relevance_score,
                        is_primary,
                        NULL::TEXT AS title,
                        NULL::TEXT AS article_url,
                        NULL::VARCHAR(255) AS source_name,
                        NULL::TIMESTAMPTZ AS published_at
                    FROM market_event_articles
                    WHERE event_id = %s
                    ORDER BY is_primary DESC, relevance_score DESC NULLS LAST, created_at DESC
                    """,
                    (event_id,),
                )
            return [dict(row) for row in await cur.fetchall()]


async def list_events_by_symbol(symbol: str, limit: int = 20) -> list[dict[str, Any]]:
    sym = symbol.upper()
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT DISTINCT
                    e.event_id::text, e.title, e.short_summary, e.importance_score, e.sentiment, e.start_time,
                    e.primary_symbol, e.symbols, e.tags, e.article_count, e.ai_takeaway, e.status, e.created_at, e.updated_at
                FROM market_events e
                JOIN symbol_event_links l ON l.event_id = e.event_id
                WHERE e.status = 'active' AND l.symbol = %s
                ORDER BY e.start_time DESC NULLS LAST, e.updated_at DESC
                LIMIT %s
                """,
                (sym, limit),
            )
            return [dict(row) for row in await cur.fetchall()]


async def get_symbol_event_markers(
    symbol: str,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    sym = symbol.upper()
    conditions = ["l.symbol = %s"]
    params: list[Any] = [sym]
    if from_ts is not None:
        conditions.append("l.event_time >= %s")
        params.append(from_ts)
    if to_ts is not None:
        conditions.append("l.event_time <= %s")
        params.append(to_ts)
    params.append(limit)

    where_clause = " AND ".join(conditions)

    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"""
                SELECT
                    l.event_id::text AS event_id,
                    l.symbol,
                    l.event_time,
                    l.impact_direction,
                    l.impact_score,
                    COALESCE(l.display_title, e.title) AS display_title
                FROM symbol_event_links l
                JOIN market_events e ON e.event_id = l.event_id
                WHERE {where_clause}
                ORDER BY l.event_time DESC
                LIMIT %s
                """,
                params,
            )
            return [dict(row) for row in await cur.fetchall()]


async def update_event_takeaway(event_id: str, ai_takeaway: str) -> bool:
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE market_events
                SET ai_takeaway = %s, updated_at = NOW()
                WHERE event_id = %s
                """,
                (ai_takeaway, event_id),
            )
            return cur.rowcount > 0
