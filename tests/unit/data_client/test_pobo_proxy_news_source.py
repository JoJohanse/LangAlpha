from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

from src.data_client.pobo_proxy.news_source import PoboProxyNewsSource
from src.data_client.registry import _pobo_proxy_available


def _mock_transport(payload: dict):
    def _handler(req: httpx.Request) -> httpx.Response:
        if req.url.path in {"/news", "/health"}:
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(_handler)


@pytest.mark.asyncio
async def test_get_news_normalizes_pobo_items():
    source = PoboProxyNewsSource(
        base_url="http://test.local",
        transport=_mock_transport(
            {
                "count": 1,
                "items": [
                    {
                        "InfoID": 123,
                        "InfoTitle": "〖金融财经〗美元上涨",
                        "Summary": "宏观摘要",
                        "CreateTime": "Fri, 24 Apr 2026 13:56:29 GMT",
                        "URL": None,
                        "Source": "上海澎博",
                        "InfoType": "021",
                        "InfoTypeName": "金融财经",
                    }
                ],
            }
        ),
    )
    data = await source.get_news(limit=20)
    await source.close()

    assert data["count"] == 1
    article = data["results"][0]
    assert article["id"] == "pobo-123"
    assert article["title"] == "〖金融财经〗美元上涨"
    assert article["description"] == "宏观摘要"
    assert article["tickers"] == ["PB_MACRO"]
    assert article["article_url"] == ""
    assert article["source"]["name"] == "上海澎博"
    assert datetime.fromisoformat(article["published_at"]).tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_get_news_fallback_to_infotype_code_when_name_missing():
    source = PoboProxyNewsSource(
        base_url="http://test.local",
        transport=_mock_transport(
            {
                "count": 1,
                "items": [
                    {
                        "InfoID": 124,
                        "InfoTitle": "测试",
                        "InfoBody": "<p>正文</p>",
                        "CreateTime": "2026-04-24T10:20:09+00:00",
                        "InfoType": "034",
                    }
                ],
            }
        ),
    )
    data = await source.get_news(limit=20)
    await source.close()
    assert data["results"][0]["tickers"] == ["PB_ENERGY"]
    assert data["results"][0]["description"] == "正文"


@pytest.mark.asyncio
async def test_get_news_article_finds_by_pobo_id():
    source = PoboProxyNewsSource(
        base_url="http://test.local",
        transport=_mock_transport(
            {
                "count": 2,
                "items": [
                    {"InfoID": 200, "InfoTitle": "A", "CreateTime": "Fri, 24 Apr 2026 13:56:29 GMT"},
                    {"InfoID": 201, "InfoTitle": "B", "CreateTime": "Fri, 24 Apr 2026 13:56:29 GMT"},
                ],
            }
        ),
    )
    found = await source.get_news_article("pobo-201")
    missing = await source.get_news_article("pobo-999")
    invalid = await source.get_news_article("abc-201")
    await source.close()
    assert found is not None and found["id"] == "pobo-201"
    assert missing is None
    assert invalid is None


def test_pobo_proxy_available_true():
    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("src.data_client.registry.request.urlopen", return_value=_Resp()):
        assert _pobo_proxy_available() is True


def test_pobo_proxy_available_false_on_error():
    with patch("src.data_client.registry.request.urlopen", side_effect=OSError("no route")):
        assert _pobo_proxy_available() is False

