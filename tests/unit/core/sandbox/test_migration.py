"""
Tests for ptc_agent.core.sandbox.migration — versioned sandbox layout migrations.

Covers:
- Zero cost when already current (no API calls)
- v1→v2 migration moves directories, creates skills dir, removes old skills/
- Idempotency (safe to re-run)
- Skipping missing source directories
- Sequential migration execution via run_layout_migrations
"""

import shlex

import pytest
from unittest.mock import AsyncMock

from ptc_agent.core.sandbox.migration import (
    CURRENT_LAYOUT_VERSION,
    migrate_layout_v1_to_v2,
    run_layout_migrations,
)


@pytest.fixture
def mock_runtime():
    runtime = AsyncMock()
    runtime.exec = AsyncMock(return_value="")
    return runtime


WORK_DIR = "/home/user/project"


# ---------------------------------------------------------------------------
# Zero cost when current
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_cost_when_current(mock_runtime):
    """current_version >= CURRENT_LAYOUT_VERSION -> returns immediately, no API calls."""
    result = await run_layout_migrations(
        mock_runtime, WORK_DIR, current_version=CURRENT_LAYOUT_VERSION
    )
    assert result == CURRENT_LAYOUT_VERSION
    mock_runtime.exec.assert_not_called()


@pytest.mark.asyncio
async def test_zero_cost_when_ahead(mock_runtime):
    """current_version > CURRENT_LAYOUT_VERSION -> also returns immediately."""
    result = await run_layout_migrations(
        mock_runtime, WORK_DIR, current_version=CURRENT_LAYOUT_VERSION + 1
    )
    assert result == CURRENT_LAYOUT_VERSION + 1
    mock_runtime.exec.assert_not_called()


# ---------------------------------------------------------------------------
# v1 → v2 migration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_v1_to_v2_moves_dirs(mock_runtime):
    """Verify the migration runs shell commands to move .agent/ subdirs to .agents/."""
    await migrate_layout_v1_to_v2(mock_runtime, WORK_DIR)

    calls = [call.args[0] for call in mock_runtime.exec.call_args_list]

    # Should create .agents/skills/ first
    assert any("mkdir -p" in c and ".agents/skills" in c for c in calls), (
        f"Expected mkdir for .agents/skills/ in calls: {calls}"
    )

    # Should move .agent/threads -> .agents/threads
    assert any(
        ".agent/threads" in c and ".agents/threads" in c and "cp -a" in c
        for c in calls
    ), f"Expected move of .agent/threads in calls: {calls}"

    # Should move .agent/user -> .agents/user
    assert any(
        ".agent/user" in c and ".agents/user" in c and "cp -a" in c
        for c in calls
    ), f"Expected move of .agent/user in calls: {calls}"

    # Should move .agent/large_tool_results -> .agents/large_tool_results
    assert any(
        ".agent/large_tool_results" in c
        and ".agents/large_tool_results" in c
        and "cp -a" in c
        for c in calls
    ), f"Expected move of .agent/large_tool_results in calls: {calls}"

    # Should clean up old .agent/ directory
    assert any("rmdir" in c and ".agent" in c for c in calls), (
        f"Expected rmdir of .agent/ in calls: {calls}"
    )

    # Should remove old skills/ directory
    assert any("rm -rf" in c and "/skills" in c for c in calls), (
        f"Expected rm -rf of skills/ in calls: {calls}"
    )


@pytest.mark.asyncio
async def test_migration_v1_to_v2_idempotent(mock_runtime):
    """Running migration twice should not fail — shell commands are idempotent."""
    await migrate_layout_v1_to_v2(mock_runtime, WORK_DIR)
    first_call_count = mock_runtime.exec.call_count

    # Run again — same commands should be issued without error
    await migrate_layout_v1_to_v2(mock_runtime, WORK_DIR)
    second_call_count = mock_runtime.exec.call_count - first_call_count

    # Same number of exec calls both times (deterministic, not skipping)
    assert first_call_count == second_call_count


@pytest.mark.asyncio
async def test_migration_v1_to_v2_creates_skills_dir(mock_runtime):
    """.agents/skills/ is created via mkdir -p."""
    await migrate_layout_v1_to_v2(mock_runtime, WORK_DIR)

    calls = [call.args[0] for call in mock_runtime.exec.call_args_list]

    expected_path = shlex.quote(f"{WORK_DIR}/.agents/skills")
    assert any(f"mkdir -p {expected_path}" in c for c in calls), (
        f"Expected mkdir -p for .agents/skills/ in calls: {calls}"
    )


@pytest.mark.asyncio
async def test_migration_v1_to_v2_skips_missing_source(mock_runtime):
    """If .agent/ doesn't exist, the `if [ -d ... ]` check skips the move."""
    await migrate_layout_v1_to_v2(mock_runtime, WORK_DIR)

    calls = [call.args[0] for call in mock_runtime.exec.call_args_list]

    # Each move command is guarded by `if [ -d <src> ]`
    move_calls = [c for c in calls if "cp -a" in c]
    for cmd in move_calls:
        assert "if [ -d " in cmd, (
            f"Move command not guarded by existence check: {cmd}"
        )


@pytest.mark.asyncio
async def test_migration_v1_to_v2_uses_quoted_paths(mock_runtime):
    """Paths are passed through shlex.quote() for safety."""
    work_dir_with_space = "/home/user/my project"
    await migrate_layout_v1_to_v2(mock_runtime, work_dir_with_space)

    calls = [call.args[0] for call in mock_runtime.exec.call_args_list]

    # shlex.quote wraps paths containing spaces in single quotes
    quoted_skills = shlex.quote(f"{work_dir_with_space}/.agents/skills")
    assert any(quoted_skills in c for c in calls), (
        f"Expected quoted path {quoted_skills} in calls: {calls}"
    )


# ---------------------------------------------------------------------------
# run_layout_migrations orchestration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_layout_migrations_sequential(mock_runtime):
    """With current_version=1 and CURRENT=2, runs exactly the v1->v2 migration."""
    result = await run_layout_migrations(mock_runtime, WORK_DIR, current_version=1)

    assert result == CURRENT_LAYOUT_VERSION
    # v1->v2 migration issues multiple exec calls (mkdir, 3 moves, rmdir, rm)
    assert mock_runtime.exec.call_count > 0

    calls = [call.args[0] for call in mock_runtime.exec.call_args_list]

    # Verify it ran the v1->v2 migration (check for characteristic commands)
    assert any(".agents/skills" in c for c in calls)
    assert any(".agent/threads" in c for c in calls)


@pytest.mark.asyncio
async def test_run_layout_migrations_returns_current_version(mock_runtime):
    """After running all migrations, returns CURRENT_LAYOUT_VERSION."""
    result = await run_layout_migrations(mock_runtime, WORK_DIR, current_version=1)
    assert result == CURRENT_LAYOUT_VERSION
    assert result == 2


@pytest.mark.asyncio
async def test_run_layout_migrations_skips_unknown_versions(mock_runtime):
    """If a version has no registered migrator, it's silently skipped."""
    # Version 0 has no registered migration, so it should skip 0->1
    # but still run 1->2
    result = await run_layout_migrations(mock_runtime, WORK_DIR, current_version=0)
    assert result == CURRENT_LAYOUT_VERSION

    # Should have run v1->v2 migration (version 0->1 has no migrator, skipped)
    calls = [call.args[0] for call in mock_runtime.exec.call_args_list]
    assert any(".agents/skills" in c for c in calls)
