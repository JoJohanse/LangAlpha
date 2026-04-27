"""Background market-event aggregation and interpretation service."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from src.server.database import market_event as market_event_db

logger = logging.getLogger(__name__)

AGG_WINDOW_HOURS = 24
AGG_INTERVAL_SECONDS = 300
MAX_NEWS_FETCH = 300
TITLE_JACCARD_THRESHOLD = 0.55
TIME_DIFF_THRESHOLD = timedelta(hours=6)
INTERPRET_TIMEOUT_SECONDS = 45

_STOP_WORDS = {
    "the", "a", "an", "to", "for", "of", "and", "or", "in", "on", "with", "at",
    "by", "from", "is", "are", "was", "were", "be", "as", "its", "it", "this", "that",
}


def _safe_parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _title_tokens(title: str) -> set[str]:
    parts = re.findall(r"[a-zA-Z0-9]+", title.lower())
    return {p for p in parts if p not in _STOP_WORDS and len(p) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def _normalize_score(article_count: int, unique_source_count: int, has_sentiment: bool) -> float:
    article_part = min(article_count, 10) / 10 * 60
    source_part = min(unique_source_count, 5) / 5 * 30
    sentiment_part = 10 if has_sentiment else 0
    return round(min(100.0, article_part + source_part + sentiment_part), 2)


def _pick_sentiment(sentiments: list[str]) -> str:
    if not sentiments:
        return "neutral"
    c = Counter(sentiments)
    pos = c.get("positive", 0)
    neg = c.get("negative", 0)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _market_session(start_time: datetime | None) -> str:
    if start_time is None:
        return "closed"
    et = timezone(timedelta(hours=-5))
    hour = start_time.astimezone(et).hour
    if 4 <= hour < 9:
        return "pre_market"
    if 9 <= hour < 16:
        return "regular"
    if 16 <= hour < 20:
        return "post_market"
    return "closed"


def _stable_event_id(primary_symbol: str, start_time: datetime, signature_tokens: list[str]) -> str:
    bucket = int(start_time.timestamp() // int(TIME_DIFF_THRESHOLD.total_seconds()))
    sig = "-".join(signature_tokens[:8])
    raw = f"{primary_symbol}|{bucket}|{sig}"
    return str(uuid5(NAMESPACE_DNS, raw))


@dataclass
class _Cluster:
    articles: list[dict[str, Any]] = field(default_factory=list)
    tickers: set[str] = field(default_factory=set)
    title_tokens: set[str] = field(default_factory=set)
    first_time: datetime | None = None
    sentiments: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)


class EventService:
    _instance: "EventService | None" = None

    @classmethod
    def get_instance(cls) -> "EventService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._loop(), name="market_event_loop")
        logger.info("[MARKET_EVENTS] Service started")

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[MARKET_EVENTS] Service stopped")

    async def run_once(self) -> int:
        from src.data_client import get_news_data_provider

        provider = await get_news_data_provider()
        after_dt = datetime.now(timezone.utc) - timedelta(hours=AGG_WINDOW_HOURS)
        data = await provider.get_news(
            limit=MAX_NEWS_FETCH,
            published_after=after_dt.isoformat(),
        )
        raw_articles = data.get("results", []) if isinstance(data, dict) else []
        clusters = self._cluster_articles(raw_articles)
        await self._persist_clusters(clusters)
        return len(clusters)

    async def interpret_event(
        self, event_id: str, focus_symbol: str | None = None, refresh: bool = False
    ) -> tuple[str, str | None, bool]:
        event = await market_event_db.get_event(event_id)
        if not event:
            raise ValueError("Event not found")
        if event.get("ai_takeaway") and not refresh:
            return str(event["ai_takeaway"]), None, True

        model_name, interpretation = await self._generate_interpretation(
            target_type="event",
            payload={
                "title": event.get("title"),
                "summary": event.get("short_summary"),
                "symbols": event.get("symbols") or [],
                "sentiment": event.get("sentiment"),
                "importance_score": event.get("importance_score"),
                "focus_symbol": focus_symbol,
            },
        )
        await market_event_db.update_event_takeaway(event_id, interpretation)
        return interpretation, model_name, False

    async def interpret_article(
        self, article: dict[str, Any], focus_symbol: str | None = None
    ) -> tuple[str, str | None]:
        model_name, interpretation = await self._generate_interpretation(
            target_type="article",
            payload={
                "title": article.get("title"),
                "summary": article.get("description"),
                "symbols": article.get("tickers") or [],
                "source": (article.get("source") or {}).get("name"),
                "focus_symbol": focus_symbol,
                "published_at": article.get("published_at"),
            },
        )
        return interpretation, model_name

    async def _generate_interpretation(
        self, target_type: str, payload: dict[str, Any]
    ) -> tuple[str | None, str]:
        from src.llms import create_llm
        from src.llms.api_call import make_api_call
        from src.server.app import setup

        model_name = None
        try:
            if not setup.agent_config or not setup.agent_config.llm:
                raise RuntimeError("LLM not configured")
            model_name = setup.agent_config.llm.flash
            llm = create_llm(model_name)
            system_prompt = (
                "You are a financial market analyst. "
                "Provide concise factual interpretation and potential market impact in 3-5 sentences. "
                "No investment advice. Use plain text only. "
                "Respond in Chinese (Simplified Chinese, 中文)."
            )
            user_prompt = f"Target type: {target_type}\nPayload: {payload}"
            text = await asyncio.wait_for(
                make_api_call(
                    llm=llm,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=None,
                ),
                timeout=INTERPRET_TIMEOUT_SECONDS,
            )
            if isinstance(text, str) and text.strip():
                return model_name, text.strip()
        except Exception as e:
            logger.warning("[MARKET_EVENTS] interpret fallback triggered: %s", e)

        symbols = ", ".join(payload.get("symbols") or []) or "the related assets"
        summary = payload.get("summary") or payload.get("title") or "No summary available."
        fallback = (
            f"This {target_type} is linked to {symbols}. "
            f"Core information: {summary}. "
            "Focus on follow-up disclosures, price/volume confirmation, and whether related sector names move in the same direction."
        )
        return model_name, fallback

    async def _loop(self) -> None:
        # initial warm run
        try:
            count = await self.run_once()
            logger.info("[MARKET_EVENTS] Initial run complete: %s events", count)
        except Exception as e:
            logger.warning("[MARKET_EVENTS] Initial run failed: %s", e)

        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=AGG_INTERVAL_SECONDS
                )
                break
            except asyncio.TimeoutError:
                pass

            try:
                count = await self.run_once()
                logger.info("[MARKET_EVENTS] Aggregation run complete: %s events", count)
            except Exception as e:
                logger.error("[MARKET_EVENTS] Aggregation failed: %s", e, exc_info=True)

    def _cluster_articles(self, raw_articles: list[dict[str, Any]]) -> list[_Cluster]:
        articles: list[dict[str, Any]] = []
        for raw in raw_articles:
            title = str(raw.get("title") or "").strip()
            article_id = str(raw.get("id") or "").strip()
            if not title or not article_id:
                continue
            published_at = _safe_parse_dt(raw.get("published_at"))
            if published_at is None:
                continue
            tickers = {str(t).upper() for t in (raw.get("tickers") or []) if t}
            if not tickers:
                continue
            sentiments = []
            for s in (raw.get("sentiments") or []):
                sent = str((s or {}).get("sentiment") or "").lower()
                if sent in {"positive", "negative", "neutral"}:
                    sentiments.append(sent)
            source_name = str(((raw.get("source") or {}).get("name")) or "").strip()
            article_url = str(raw.get("article_url") or "").strip()
            articles.append(
                {
                    "id": article_id,
                    "title": title,
                    "article_url": article_url or None,
                    "published_at": published_at,
                    "tickers": sorted(tickers),
                    # Include ticker tokens in similarity signature so wording
                    # variants around the same symbol can still meet threshold.
                    "title_tokens": _title_tokens(title) | tickers,
                    "sentiments": sentiments,
                    "source_name": source_name,
                }
            )

        articles.sort(key=lambda x: x["published_at"], reverse=True)
        clusters: list[_Cluster] = []
        for article in articles:
            matched: _Cluster | None = None
            for cluster in clusters:
                if not (set(article["tickers"]) & cluster.tickers):
                    continue
                if cluster.first_time is None:
                    continue
                if abs(cluster.first_time - article["published_at"]) > TIME_DIFF_THRESHOLD:
                    continue
                if _jaccard(article["title_tokens"], cluster.title_tokens) < TITLE_JACCARD_THRESHOLD:
                    continue
                matched = cluster
                break

            if matched is None:
                matched = _Cluster(
                    articles=[],
                    tickers=set(),
                    title_tokens=set(article["title_tokens"]),
                    first_time=article["published_at"],
                    sentiments=[],
                    sources=set(),
                )
                clusters.append(matched)

            matched.articles.append(article)
            matched.tickers.update(article["tickers"])
            matched.title_tokens.update(article["title_tokens"])
            matched.sentiments.extend(article["sentiments"])
            if article["source_name"]:
                matched.sources.add(article["source_name"])
            if matched.first_time is None or article["published_at"] < matched.first_time:
                matched.first_time = article["published_at"]

        return clusters

    async def _persist_clusters(self, clusters: list[_Cluster]) -> None:
        for cluster in clusters:
            if not cluster.articles or not cluster.first_time:
                continue

            ticker_counter = Counter(
                t for article in cluster.articles for t in article["tickers"]
            )
            primary_symbol = (
                ticker_counter.most_common(1)[0][0] if ticker_counter else "UNKNOWN"
            )
            sorted_symbols = sorted(cluster.tickers)
            lead_article = cluster.articles[0]
            signature_tokens = sorted(cluster.title_tokens)
            event_id = _stable_event_id(
                primary_symbol=primary_symbol,
                start_time=cluster.first_time,
                signature_tokens=signature_tokens,
            )
            sentiment = _pick_sentiment(cluster.sentiments)
            importance = _normalize_score(
                article_count=len(cluster.articles),
                unique_source_count=len(cluster.sources),
                has_sentiment=bool(cluster.sentiments),
            )
            event_row = await market_event_db.upsert_market_event(
                {
                    "event_id": event_id,
                    "title": lead_article["title"],
                    "short_summary": self._build_cluster_summary(cluster),
                    "importance_score": importance,
                    "sentiment": sentiment,
                    "start_time": cluster.first_time,
                    "primary_symbol": primary_symbol,
                    "symbols": sorted_symbols,
                    "tags": signature_tokens[:12],
                    "article_count": len(cluster.articles),
                    "status": "active",
                }
            )

            event_articles = []
            for idx, article in enumerate(cluster.articles):
                event_articles.append(
                    {
                        "article_id": article["id"],
                        "relevance_score": round(max(0.0, 1.0 - (idx * 0.08)), 2),
                        "is_primary": idx == 0,
                        "title": article.get("title"),
                        "article_url": article.get("article_url"),
                        "source_name": article.get("source_name"),
                        "published_at": article.get("published_at"),
                    }
                )
            await market_event_db.replace_event_articles(
                event_row["event_id"], event_articles
            )

            direction = (
                "up" if sentiment == "positive" else "down" if sentiment == "negative" else "neutral"
            )
            symbol_links = [
                {
                    "symbol": symbol,
                    "event_time": cluster.first_time,
                    "impact_direction": direction,
                    "impact_score": importance,
                    "display_title": lead_article["title"],
                }
                for symbol in sorted_symbols
            ]
            await market_event_db.replace_symbol_links(
                event_row["event_id"], symbol_links
            )

    def _build_cluster_summary(self, cluster: _Cluster) -> str:
        if not cluster.articles:
            return ""
        if len(cluster.articles) == 1:
            return cluster.articles[0]["title"]
        titles = [a["title"] for a in cluster.articles[:3]]
        joined = "; ".join(titles)
        extra = max(0, len(cluster.articles) - 3)
        if extra:
            joined += f"; +{extra} related updates"
        return joined
