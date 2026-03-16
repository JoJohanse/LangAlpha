from __future__ import annotations

import pytest_asyncio

from ptc_agent.core.sandbox.ptc_sandbox import PTCSandbox


@pytest_asyncio.fixture
async def sandbox(core_config, _patch_create_provider):
    """A PTCSandbox with workspace set up, ready for operations."""
    sb = PTCSandbox(core_config)
    await sb.setup_sandbox_workspace()
    assert sb.runtime is not None
    assert sb.sandbox_id is not None

    actual_work_dir = await sb.runtime.fetch_working_dir()
    sb.config.filesystem.working_directory = actual_work_dir
    sb.config.filesystem.allowed_directories = [actual_work_dir, "/tmp"]
    sb.TOKEN_FILE_PATH = f"{actual_work_dir}/_internal/.mcp_tokens.json"
    sb.UNIFIED_MANIFEST_PATH = f"{actual_work_dir}/_internal/.sandbox_manifest.json"

    yield sb
    try:
        await sb.cleanup()
    except Exception:
        pass


@pytest_asyncio.fixture
async def sandbox_minimal(core_config, _patch_create_provider):
    """A PTCSandbox constructed but NOT set up -- for testing init flow."""
    sb = PTCSandbox(core_config)
    yield sb
    try:
        if sb.runtime:
            await sb.cleanup()
    except Exception:
        pass
