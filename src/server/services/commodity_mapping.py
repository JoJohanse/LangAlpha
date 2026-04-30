"""Commodity symbol mapping for news ingestion.

Maps free-form news text (title + description + content) to a fixed universe of
five commodities. Articles that do not match any commodity should be filtered
out before downstream tagging or event clustering.
"""

from __future__ import annotations

import re

CRUDE_OIL = "原油"
GOLD = "黄金"
COPPER = "铜"
REBAR = "螺纹钢"
SOYBEAN_MEAL = "豆粕"

ALLOWED_COMMODITIES: tuple[str, ...] = (
    CRUDE_OIL,
    GOLD,
    COPPER,
    REBAR,
    SOYBEAN_MEAL,
)

# Keyword dictionary. English keywords are lowercased and matched on a
# normalized lowercase text; CJK keywords are matched on the original text.
_COMMODITY_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    CRUDE_OIL: {
        "en": (
            "crude oil", "crude", "brent", "wti", "opec", "opec+",
            "petroleum", "shale oil", "oil price", "oil futures",
        ),
        "cjk": (
            "原油", "石油", "布伦特", "布兰特", "美油", "油价", "页岩油",
            "欧佩克", "沙特", "燃油",
        ),
    },
    GOLD: {
        "en": (
            "gold", "bullion", "xau", "xauusd", "gold price",
            "gold futures", "comex gold",
        ),
        "cjk": ("黄金", "金价", "金条", "金饰", "沪金", "现货黄金"),
    },
    COPPER: {
        "en": (
            "copper", "lme copper", "comex copper", "copper price",
            "copper futures", "red metal",
        ),
        "cjk": ("铜价", "沪铜", "电解铜", "精炼铜", "铜矿", "伦铜"),
    },
    REBAR: {
        "en": (
            "rebar", "steel rebar", "rebar futures", "construction steel",
            "deformed bar",
        ),
        "cjk": ("螺纹钢", "螺纹", "建筑钢材", "钢筋"),
    },
    SOYBEAN_MEAL: {
        "en": (
            "soybean meal", "soymeal", "soya meal", "soybean meal futures",
        ),
        "cjk": ("豆粕", "大豆粕", "豆粕期货"),
    },
}

# Tickers commonly emitted by upstream providers that we map directly.
_TICKER_TO_COMMODITY: dict[str, str] = {
    "CL": CRUDE_OIL, "CL=F": CRUDE_OIL, "BZ": CRUDE_OIL, "BZ=F": CRUDE_OIL,
    "USO": CRUDE_OIL, "BNO": CRUDE_OIL, "WTI": CRUDE_OIL, "BRENT": CRUDE_OIL,
    "GC": GOLD, "GC=F": GOLD, "XAU": GOLD, "XAUUSD": GOLD,
    "GLD": GOLD, "IAU": GOLD,
    "HG": COPPER, "HG=F": COPPER, "CPER": COPPER,
    "ZM": SOYBEAN_MEAL, "ZM=F": SOYBEAN_MEAL,
}

# A small overall match-strength threshold below which an article is dropped.
# 1 keyword hit == 1 unit. Tunable.
MIN_MATCH_SCORE = 1


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def map_text_to_commodities(text: str) -> dict[str, int]:
    """Return {commodity: hit_count} for matches found in *text*.

    English keywords are matched case-insensitively on a normalized form;
    CJK keywords are matched on the raw text (case is irrelevant for CJK).
    """
    if not text:
        return {}
    lowered = _normalize(text)
    raw = text or ""
    scores: dict[str, int] = {}
    for commodity, groups in _COMMODITY_KEYWORDS.items():
        hits = 0
        for kw in groups.get("en", ()):  # word-ish boundary for short tokens
            if len(kw) <= 3:
                if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", lowered):
                    hits += 1
            elif kw in lowered:
                hits += 1
        for kw in groups.get("cjk", ()):
            if kw in raw:
                hits += 1
        if hits > 0:
            scores[commodity] = hits
    return scores


def map_article_to_commodities(
    *,
    title: str | None = None,
    description: str | None = None,
    content: str | None = None,
    tickers: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Map an article's text + tickers to allowed commodity codes.

    Returns a list of commodity codes (in fixed ALLOWED_COMMODITIES order)
    whose total match score meets MIN_MATCH_SCORE. Returns an empty list
    when the article does not match any commodity well — caller should drop.
    """
    text_blob = "\n".join(p for p in (title, description, content) if p)
    scores = map_text_to_commodities(text_blob)

    for ticker in tickers or ():
        commodity = _TICKER_TO_COMMODITY.get(str(ticker).upper())
        if commodity:
            scores[commodity] = scores.get(commodity, 0) + 2  # ticker is strong

    matched = [c for c in ALLOWED_COMMODITIES if scores.get(c, 0) >= MIN_MATCH_SCORE]
    return matched
