"""Database operations for news tag snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json

from src.server.database.conversation import get_db_connection


async def upsert_news_article_tag(snapshot: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO news_article_tags (
                    article_id, title, article_url, source_name, published_at,
                    tickers, sector, topic, region, tags, created_at, updated_at
                ) VALUES (
                    %(article_id)s, %(title)s, %(article_url)s, %(source_name)s, %(published_at)s,
                    %(tickers)s, %(sector)s, %(topic)s, %(region)s, %(tags)s, %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (article_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    article_url = EXCLUDED.article_url,
                    source_name = EXCLUDED.source_name,
                    published_at = EXCLUDED.published_at,
                    tickers = EXCLUDED.tickers,
                    sector = EXCLUDED.sector,
                    topic = EXCLUDED.topic,
                    region = EXCLUDED.region,
                    tags = EXCLUDED.tags,
                    updated_at = EXCLUDED.updated_at
                """,
                {
                    **snapshot,
                    "tickers": Json(snapshot.get("tickers") or []),
                    "tags": Json(snapshot.get("tags") or []),
                    "created_at": snapshot.get("created_at") or now,
                    "updated_at": now,
                },
            )


async def get_article_tag(article_id: str) -> dict[str, Any] | None:
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    article_id,
                    title,
                    article_url,
                    source_name,
                    published_at,
                    tickers,
                    sector,
                    topic,
                    region,
                    tags,
                    created_at,
                    updated_at
                FROM news_article_tags
                WHERE article_id = %s
                """,
                (article_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None


async def list_article_tags_by_ids(article_ids: list[str]) -> dict[str, dict[str, Any]]:
    ids = [str(i).strip() for i in article_ids if str(i).strip()]
    if not ids:
        return {}
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    article_id,
                    title,
                    article_url,
                    source_name,
                    published_at,
                    tickers,
                    sector,
                    topic,
                    region,
                    tags,
                    created_at,
                    updated_at
                FROM news_article_tags
                WHERE article_id = ANY(%s)
                """,
                (ids,),
            )
            rows = await cur.fetchall()
            return {str(row["article_id"]): dict(row) for row in rows}


async def list_articles_by_sector(
    sector: str, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    article_id,
                    title,
                    article_url,
                    source_name,
                    published_at,
                    tickers,
                    sector,
                    topic,
                    region,
                    tags
                FROM news_article_tags
                WHERE LOWER(COALESCE(sector, '')) = LOWER(%s)
                ORDER BY published_at DESC NULLS LAST, updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (sector, limit, offset),
            )
            return [dict(row) for row in await cur.fetchall()]


async def list_articles_by_topic(
    topic: str, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    async with get_db_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    article_id,
                    title,
                    article_url,
                    source_name,
                    published_at,
                    tickers,
                    sector,
                    topic,
                    region,
                    tags
                FROM news_article_tags
                WHERE LOWER(COALESCE(topic, '')) = LOWER(%s)
                ORDER BY published_at DESC NULLS LAST, updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (topic, limit, offset),
            )
            return [dict(row) for row in await cur.fetchall()]
