"""NewsDataSource implementation for local Pobo proxy service."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://host.docker.internal:5000"
_DETAIL_FETCH_LIMIT = 300
_DESC_MAX_LEN = 240
_POBO_SOURCE_TZ = ZoneInfo("Asia/Shanghai")

_INFOTYPE_NAME_TO_TICKERS: dict[str, list[str]] = {
    "金融财经": ["PB_MACRO"],
    "新闻快讯": ["PB_FLASH"],
    "能源化工": ["PB_ENERGY"],
    "农产品": ["PB_AGRI"],
    "金属市场": ["PB_METAL"],
    "黑色金属": ["PB_METAL_BLACK"],
    "稀贵金属": ["PB_METAL_PRECIOUS"],
    "股指期货": ["PB_INDEX_FUT"],
}

_INFOTYPE_CODE_TO_TICKERS: dict[str, list[str]] = {
    "020": ["PB_FLASH"],
    "021": ["PB_MACRO"],
    "031": ["PB_METAL_PRECIOUS"],
    "032": ["PB_METAL"],
    "033": ["PB_AGRI"],
    "034": ["PB_ENERGY"],
    "035": ["PB_METAL_BLACK"],
    "037": ["PB_INDEX_FUT"],
}

_TAG_RE = re.compile(r"<[^>]+>")
_INVALID_DESC_RE = re.compile(r"^\d+$")


def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _parse_dt_to_iso(value: Any) -> str:
    raw = _safe_text(value)
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return datetime.now(timezone.utc).isoformat()

    if dt.tzinfo is None:
        # Pobo CreateTime is local China time when tz info is omitted.
        dt = dt.replace(tzinfo=_POBO_SOURCE_TZ)
    return dt.astimezone(timezone.utc).isoformat()


def _strip_html(html: Any) -> str:
    text = _TAG_RE.sub(" ", _safe_text(html))
    return re.sub(r"\s+", " ", text).strip()


def _description(row: dict[str, Any]) -> str:
    title = _safe_text(row.get("InfoTitle"))
    summary = _safe_text(row.get("Summary"))
    if summary and not _INVALID_DESC_RE.fullmatch(summary):
        return summary[:_DESC_MAX_LEN]
    body = _strip_html(row.get("InfoBody"))
    if body and not _INVALID_DESC_RE.fullmatch(body):
        return body[:_DESC_MAX_LEN]
    return title[:_DESC_MAX_LEN]


def _extract_infotype_name(row: dict[str, Any]) -> str:
    return _safe_text(row.get("InfoTypeName") or row.get("InfotypeName"))


def _map_tickers(row: dict[str, Any]) -> list[str]:
    info_type_name = _extract_infotype_name(row)
    if info_type_name and info_type_name in _INFOTYPE_NAME_TO_TICKERS:
        return _INFOTYPE_NAME_TO_TICKERS[info_type_name]
    code = _safe_text(row.get("InfoType"))
    return _INFOTYPE_CODE_TO_TICKERS.get(code, [])


def _normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    info_id = row.get("InfoID")
    title = _safe_text(row.get("InfoTitle"))
    if info_id is None or not title:
        return None
    article_id = f"pobo-{info_id}"
    return {
        "id": article_id,
        "title": title,
        "author": None,
        "description": _description(row),
        "published_at": _parse_dt_to_iso(row.get("CreateTime")),
        "article_url": _safe_text(row.get("URL")),
        "image_url": None,
        "source": {
            "name": _safe_text(row.get("Source")) or "上海澎博",
            "logo_url": None,
            "homepage_url": None,
            "favicon_url": None,
        },
        "tickers": _map_tickers(row),
        "keywords": [],
        "sentiments": [],
    }


def _pobo_id_to_info_id(article_id: str) -> str | None:
    if not article_id.startswith("pobo-"):
        return None
    raw = article_id.removeprefix("pobo-").strip()
    return raw if raw else None


class PoboProxyNewsSource:
    """Fetches news from local Pobo forwarding service."""

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

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
        # Local proxy currently doesn't support ticker/cursor/order/sort filters.
        if any(v is not None for v in (tickers, cursor, order, sort, user_id)):
            logger.debug(
                "pobo_proxy.news: ignoring unsupported params",
                extra={"tickers": tickers, "cursor": cursor, "order": order, "sort": sort},
            )

        params: dict[str, Any] = {"limit": limit}
        if published_after:
            params["start_time"] = published_after
        if published_before:
            params["end_time"] = published_before

        resp = await self._client.get("/news", params=params)
        resp.raise_for_status()
        body = resp.json()
        payload = body if isinstance(body, dict) else {}
        raw_items = payload.get("items", [])

        results: list[dict[str, Any]] = []
        for row in raw_items:
            if not isinstance(row, dict):
                continue
            normalized = _normalize_row(row)
            if normalized:
                results.append(normalized)
        return {"results": results, "count": len(results), "next_cursor": None}

    async def get_news_article(
        self, article_id: str, user_id: str | None = None
    ) -> dict[str, Any] | None:
        info_id = _pobo_id_to_info_id(article_id)
        if not info_id:
            return None

        # Try dedicated single-article endpoint first (avoids fetching hundreds of items).
        try:
            resp = await self._client.get(f"/news/{info_id}")
            resp.raise_for_status()
            body = resp.json()
            if isinstance(body, dict) and body.get("InfoID") is not None:
                return _normalize_row(body)
        except Exception:
            pass  # endpoint not supported or article not found — fall back to list scan

        resp = await self._client.get("/news", params={"limit": _DETAIL_FETCH_LIMIT})
        resp.raise_for_status()
        body = resp.json()
        payload = body if isinstance(body, dict) else {}
        for row in payload.get("items", []):
            if not isinstance(row, dict):
                continue
            if str(row.get("InfoID")) != info_id:
                continue
            return _normalize_row(row)
        return None

    async def close(self) -> None:
        await self._client.aclose()
