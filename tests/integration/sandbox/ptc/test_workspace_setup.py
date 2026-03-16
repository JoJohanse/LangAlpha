from __future__ import annotations

import pytest

from ptc_agent.core.sandbox.runtime import RuntimeState

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestWorkspaceSetup:
    """setup_sandbox_workspace() creates the runtime and directory skeleton."""

    async def test_setup_creates_runtime(self, sandbox):
        assert sandbox.runtime is not None
        assert sandbox.sandbox_id is not None
        state = await sandbox.runtime.get_state()
        assert state == RuntimeState.RUNNING

    async def test_setup_creates_directories(self, sandbox):
        """Verify all 8 standard directories exist after setup."""
        expected_dirs = [
            "tools",
            "tools/docs",
            "results",
            "data",
            "code",
            "work",
            ".agent/threads",
            "_internal/src",
        ]
        for d in expected_dirs:
            result = await sandbox.runtime.exec(f"test -d {sandbox._work_dir}/{d} && echo EXISTS")
            assert "EXISTS" in result.stdout, f"Directory {d} was not created"

    async def test_setup_idempotent_structure(self, sandbox):
        """Calling _setup_workspace again should not fail."""
        await sandbox._setup_workspace()
        result = await sandbox.runtime.exec(f"test -d {sandbox._work_dir}/tools && echo OK")
        assert "OK" in result.stdout
