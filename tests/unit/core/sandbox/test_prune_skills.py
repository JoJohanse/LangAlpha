"""Tests for _prune_remote_skills() prune-protection logic in PTCSandbox.

Verifies that user-installed skills are never pruned, stale platform skills
are removed, and safe defaults preserve skills when the lock is unavailable
or has no entry for a given directory.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ptc_agent.config.core import (
    CoreConfig,
    DaytonaConfig,
    FilesystemConfig,
    LoggingConfig,
    MCPConfig,
    SandboxConfig,
    SecurityConfig,
)
from ptc_agent.core.sandbox.runtime import (
    ExecResult,
    RuntimeState,
    SandboxProvider,
    SandboxRuntime,
)


def _make_config(**overrides) -> CoreConfig:
    defaults = dict(
        sandbox=SandboxConfig(daytona=DaytonaConfig(api_key="test-key")),
        security=SecurityConfig(),
        mcp=MCPConfig(),
        logging=LoggingConfig(),
        filesystem=FilesystemConfig(),
    )
    defaults.update(overrides)
    return CoreConfig(**defaults)


def _dir_entry(name: str, path: str) -> dict:
    return {"name": name, "path": path, "is_dir": True}


@pytest.fixture
def mock_runtime():
    runtime = AsyncMock(spec=SandboxRuntime)
    runtime.id = "mock-runtime-1"
    runtime.working_dir = "/home/workspace"
    runtime.exec = AsyncMock(return_value=ExecResult("", "", 0))
    runtime.get_state = AsyncMock(return_value=RuntimeState.RUNNING)
    runtime.list_files = AsyncMock(return_value=[])
    return runtime


@pytest.fixture
def mock_provider(mock_runtime):
    provider = AsyncMock(spec=SandboxProvider)
    provider.create = AsyncMock(return_value=mock_runtime)
    provider.get = AsyncMock(return_value=mock_runtime)
    provider.close = AsyncMock()
    provider.is_transient_error = MagicMock(return_value=False)
    return provider


SANDBOX_BASE = "/home/workspace/.agents/skills"


class TestPruneRemoteSkills:
    """Unit tests for PTCSandbox._prune_remote_skills()."""

    @patch("ptc_agent.core.sandbox.ptc_sandbox.create_provider")
    @pytest.mark.asyncio
    async def test_prune_skips_user_owned_skill(
        self, mock_create_provider, mock_provider, mock_runtime
    ):
        """Skill not in platform list but owner='user' in lock -> survives."""
        from ptc_agent.core.sandbox.ptc_sandbox import PTCSandbox

        mock_create_provider.return_value = mock_provider
        sandbox = PTCSandbox(config=_make_config())
        sandbox.runtime = mock_runtime

        # Sandbox has a user-installed skill "my-custom-skill"
        mock_runtime.list_files = AsyncMock(
            return_value=[
                _dir_entry(
                    "my-custom-skill",
                    f"{SANDBOX_BASE}/my-custom-skill",
                ),
            ]
        )

        lock = {
            "my-custom-skill": {"owner": "user", "name": "my-custom-skill"},
        }

        # Platform set does NOT include "my-custom-skill"
        await sandbox._prune_remote_skills(
            SANDBOX_BASE, local_skill_names=set(), existing_lock=lock
        )

        # rm -rf should NOT have been called
        mock_runtime.exec.assert_not_called()

    @patch("ptc_agent.core.sandbox.ptc_sandbox.create_provider")
    @pytest.mark.asyncio
    async def test_prune_removes_stale_platform_skill(
        self, mock_create_provider, mock_provider, mock_runtime
    ):
        """Skill not in platform list and owner='platform' -> pruned."""
        from ptc_agent.core.sandbox.ptc_sandbox import PTCSandbox

        mock_create_provider.return_value = mock_provider
        sandbox = PTCSandbox(config=_make_config())
        sandbox.runtime = mock_runtime

        mock_runtime.list_files = AsyncMock(
            return_value=[
                _dir_entry(
                    "old-platform-skill",
                    f"{SANDBOX_BASE}/old-platform-skill",
                ),
            ]
        )

        lock = {
            "old-platform-skill": {
                "owner": "platform",
                "name": "old-platform-skill",
            },
        }

        await sandbox._prune_remote_skills(
            SANDBOX_BASE, local_skill_names=set(), existing_lock=lock
        )

        # rm -rf SHOULD have been called for the stale platform skill
        mock_runtime.exec.assert_called_once()
        call_args = mock_runtime.exec.call_args[0][0]
        assert "rm -rf" in call_args
        assert "old-platform-skill" in call_args

    @patch("ptc_agent.core.sandbox.ptc_sandbox.create_provider")
    @pytest.mark.asyncio
    async def test_prune_skips_unknown_skill_safe_default(
        self, mock_create_provider, mock_provider, mock_runtime
    ):
        """Skill dir not in lock at all -> preserved (safe default)."""
        from ptc_agent.core.sandbox.ptc_sandbox import PTCSandbox

        mock_create_provider.return_value = mock_provider
        sandbox = PTCSandbox(config=_make_config())
        sandbox.runtime = mock_runtime

        mock_runtime.list_files = AsyncMock(
            return_value=[
                _dir_entry(
                    "mystery-skill",
                    f"{SANDBOX_BASE}/mystery-skill",
                ),
            ]
        )

        # Lock exists but has no entry for "mystery-skill"
        lock = {
            "other-skill": {"owner": "platform", "name": "other-skill"},
        }

        await sandbox._prune_remote_skills(
            SANDBOX_BASE, local_skill_names=set(), existing_lock=lock
        )

        # Unknown origin -> preserved; rm -rf should NOT be called
        mock_runtime.exec.assert_not_called()

    @patch("ptc_agent.core.sandbox.ptc_sandbox.create_provider")
    @pytest.mark.asyncio
    async def test_prune_skips_all_when_lock_unavailable(
        self, mock_create_provider, mock_provider, mock_runtime
    ):
        """Lock is None -> no skills pruned (safe default)."""
        from ptc_agent.core.sandbox.ptc_sandbox import PTCSandbox

        mock_create_provider.return_value = mock_provider
        sandbox = PTCSandbox(config=_make_config())
        sandbox.runtime = mock_runtime

        mock_runtime.list_files = AsyncMock(
            return_value=[
                _dir_entry(
                    "skill-a",
                    f"{SANDBOX_BASE}/skill-a",
                ),
                _dir_entry(
                    "skill-b",
                    f"{SANDBOX_BASE}/skill-b",
                ),
            ]
        )

        await sandbox._prune_remote_skills(
            SANDBOX_BASE, local_skill_names=set(), existing_lock=None
        )

        # No lock -> everything preserved
        mock_runtime.exec.assert_not_called()

    @patch("ptc_agent.core.sandbox.ptc_sandbox.create_provider")
    @pytest.mark.asyncio
    async def test_prune_cleans_stale_lock_entries(
        self, mock_create_provider, mock_provider, mock_runtime
    ):
        """Only platform skills NOT in local_skill_names are pruned;
        user skills and current platform skills survive."""
        from ptc_agent.core.sandbox.ptc_sandbox import PTCSandbox

        mock_create_provider.return_value = mock_provider
        sandbox = PTCSandbox(config=_make_config())
        sandbox.runtime = mock_runtime

        mock_runtime.list_files = AsyncMock(
            return_value=[
                _dir_entry("current-skill", f"{SANDBOX_BASE}/current-skill"),
                _dir_entry("stale-skill", f"{SANDBOX_BASE}/stale-skill"),
                _dir_entry("user-skill", f"{SANDBOX_BASE}/user-skill"),
            ]
        )

        lock = {
            "current-skill": {"owner": "platform", "name": "current-skill"},
            "stale-skill": {"owner": "platform", "name": "stale-skill"},
            "user-skill": {"owner": "user", "name": "user-skill"},
        }

        # "current-skill" is still in the local platform set
        await sandbox._prune_remote_skills(
            SANDBOX_BASE,
            local_skill_names={"current-skill"},
            existing_lock=lock,
        )

        # Only "stale-skill" should be pruned
        assert mock_runtime.exec.call_count == 1
        call_args = mock_runtime.exec.call_args[0][0]
        assert "rm -rf" in call_args
        assert "stale-skill" in call_args
