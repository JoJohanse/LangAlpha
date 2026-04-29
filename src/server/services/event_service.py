"""Background market-event aggregation and interpretation service."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from pydantic import BaseModel, Field

from src.server.database import market_event as market_event_db

logger = logging.getLogger(__name__)

AGG_WINDOW_HOURS = 24
AGG_INTERVAL_SECONDS = 600
MAX_NEWS_FETCH = 100
TITLE_JACCARD_THRESHOLD = 0.55
TIME_DIFF_THRESHOLD = timedelta(hours=6)
INTERPRET_TIMEOUT_SECONDS = 45
EVENT_PREGENERATE_TIMEOUT_SECONDS = 60
CONTEXT_JACCARD_THRESHOLD = 0.18
TITLE_COVERAGE_THRESHOLD = 0.6
CLUSTER_SIMILARITY_THRESHOLD = 0.52
CONTEXT_TEXT_MAX_CHARS = 800
EVENT_GENERATION_MAX_CONCURRENCY = 3

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


def _text_tokens(text: str, max_chars: int | None = None) -> set[str]:
    if max_chars is not None:
        text = text[:max_chars]
    parts = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {p for p in parts if p not in _STOP_WORDS and len(p) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def _coverage(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


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
    context_tokens: set[str] = field(default_factory=set)
    first_time: datetime | None = None
    sentiments: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)


class _EventInterpretationOutput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    takeaway: str = Field(min_length=1, max_length=1200)


_EVENT_JSON_GUIDELINES = """
You MUST respond with ONLY a valid JSON object.
Do not include markdown, code fences, commentary, or extra text.
The JSON schema is:
{
  "title": "简体中文事件标题，概括相关新闻共同主题，最多120字",
  "takeaway": "简体中文事件总结，3-5句，基于已提供新闻内容，避免投资建议"
}
"""


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

        related_articles = await market_event_db.list_event_article_links(event_id)

        model_name, generated_title, interpretation, _ = await self._generate_event_interpretation(
            payload={
                "title": event.get("title"),
                "summary": event.get("short_summary"),
                "symbols": event.get("symbols") or [],
                "sentiment": event.get("sentiment"),
                "importance_score": event.get("importance_score"),
                "focus_symbol": focus_symbol,
                "related_articles": [
                    {
                        "title": article.get("title"),
                        "source_name": article.get("source_name"),
                        "published_at": (
                            article.get("published_at").isoformat()
                            if getattr(article.get("published_at"), "isoformat", None)
                            else article.get("published_at")
                        ),
                    }
                    for article in related_articles[:6]
                ],
            },
        )
        await market_event_db.update_event_takeaway(
            event_id,
            ai_takeaway=interpretation,
            title=generated_title,
        )
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

    async def _generate_event_interpretation(
        self, payload: dict[str, Any]
    ) -> tuple[str | None, str, str, bool]:
        from src.llms import create_llm
        from src.llms.api_call import make_api_call
        from src.server.app import setup

        model_name = None
        fallback_title = str(payload.get("title") or "").strip() or "市场事件"
        fallback_summary = str(payload.get("summary") or "").strip() or fallback_title
        fallback_takeaway = (
            f"该事件与 {', '.join(payload.get('symbols') or []) or '相关资产'} 相关。"
            f"核心信息：{fallback_summary}。"
            "请结合后续新闻进展、价格变化和成交量确认影响是否持续。"
        )

        try:
            if not setup.agent_config or not setup.agent_config.llm:
                raise RuntimeError("LLM not configured")
            model_name = setup.agent_config.llm.flash
            llm = create_llm(model_name)
            system_prompt = (
                "You are a financial market analyst. "
                "Read the related news context and produce a single representative event title plus a concise factual interpretation. "
                "The title must summarize the common event behind the related news rather than copying one article headline verbatim when a broader synthesis is possible. "
                "Avoid investment advice and speculation. "
                "All output must be in Simplified Chinese."
            )
            user_prompt = (
                "Generate a representative market-event title and takeaway from this payload.\n"
                f"{_EVENT_JSON_GUIDELINES}\n"
                f"Payload: {payload}"
            )
            response = await asyncio.wait_for(
                make_api_call(
                    llm=llm,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=_EventInterpretationOutput,
                    max_parsing_retries=2,
                ),
                timeout=INTERPRET_TIMEOUT_SECONDS,
            )
            title = str(response.title).strip()
            takeaway = str(response.takeaway).strip()
            if title and takeaway:
                return model_name, title, takeaway, True
        except Exception as e:
            logger.warning("[MARKET_EVENTS] event interpret fallback triggered: %s", e)

        return model_name, fallback_title, fallback_takeaway, False

    async def _generate_interpretation(
        self, target_type: str, payload: dict[str, Any]
    ) -> tuple[str | None, str]:
        from src.llms import create_llm
        from src.llms.api_call import make_api_call
        from src.llms.content_utils import format_llm_content
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
            response = await asyncio.wait_for(
                make_api_call(
                    llm=llm,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=None,
                ),
                timeout=INTERPRET_TIMEOUT_SECONDS,
            )
            # make_api_call returns raw content which may be a string or a list of
            # content blocks (when the provider uses Responses API). Normalize via
            # format_llm_content to always get a plain-text string.
            text = format_llm_content(response).get("text", "").strip()
            if text:
                return model_name, text
        except Exception as e:
            logger.warning("[MARKET_EVENTS] interpret fallback triggered: %s", e)

        symbols = ", ".join(payload.get("symbols") or []) or "相关资产"
        summary = payload.get("summary") or payload.get("title") or "暂无摘要信息。"
        type_cn = "事件" if target_type == "event" else "资讯"
        fallback = (
            f"该{type_cn}与 {symbols} 相关。"
            f"核心信息：{summary}。"
            "请关注后续披露、价格与成交量确认，以及相关板块是否同向波动。"
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
            context_text = self._build_context_text(raw)
            title_tokens = _title_tokens(title) | tickers
            context_tokens = _text_tokens(context_text, max_chars=CONTEXT_TEXT_MAX_CHARS) | tickers
            articles.append(
                {
                    "id": article_id,
                    "title": title,
                    "context_text": context_text or None,
                    "article_url": article_url or None,
                    "published_at": published_at,
                    "tickers": sorted(tickers),
                    # Include ticker tokens in similarity signatures so wording
                    # variants around the same symbol can still be linked.
                    "title_tokens": title_tokens,
                    "context_tokens": context_tokens,
                    "sentiments": sentiments,
                    "source_name": source_name,
                }
            )

        articles.sort(key=lambda x: x["published_at"], reverse=True)
        clusters: list[_Cluster] = []
        for article in articles:
            matched: _Cluster | None = None
            best_score = 0.0
            for cluster in clusters:
                if not (set(article["tickers"]) & cluster.tickers):
                    continue
                if cluster.first_time is None:
                    continue
                if abs(cluster.first_time - article["published_at"]) > TIME_DIFF_THRESHOLD:
                    continue
                similarity = self._cluster_similarity(article, cluster)
                if similarity < CLUSTER_SIMILARITY_THRESHOLD:
                    continue
                if similarity > best_score:
                    matched = cluster
                    best_score = similarity

            if matched is None:
                matched = _Cluster(
                    articles=[],
                    tickers=set(),
                    title_tokens=set(article["title_tokens"]),
                    context_tokens=set(article["context_tokens"]),
                    first_time=article["published_at"],
                    sentiments=[],
                    sources=set(),
                )
                clusters.append(matched)

            matched.articles.append(article)
            matched.tickers.update(article["tickers"])
            matched.title_tokens.update(article["title_tokens"])
            matched.context_tokens.update(article["context_tokens"])
            matched.sentiments.extend(article["sentiments"])
            if article["source_name"]:
                matched.sources.add(article["source_name"])
            if matched.first_time is None or article["published_at"] < matched.first_time:
                matched.first_time = article["published_at"]

        return clusters

    def _build_context_text(self, raw_article: dict[str, Any]) -> str:
        parts: list[str] = []
        for key in ("description", "summary", "content", "body", "text"):
            value = str(raw_article.get(key) or "").strip()
            if value and value not in parts:
                parts.append(value)
        return "\n".join(parts)[:CONTEXT_TEXT_MAX_CHARS]

    def _cluster_similarity(self, article: dict[str, Any], cluster: _Cluster) -> float:
        title_similarity = _jaccard(article["title_tokens"], cluster.title_tokens)
        context_similarity = _jaccard(article["context_tokens"], cluster.context_tokens)
        title_coverage = _coverage(article["title_tokens"], cluster.title_tokens)
        context_coverage = _coverage(article["context_tokens"], cluster.context_tokens)

        if (
            title_similarity < (TITLE_JACCARD_THRESHOLD * 0.45)
            and title_coverage < TITLE_COVERAGE_THRESHOLD
        ):
            return 0.0
        if context_similarity < CONTEXT_JACCARD_THRESHOLD and context_coverage < 0.35:
            return 0.0

        return round(
            (title_similarity * 0.5)
            + (title_coverage * 0.3)
            + (context_similarity * 0.15)
            + (context_coverage * 0.05),
            4,
        )

    async def _persist_clusters(self, clusters: list[_Cluster]) -> None:
        valid_clusters = [
            cluster for cluster in clusters if cluster.articles and cluster.first_time
        ]
        if not valid_clusters:
            return

        generated_event_content = await self._generate_cluster_contents(valid_clusters)

        for cluster, generated in zip(valid_clusters, generated_event_content, strict=False):
            event_title = generated["title"]
            ai_takeaway = generated["takeaway"]

            ticker_counter = Counter(
                t for article in cluster.articles for t in article["tickers"]
            )
            primary_symbol = (
                ticker_counter.most_common(1)[0][0] if ticker_counter else "UNKNOWN"
            )
            sorted_symbols = sorted(cluster.tickers)
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
                    "title": event_title,
                    "short_summary": self._build_cluster_summary(cluster),
                    "importance_score": importance,
                    "sentiment": sentiment,
                    "start_time": cluster.first_time,
                    "primary_symbol": primary_symbol,
                    "symbols": sorted_symbols,
                    "tags": signature_tokens[:12],
                    "article_count": len(cluster.articles),
                    "ai_takeaway": ai_takeaway or None,
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
                    "display_title": event_title,
                }
                for symbol in sorted_symbols
            ]
            await market_event_db.replace_symbol_links(
                event_row["event_id"], symbol_links
            )

    async def _generate_cluster_contents(
        self,
        clusters: list[_Cluster],
    ) -> list[dict[str, str]]:
        semaphore = asyncio.Semaphore(EVENT_GENERATION_MAX_CONCURRENCY)

        async def _generate(cluster: _Cluster) -> dict[str, str]:
            fallback_title = self._build_cluster_title(cluster)
            fallback_takeaway = self._build_cluster_summary(cluster)
            try:
                payload = self._build_cluster_generation_payload(cluster)
                async with semaphore:
                    _, title, takeaway, success = await asyncio.wait_for(
                        self._generate_event_interpretation(payload),
                        timeout=EVENT_PREGENERATE_TIMEOUT_SECONDS,
                    )
                return {
                    "title": title if success and title else fallback_title,
                    "takeaway": takeaway if success and takeaway else "",
                }
            except (asyncio.TimeoutError, asyncio.CancelledError) as e:
                logger.warning(
                    "[MARKET_EVENTS] Cluster gen timeout, using fallback: %s", e
                )
            except Exception as e:
                logger.warning(
                    "[MARKET_EVENTS] Cluster gen failed, using fallback: %s", e
                )
            return {
                "title": fallback_title,
                "takeaway": fallback_takeaway if fallback_takeaway else "",
            }

        return await asyncio.gather(*[_generate(cluster) for cluster in clusters])

    def _build_cluster_generation_payload(self, cluster: _Cluster) -> dict[str, Any]:
        ticker_counter = Counter(
            ticker for article in cluster.articles for ticker in article["tickers"]
        )
        primary_symbol = (
            ticker_counter.most_common(1)[0][0] if ticker_counter else None
        )
        return {
            "title": self._build_cluster_title(cluster),
            "summary": self._build_cluster_summary(cluster),
            "symbols": sorted(cluster.tickers),
            "primary_symbol": primary_symbol,
            "sentiment": _pick_sentiment(cluster.sentiments),
            "importance_score": _normalize_score(
                article_count=len(cluster.articles),
                unique_source_count=len(cluster.sources),
                has_sentiment=bool(cluster.sentiments),
            ),
            "related_articles": [
                {
                    "title": article.get("title"),
                    "source_name": article.get("source_name"),
                    "published_at": (
                        article.get("published_at").isoformat()
                        if getattr(article.get("published_at"), "isoformat", None)
                        else article.get("published_at")
                    ),
                    "summary": article.get("context_text"),
                    "tickers": article.get("tickers"),
                }
                for article in cluster.articles[:6]
            ],
        }

    def _build_cluster_title(self, cluster: _Cluster) -> str:
        if not cluster.articles:
            return ""
        if len(cluster.articles) == 1:
            return str(cluster.articles[0]["title"])

        best_article = max(
            cluster.articles,
            key=lambda article: (
                self._cluster_title_score(article, cluster.articles, cluster.tickers),
                len(set(article["tickers"]) & cluster.tickers),
                -len(str(article.get("title") or "")),
                article.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
        return str(best_article["title"])

    def _cluster_title_score(
        self,
        candidate: dict[str, Any],
        articles: list[dict[str, Any]],
        cluster_tickers: set[str],
    ) -> float:
        if not articles:
            return 0.0

        peer_scores = [
            self._article_pair_similarity(candidate, article)
            for article in articles
            if article["id"] != candidate["id"]
        ]
        mean_peer_score = sum(peer_scores) / len(peer_scores) if peer_scores else 1.0
        ticker_coverage = (
            len(set(candidate["tickers"]) & cluster_tickers) / len(cluster_tickers)
            if cluster_tickers
            else 0.0
        )
        source_bonus = 0.02 if candidate.get("source_name") else 0.0
        return round((mean_peer_score * 0.9) + (ticker_coverage * 0.08) + source_bonus, 4)

    def _article_pair_similarity(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> float:
        title_similarity = _jaccard(left["title_tokens"], right["title_tokens"])
        title_coverage = _coverage(left["title_tokens"], right["title_tokens"])
        context_similarity = _jaccard(left["context_tokens"], right["context_tokens"])
        ticker_overlap = _coverage(set(left["tickers"]), set(right["tickers"]))

        return round(
            (title_similarity * 0.55)
            + (title_coverage * 0.25)
            + (context_similarity * 0.12)
            + (ticker_overlap * 0.08),
            4,
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
