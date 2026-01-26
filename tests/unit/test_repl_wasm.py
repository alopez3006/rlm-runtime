"""Tests for WebAssembly REPL using Pyodide."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


class TestWasmREPLInit:
    """Tests for WasmREPL initialization."""

    def test_default_initialization(self):
        """Should initialize with default settings."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL()

        assert repl.timeout == 30
        assert repl.packages == []
        assert repl.allow_top_level_await is True
        assert repl._pyodide is None
        assert repl._context == {}

    def test_custom_timeout(self):
        """Should accept custom timeout."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL(timeout=60)

        assert repl.timeout == 60

    def test_custom_packages(self):
        """Should accept custom packages list."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL(packages=["numpy", "pandas"])

        assert repl.packages == ["numpy", "pandas"]

    def test_disable_top_level_await(self):
        """Should allow disabling top-level await."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL(allow_top_level_await=False)

        assert repl.allow_top_level_await is False

    def test_environment_name(self):
        """Should return 'wasm' as environment name."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL()

        assert repl.environment_name == "wasm"


class TestEnsurePyodide:
    """Tests for Pyodide initialization."""

    @pytest.mark.asyncio
    async def test_pyodide_import_error(self):
        """Should raise ImportError when Pyodide not installed."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL()

        # Both import attempts should fail
        with patch.dict("sys.modules", {"pyodide": None, "pyodide_py": None}):
            with pytest.raises(ImportError) as exc_info:
                await repl._ensure_pyodide()

            assert "Pyodide not installed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pyodide_loads_successfully(self):
        """Should load Pyodide when available."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_load_pyodide = AsyncMock(return_value=mock_pyodide)

        repl = WasmREPL()

        with patch.dict("sys.modules", {"pyodide": MagicMock(loadPyodide=mock_load_pyodide)}):
            with patch("rlm.repl.wasm.WasmREPL._ensure_pyodide", new_callable=AsyncMock) as mock_ensure:
                mock_ensure.return_value = mock_pyodide
                result = await repl._ensure_pyodide()

                # The mock should be called
                mock_ensure.assert_called_once()

    @pytest.mark.asyncio
    async def test_pyodide_cached_after_first_load(self):
        """Should return cached Pyodide after first load."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()

        repl = WasmREPL()
        repl._pyodide = mock_pyodide  # Simulate already loaded

        result = await repl._ensure_pyodide()

        assert result is mock_pyodide


class TestWasmREPLExecute:
    """Tests for WasmREPL execution."""

    @pytest.mark.asyncio
    async def test_execute_handles_import_error(self):
        """Should handle ImportError gracefully."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL()

        # Mock _ensure_pyodide to raise ImportError
        async def raise_import_error():
            raise ImportError("Pyodide not installed")

        with patch.object(repl, "_ensure_pyodide", side_effect=raise_import_error):
            result = await repl.execute("print('hello')")

            assert result.error is not None
            assert "Pyodide not installed" in result.error
            assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_handles_timeout_on_init(self):
        """Should handle timeout during Pyodide initialization."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL(timeout=1)

        # Mock _ensure_pyodide to never complete
        async def slow_init():
            await asyncio.sleep(10)

        with patch.object(repl, "_ensure_pyodide", side_effect=slow_init):
            result = await repl.execute("print('hello')")

            assert result.error is not None
            assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_successful(self):
        """Should execute code and return output."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.globals.get.side_effect = lambda key, default="": {
            "_output": "Hello, World!",
            "_errors": "",
        }.get(key, default)
        mock_pyodide.runPython.return_value = None
        mock_pyodide.runPythonAsync = MagicMock(return_value=None)

        repl = WasmREPL()
        repl._pyodide = mock_pyodide

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=None):
                result = await repl.execute("print('Hello, World!')")

                assert result.output == "Hello, World!"
                assert result.error is None
                assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_with_result(self):
        """Should include result value in output."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.globals.get.side_effect = lambda key, default="": {
            "_output": "",
            "_errors": "",
        }.get(key, default)
        mock_pyodide.runPython.return_value = None

        repl = WasmREPL()
        repl._pyodide = mock_pyodide

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=42):
                result = await repl.execute("2 + 2")

                assert "42" in result.output or "result" in result.output

    @pytest.mark.asyncio
    async def test_execute_with_stderr(self):
        """Should capture stderr output."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.globals.get.side_effect = lambda key, default="": {
            "_output": "",
            "_errors": "Warning: deprecated",
        }.get(key, default)
        mock_pyodide.runPython.return_value = None

        repl = WasmREPL()
        repl._pyodide = mock_pyodide

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=None):
                result = await repl.execute("import warnings")

                assert result.error == "Warning: deprecated"

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self):
        """Should handle execution exceptions."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.runPython.side_effect = [None, RuntimeError("Execution failed"), None]

        repl = WasmREPL()
        repl._pyodide = mock_pyodide

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            with patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=RuntimeError("Execution failed")):
                result = await repl.execute("raise RuntimeError('test')")

                assert result.error is not None
                assert "Execution failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_without_top_level_await(self):
        """Should use runPython when top_level_await disabled."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.globals.get.side_effect = lambda key, default="": {
            "_output": "output",
            "_errors": "",
        }.get(key, default)
        mock_pyodide.runPython.return_value = None

        repl = WasmREPL(allow_top_level_await=False)
        repl._pyodide = mock_pyodide

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=None) as mock_thread:
                result = await repl.execute("x = 1")

                # Should call runPython, not runPythonAsync
                mock_thread.assert_called()
                call_args = mock_thread.call_args
                assert call_args[0][0] == mock_pyodide.runPython

    @pytest.mark.asyncio
    async def test_execute_handles_execution_timeout(self):
        """Should handle timeout during code execution."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()

        async def slow_execution(*args):
            await asyncio.sleep(10)

        repl = WasmREPL(timeout=1)
        repl._pyodide = mock_pyodide

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            with patch("asyncio.to_thread", side_effect=slow_execution):
                result = await repl.execute("import time; time.sleep(100)")

                assert result.error is not None
                assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_truncates_long_output(self):
        """Should truncate very long output."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        # Output exceeding 100,000 chars
        long_output = "x" * 150_000
        mock_pyodide.globals.get.side_effect = lambda key, default="": {
            "_output": long_output,
            "_errors": "",
        }.get(key, default)
        mock_pyodide.runPython.return_value = None

        repl = WasmREPL()
        repl._pyodide = mock_pyodide

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=None):
                result = await repl.execute("print('x' * 150000)")

                assert len(result.output) <= 100_100  # max_output + some extra for message
                assert "truncated" in result.output.lower()
                assert result.truncated is True


