from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestExecuteBashCommand:
    """PTCSandbox.execute_bash_command() -- shell command execution."""

    async def test_bash_simple(self, sandbox):
        wd = sandbox._work_dir
        result = await sandbox.execute_bash_command("echo hello bash", working_dir=wd)
        assert result["success"] is True
        assert "hello bash" in result["stdout"]
        assert result["exit_code"] == 0

    async def test_bash_returns_metadata(self, sandbox):
        wd = sandbox._work_dir
        result = await sandbox.execute_bash_command("echo test", working_dir=wd)
        assert "bash_id" in result
        assert "command_hash" in result

    async def test_bash_error(self, sandbox):
        wd = sandbox._work_dir
        result = await sandbox.execute_bash_command("exit 1", working_dir=wd)
        assert result["success"] is False
        assert result["exit_code"] == 1

    async def test_bash_increments_counter(self, sandbox):
        wd = sandbox._work_dir
        assert sandbox.bash_execution_count == 0
        await sandbox.execute_bash_command("echo 1", working_dir=wd)
        assert sandbox.bash_execution_count == 1

    async def test_bash_with_pipe(self, sandbox):
        wd = sandbox._work_dir
        result = await sandbox.execute_bash_command("echo 'a b c' | wc -w", working_dir=wd)
        assert result["success"] is True
        assert "3" in result["stdout"]

    async def test_bash_creates_files(self, sandbox):
        wd = sandbox._work_dir
        await sandbox.execute_bash_command(f"echo 'bash content' > {wd}/bash_file.txt", working_dir=wd)
        content = await sandbox.adownload_file_bytes(f"{wd}/bash_file.txt")
        assert content is not None
        assert b"bash content" in content
