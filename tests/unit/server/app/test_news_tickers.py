from src.server.app.news import _compact, _merge_tag_maps
from src.server.services.commodity_mapping import CRUDE_OIL
from src.server.services.news_enrichment_service import NewsEnrichmentService


def test_compact_uses_tagged_tickers_over_raw_pobo_tickers():
    article = {
        "id": "pobo-1",
        "title": "Crude oil prices rise",
        "published_at": "2026-04-30T01:00:00+00:00",
        "article_url": "",
        "source": {"name": "Pobo"},
        "tickers": ["PB_ENERGY"],
    }
    compact = _compact(
        article,
        tag_map={
            "pobo-1": {
                "tickers": [CRUDE_OIL],
                "sector": "energy",
                "topic": "energy",
                "region": "China",
                "tags": ["energy", CRUDE_OIL.lower()],
            }
        },
    )

    assert compact is not None
    assert compact.tickers == [CRUDE_OIL]


def test_fresh_tag_map_overrides_stale_persisted_tickers():
    merged = _merge_tag_maps(
        persisted_tag_map={"pobo-1": {"tickers": ["PB_ENERGY"]}},
        fresh_tag_map={"pobo-1": {"tickers": [CRUDE_OIL]}},
    )

    assert merged["pobo-1"]["tickers"] == [CRUDE_OIL]


def test_ask_payload_uses_tagged_tickers_over_raw_pobo_tickers():
    payload = NewsEnrichmentService().build_ask_payload(
        {
            "id": "pobo-1",
            "title": "Crude oil prices rise",
            "description": "WTI crude oil futures moved higher.",
            "article_url": "",
            "source": {"name": "Pobo"},
            "published_at": "2026-04-30T01:00:00+00:00",
            "tickers": ["PB_ENERGY"],
        }
    )

    context = payload["additional_context"][0]["content"]
    assert f"Tickers: {CRUDE_OIL}" in context
    assert "PB_ENERGY" not in context
