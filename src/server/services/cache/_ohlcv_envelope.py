"""Shared envelope helpers for OHLCV cache services (daily + intraday).

Provides the envelope structure, parsing, delta-merge, and SWR staleness
check used by both DailyCacheService and IntradayCacheService.
"""

import time
from bisect import bisect_left
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.config.settings import get_nested_config
from src.utils.market_hours import current_trading_date, is_market_active, is_market_closed

_ET = ZoneInfo("America/New_York")

ENVELOPE_VERSION = 3  # v3: adds data_date and truncated fields
_SOFT_TTL_RATIO: float = get_nested_config("redis.swr.soft_ttl_ratio", 0.5)
_TRUNCATED_TTL_RATIO = 0.25  # aggressive refresh for truncated data
_EMPTY_RESULT_TTL = 30  # short TTL for empty upstream results


def _build_envelope(
    bars: List[Dict[str, Any]],
    market_phase: str,
    complete: bool,
    stored_ttl: int = 0,
    truncated: bool = False,
    data_date: Optional[str] = None,
) -> Dict[str, Any]:
    watermark = bars[-1].get("time", 0) if bars else 0
    return {
        "v": ENVELOPE_VERSION,
        "bars": bars,
        "watermark": watermark,
        "fetched_at": time.time(),
        "market_phase": market_phase,
        "complete": complete,
        "stored_ttl": stored_ttl,
        "data_date": data_date or current_trading_date(),
        "truncated": truncated,
    }


def _parse_envelope(raw: Any) -> Optional[Dict[str, Any]]:
    """Return the envelope dict if valid, else None (treat as cache miss)."""
    if not isinstance(raw, dict):
        return None
    if raw.get("v") != ENVELOPE_VERSION:
        return None
    if "bars" not in raw:
        return None
    return raw


def _merge_bars(
    existing: List[Dict[str, Any]],
    delta: List[Dict[str, Any]],
    watermark,
) -> List[Dict[str, Any]]:
    """Merge delta bars into existing, keeping the immutable prefix intact.

    Everything before the watermark is immutable history.
    Delta replaces everything from the watermark onward.
    Delta may start earlier than the watermark (when from_date is a date
    string rather than a precise timestamp), so we filter it first.

    Gap fill: when the delta contains bars that predate the existing prefix
    (e.g. the initial load returned only recent bars), those earlier bars
    are prepended so the gap is filled on the next refresh.
    """
    if not existing:
        return delta
    if not delta:
        return existing

    # Find split point via bisect on the "time" field (Unix ms)
    times = [b.get("time", 0) for b in existing]
    split_idx = bisect_left(times, watermark)

    # Filter delta to only bars at or after the watermark so we don't
    # re-introduce bars that are already in the immutable prefix.
    fresh = [b for b in delta if b.get("time", 0) >= watermark]

    # Gap fill: delta bars that predate existing (partial initial load).
    first_existing_time = times[0] if times else 0
    gap_fill = [b for b in delta if 0 < b.get("time", 0) < first_existing_time]

    if not fresh and not gap_fill:
        return existing

    return gap_fill + existing[:split_idx] + fresh


def watermark_to_date_str(watermark) -> Optional[str]:
    """Convert a watermark (Unix ms) to an ET date string (YYYY-MM-DD)."""
    if not watermark or not isinstance(watermark, (int, float)) or watermark <= 0:
        return None
    dt_et = datetime.fromtimestamp(watermark / 1000, tz=timezone.utc).astimezone(_ET)
    return dt_et.strftime("%Y-%m-%d")


def _is_stale_date(envelope: Dict[str, Any]) -> bool:
    """Return True if the envelope's data_date doesn't match today's trading date.

    Only returns True when the market is active (pre/open/post), since
    during closed hours the previous trading day's data is expected.
    """
    data_date = envelope.get("data_date")
    if not data_date:
        return True  # missing data_date — treat as stale
    if not is_market_active():
        return False
    return data_date != current_trading_date()


def _needs_refresh(envelope: Dict[str, Any], ttl: int) -> bool:
    """Determine whether an SWR background refresh should fire.

    Priority order:
    1. Stale date (data_date != current trading date, market active) → always refresh
    2. Complete + market reopened → refresh (day-boundary transition)
    3. Truncated data → aggressive 25% soft TTL
    4. Normal → 50% soft TTL
    """
    # 1. Stale date — strongest signal
    if _is_stale_date(envelope):
        return True

    # 2. Complete + market reopened
    if envelope.get("complete"):
        if not is_market_closed():
            return True
        return False

    elapsed = time.time() - envelope.get("fetched_at", 0)

    # 3. Truncated data — aggressive refresh
    if envelope.get("truncated"):
        return elapsed > ttl * _TRUNCATED_TTL_RATIO

    # 4. Normal soft TTL
    return elapsed > ttl * _SOFT_TTL_RATIO
