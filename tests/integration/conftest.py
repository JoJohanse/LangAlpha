"""Fixtures for integration tests.

Resets FMP and ginlix-data singletons between tests to avoid
'Event loop is closed' errors from stale httpx clients.
"""

from __future__ import annotations

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _reset_fmp_singleton():
    """Close and reset the FMP client singleton after each test."""
    yield
    from data_client.fmp import close_fmp_client
    await close_fmp_client()


@pytest_asyncio.fixture(autouse=True)
async def _reset_ginlix_singleton():
    """Close and reset the ginlix-data httpx client after each test."""
    yield
    import mcp_servers.price_data_mcp_server as mod
    if mod._ginlix_http is not None:
        await mod._ginlix_http.aclose()
        mod._ginlix_http = None
