from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestExecute:
    """PTCSandbox.execute() -- Python code execution with full orchestration."""

    async def test_execute_simple_code(self, sandbox):
        result = await sandbox.execute("print('hello world')")
        assert result.success is True
        assert "hello world" in result.stdout

    async def test_execute_returns_execution_result(self, sandbox):
        result = await sandbox.execute("x = 42; print(x)")
        assert result.success is True
        assert result.execution_id is not None
        assert result.code_hash is not None
        assert isinstance(result.duration, float)

    async def test_execute_error_code(self, sandbox):
        result = await sandbox.execute("raise RuntimeError('test failure')")
        assert result.success is False

    async def test_execute_creates_code_file(self, sandbox):
        """execute() should save the code to code/ directory."""
        result = await sandbox.execute("print('saved')")
        assert result.success is True
        # Check code dir has files
        ls_result = await sandbox.runtime.exec(f"ls {sandbox._work_dir}/code/")
        assert ls_result.exit_code == 0

    async def test_execute_with_thread_id(self, sandbox):
        result = await sandbox.execute(
            "print('threaded')", thread_id="test-thread-123"
        )
        assert result.success is True
        # Check thread dir was created
        ls_result = await sandbox.runtime.exec(
            f"test -d {sandbox._work_dir}/.agent/threads/test-thread-123/code && echo OK"
        )
        assert "OK" in ls_result.stdout

    async def test_execute_with_file_creation(self, sandbox):
        """Code that creates files should report files_created."""
        result = await sandbox.execute(
            "with open('results/test_output.txt', 'w') as f: f.write('data')"
        )
        assert result.success is True

    async def test_execute_increments_counter(self, sandbox):
        assert sandbox.execution_count == 0
        await sandbox.execute("print(1)")
        assert sandbox.execution_count == 1
        await sandbox.execute("print(2)")
        assert sandbox.execution_count == 2

    async def test_execute_with_pythonpath(self, sandbox):
        """Verify PYTHONPATH is set so _internal/src imports work."""
        # Upload a module to _internal/src
        await sandbox.runtime.upload_file(
            b"INTERNAL_VALUE = 99\n",
            f"{sandbox._work_dir}/_internal/src/test_internal.py",
        )
        result = await sandbox.execute(
            "from test_internal import INTERNAL_VALUE; print(INTERNAL_VALUE)"
        )
        assert result.success is True
        assert "99" in result.stdout