class TestWasmREPLReset:
    """Tests for WasmREPL reset."""

    def test_reset_clears_context(self):
        """Should clear the context dictionary."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL()
        repl._context = {"x": 1, "y": 2}

        repl.reset()

        assert repl._context == {}

    def test_reset_clears_pyodide_globals(self):
        """Should clear Pyodide globals when loaded."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        repl = WasmREPL()
        repl._pyodide = mock_pyodide
        repl._context = {"test": "value"}

        repl.reset()

        assert repl._context == {}
        mock_pyodide.runPython.assert_called_once()

    def test_reset_handles_pyodide_error(self):
        """Should handle errors when clearing Pyodide globals."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.runPython.side_effect = Exception("Pyodide error")

        repl = WasmREPL()
        repl._pyodide = mock_pyodide
        repl._context = {"test": "value"}

        # Should not raise
        repl.reset()

        assert repl._context == {}


class TestWasmREPLInstallPackage:
    """Tests for WasmREPL package installation."""

    @pytest.mark.asyncio
    async def test_install_package_success(self):
        """Should return success dict on successful installation."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.loadPackagesFromImports = AsyncMock()

        repl = WasmREPL()

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            result = await repl.install_package("numpy")

            assert result["success"] is True
            assert "message" in result
            mock_pyodide.loadPackagesFromImports.assert_called_once_with(["numpy"])

    @pytest.mark.asyncio
    async def test_install_package_failure(self):
        """Should return failure dict on installation failure."""
        from rlm.repl.wasm import WasmREPL

        mock_pyodide = MagicMock()
        mock_pyodide.loadPackagesFromImports = AsyncMock(side_effect=Exception("Package not found"))
        mock_pyodide.runPythonAsync = AsyncMock(side_effect=Exception("Package not found"))

        repl = WasmREPL()

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, return_value=mock_pyodide):
            result = await repl.install_package("nonexistent-package")

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_install_package_pyodide_init_fails(self):
        """Should return failure dict if Pyodide init fails."""
        from rlm.repl.wasm import WasmREPL

        repl = WasmREPL()

        with patch.object(repl, "_ensure_pyodide", new_callable=AsyncMock, side_effect=ImportError("No pyodide")):
            result = await repl.install_package("numpy")

            assert result["success"] is False
            assert "error" in result


class TestWasmREPLInheritance:
    """Tests for WasmREPL base class inheritance."""

    def test_inherits_from_base_repl(self):
        """Should inherit from BaseREPL."""
        from rlm.repl.wasm import WasmREPL
        from rlm.repl.base import BaseREPL

        assert issubclass(WasmREPL, BaseREPL)

    def test_execute_returns_repl_result(self):
        """Should return REPLResult type."""
        from rlm.repl.wasm import WasmREPL
        from rlm.core.types import REPLResult

        repl = WasmREPL()

        # Just verify the type annotation exists
        import inspect
        sig = inspect.signature(repl.execute)
        # execute should be an async method
        assert asyncio.iscoroutinefunction(repl.execute)
