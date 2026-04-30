"""News enrichment helpers: tags, hot-rank scoring, ask-context payload."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from src.server.database import news_article_tags as tags_db
from src.server.services.commodity_mapping import map_article_to_commodities

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "artificial intelligence", "llm", "semiconductor", "chip"),
    "earnings": ("earnings", "guidance", "eps", "revenue", "quarter"),
    "macro": ("inflation", "fed", "rates", "treasury", "cpi", "ppi", "gdp"),
    "crypto": ("bitcoin", "ethereum", "crypto", "blockchain", "token"),
    "energy": ("oil", "gas", "opec", "energy", "refinery"),
    "healthcare": ("drug", "fda", "biotech", "healthcare", "trial"),
}

_SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "technology": ("tech", "software", "cloud", "chip", "semiconductor", "ai"),
    "finance": ("bank", "lender", "insurance", "credit", "financial"),
    "energy": ("oil", "gas", "energy", "refining", "opec"),
    "healthcare": ("health", "biotech", "pharma", "drug", "medical"),
    "consumer": ("retail", "consumer", "ecommerce", "apparel", "restaurant"),
    "industrial": ("manufacturing", "industrial", "aerospace", "logistics"),
}

_REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "US": ("u.s.", "us ", "united states", "wall street", "nyse", "nasdaq"),
    "China": ("china", "beijing", "shanghai", "hong kong"),
    "Europe": ("europe", "eu", "ecb", "london", "frankfurt"),
    "Japan": ("japan", "tokyo", "nikkei"),
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


def _norm_text(parts: list[str]) -> str:
    text = " ".join(p for p in parts if p).strip().lower()
    return re.sub(r"\s+", " ", text)


def _first_match(text: str, dictionary: dict[str, tuple[str, ...]], default: str = "general") -> str:
    for label, keywords in dictionary.items():
        if any(k in text for k in keywords):
            return label
    return default


@dataclass
class TaggedArticle:
    article_id: str
    title: str
    article_url: str | None
    source_name: str | None
    published_at: datetime | None
    tickers: list[str]
    sector: str
    topic: str
    region: str
    tags: list[str]
    sentiments: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "article_url": self.article_url,
            "source_name": self.source_name,
            "published_at": self.published_at,
            "tickers": self.tickers,
            "sector": self.sector,
            "topic": self.topic,
            "region": self.region,
            "tags": self.tags,
            "sentiments": self.sentiments,
        }


class NewsEnrichmentService:
    async def build_and_store_tags(self, raw_articles: list[dict[str, Any]]) -> list[TaggedArticle]:
        tagged: list[TaggedArticle] = []
        for article in raw_articles:
            t = self._tag_article(article)
            if not t:
                continue
            tagged.append(t)
            await tags_db.upsert_news_article_tag(
                {
                    "article_id": t.article_id,
                    "title": t.title,
                    "article_url": t.article_url,
                    "source_name": t.source_name,
                    "published_at": t.published_at,
                    "tickers": t.tickers,
                    "sector": t.sector,
                    "topic": t.topic,
                    "region": t.region,
                    "tags": t.tags,
                }
            )
        return tagged

    def _tag_article(self, article: dict[str, Any]) -> TaggedArticle | None:
        article_id = str(article.get("id") or "").strip()
        title = str(article.get("title") or "").strip()
        if not article_id or not title:
            return None
        description = str(article.get("description") or "").strip()
        source_name = str(((article.get("source") or {}).get("name")) or "").strip() or None
        text = _norm_text([title, description, source_name or ""])
        raw_tickers = [str(t).upper() for t in (article.get("tickers") or []) if t]
        tickers = map_article_to_commodities(
            title=title,
            description=description,
            content=str(article.get("content") or article.get("body") or "").strip(),
            tickers=raw_tickers,
        )
        if not tickers:
            return None
        sentiments = []
        for s in (article.get("sentiments") or []):
            sent = str((s or {}).get("sentiment") or "").lower()
            if sent in {"positive", "negative", "neutral"}:
                sentiments.append(sent)

        sector = _first_match(text, _SECTOR_KEYWORDS, default="general")
        topic = _first_match(text, _TOPIC_KEYWORDS, default="general")
        region = _first_match(text, _REGION_KEYWORDS, default="US")
        tags = sorted({sector, topic, region.lower(), *[t.lower() for t in tickers]})[:12]

        return TaggedArticle(
            article_id=article_id,
            title=title,
            article_url=(str(article.get("article_url") or "").strip() or None),
            source_name=source_name,
            published_at=_safe_parse_dt(article.get("published_at")),
            tickers=tickers,
            sector=sector,
            topic=topic,
            region=region,
            tags=tags,
            sentiments=sentiments,
        )

    def build_hot_rank(
        self,
        tagged_articles: list[TaggedArticle],
        window_hours: int = 24,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=window_hours)
        rows: list[dict[str, Any]] = []
        for article in tagged_articles:
            if article.published_at and article.published_at < window_start:
                continue
            recency = self._recency_score(article.published_at, now=now)
            source_count = 1.0 if article.source_name else 0.5
            sentiment_presence = 1.0 if article.sentiments else 0.0
            ticker_bonus = min(1.0, len(article.tickers) / 3)
            importance = round(
                min(100.0, 45 * recency + 25 * source_count + 15 * sentiment_presence + 15 * ticker_bonus),
                2,
            )
            rows.append(
                {
                    **article.as_dict(),
                    "importance_score": importance,
                    "recency_score": round(recency * 100, 2),
                    "source_count": 1 if article.source_name else 0,
                }
            )
        rows.sort(key=lambda x: (x["importance_score"], x.get("published_at") or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        return rows[:limit]

    def build_ask_payload(self, article: dict[str, Any], question: str | None = None) -> dict[str, Any]:
        title = str(article.get("title") or "").strip()
        ai_summary = str(article.get("ai_takeaway") or "").strip()
        description = str(article.get("description") or "").strip()
        source_name = str(((article.get("source") or {}).get("name")) or "").strip()
        article_url = str(article.get("article_url") or "").strip()
        tagged = self._tag_article(article)
        raw_tickers = [str(t).upper() for t in (article.get("tickers") or []) if t]
        tickers = tagged.tickers if tagged else raw_tickers
        ask_message = (question or "").strip()
        if not ask_message:
            ask_message = f"Please analyze the market impact of this news"
        additional_info = [
            "Use the following news context when answering the user's question.",
            f"Title: {title}",
            f"Summary: {ai_summary or description}",
        ]
        if source_name:
            additional_info.append(f"Source: {source_name}")
        if article_url:
            additional_info.append(f"URL: {article_url}")
        if tickers:
            additional_info.append(f"Tickers: {', '.join(tickers)}")
        if tagged:
            additional_info.append(f"Sector: {tagged.sector}")
            additional_info.append(f"Topic: {tagged.topic}")
            additional_info.append(f"Region: {tagged.region}")
            if tagged.tags:
                additional_info.append(f"Tags: {', '.join(tagged.tags)}")
        additional_context = [{"type": "directive", "content": "\n".join(additional_info)}]
        return {
            "thread_initial_message": ask_message,
            "additional_context": additional_context,
            "fallback_message": ask_message,
        }

    @staticmethod
    def _recency_score(published_at: datetime | None, now: datetime) -> float:
        if published_at is None:
            return 0.0
        age_hours = max(0.0, (now - published_at).total_seconds() / 3600)
        if age_hours <= 1:
            return 1.0
        if age_hours >= 24:
            return 0.0
        return max(0.0, 1.0 - (age_hours - 1) / 23)
