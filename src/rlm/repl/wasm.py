"""WebAssembly REPL using Pyodide for browser-safe execution.

This module provides a sandboxed Python execution environment that runs
in WebAssembly using Pyodide. It's suitable for browser environments
and provides strong isolation without Docker.

Note: This REPL requires the 'pyodide' package to be installed.
Install with: pip install pyodide-py

Example:
    ```python
    from rlm.repl.wasm import WasmREPL

    repl = WasmREPL()
    result = await repl.execute("print(2 + 2)")
    print(result.output)  # "4"
    ```
"""

from __future__ import annotations

import asyncio
from typing import Any

from rlm.core.types import REPLResult
from rlm.repl.base import BaseREPL


class WasmREPL(BaseREPL):
    """WebAssembly-based Python REPL using Pyodide.

    Provides sandboxed Python execution in a WebAssembly environment.
    This is browser-safe and provides strong isolation without containers.

    Features:
    - Runs Python in WebAssembly sandbox
    - No filesystem or network access by default
    - Pre-installed scientific packages (numpy, pandas, etc.)
    - Persistent context across executions

    Limitations:
    - Some Python packages may not be available
    - I/O operations are limited
    - Startup time is longer than LocalREPL
    """

    def __init__(
        self,
        timeout: int = 30,
        packages: list[str] | None = None,
        allow_top_level_await: bool = True,
    ):
        """Initialize the WebAssembly REPL.

        Args:
            timeout: Maximum execution time in seconds
            packages: Additional packages to install (micropip)
            allow_top_level_await: Allow top-level await in code
        """
        self.timeout = timeout
        self.packages = packages or []
        self.allow_top_level_await = allow_top_level_await
        self._pyodide: Any | None = None
        self._context: dict[str, Any] = {}

    async def _ensure_pyodide(self) -> Any:
        """Ensure Pyodide runtime is initialized."""
        if self._pyodide is not None:
            return self._pyodide

        try:
            from pyodide import loadPyodide  # type: ignore[attr-defined]  # noqa: N813
        except ImportError:
            # Try alternative import for different pyodide versions
            try:
                import pyodide_py as pyodide
                loadPyodide = pyodide.loadPyodide  # noqa: N806
            except ImportError:
                raise ImportError(
                    "Pyodide not installed. Install with: pip install pyodide-py\n"
                    "Or use in browser with: <script src='https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js'></script>"
                ) from None

        # Load Pyodide runtime
        self._pyodide = await loadPyodide()

        # Install additional packages if specified
        if self.packages:
            await self._pyodide.loadPackagesFromImports(self.packages)

        return self._pyodide

    async def execute(self, code: str, timeout: int | None = None) -> REPLResult:
        """Execute Python code in the WebAssembly sandbox.

        Args:
            code: Python code to execute
            timeout: Optional timeout in seconds (not implemented for WASM)

        Returns:
            REPLResult with output, any errors, and execution time
        """
        # Note: timeout is not currently implemented for WASM execution
        _ = timeout  # Unused for now
        import time

        start_time = time.time()
        output_lines: list[str] = []

        try:
            pyodide = await asyncio.wait_for(
                self._ensure_pyodide(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            return REPLResult(
                output="",
                error=f"Pyodide initialization timed out after {self.timeout}s",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except ImportError as e:
            return REPLResult(
                output="",
                error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        try:
            # Set up output capture
            capture_code = """
import sys
from io import StringIO
_stdout = sys.stdout
_stderr = sys.stderr
_captured_stdout = StringIO()
_captured_stderr = StringIO()
sys.stdout = _captured_stdout
sys.stderr = _captured_stderr
"""
            pyodide.runPython(capture_code)

            # Execute user code with timeout
            try:
                if self.allow_top_level_await:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(pyodide.runPythonAsync, code),
                        timeout=self.timeout,
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(pyodide.runPython, code),
                        timeout=self.timeout,
                    )
            except asyncio.TimeoutError:
                # Restore stdout/stderr before returning
                pyodide.runPython("sys.stdout = _stdout; sys.stderr = _stderr")
                return REPLResult(
                    output="",
                    error=f"Execution timed out after {self.timeout}s",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            # Capture output
            restore_code = """
sys.stdout = _stdout
sys.stderr = _stderr
_output = _captured_stdout.getvalue()
_errors = _captured_stderr.getvalue()
"""
            pyodide.runPython(restore_code)

            stdout_output = pyodide.globals.get("_output", "")
            stderr_output = pyodide.globals.get("_errors", "")

            # Build output
            if stdout_output:
                output_lines.append(stdout_output.rstrip())

            if result is not None:
                # Convert Pyodide proxy to Python object if needed
                try:
                    result_str = str(result)
                    if result_str and result_str != "None":
                        output_lines.append(f"result = {result_str}")
                except Exception:
                    pass

            output = "\n".join(output_lines)

            # Truncate if too long
            max_output = 100_000
            truncated = False
            if len(output) > max_output:
                output = output[:max_output] + "\n... (output truncated)"
                truncated = True

            execution_time_ms = int((time.time() - start_time) * 1000)

            if stderr_output:
                return REPLResult(
                    output=output,
                    error=stderr_output,
                    execution_time_ms=execution_time_ms,
                    truncated=truncated,
                )

            return REPLResult(
                output=output,
                error=None,
                execution_time_ms=execution_time_ms,
                truncated=truncated,
            )

        except Exception as e:
            # Try to restore stdout/stderr
            try:
                pyodide.runPython("sys.stdout = _stdout; sys.stderr = _stderr")
            except Exception:
                pass

            execution_time_ms = int((time.time() - start_time) * 1000)
            return REPLResult(
                output="\n".join(output_lines),
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def reset(self) -> None:
        """Reset the REPL state.

        This clears any variables and resets the execution context.
        """
        self._context.clear()
        if self._pyodide is not None:
            try:
                # Clear user-defined variables
                self._pyodide.runPython("""
for _name in list(globals().keys()):
    if not _name.startswith('_'):
        del globals()[_name]
""")
            except Exception:
                pass

    async def install_package(self, package: str) -> dict[str, Any]:
        """Install a pure-Python package using micropip.

        This uses Pyodide's micropip to install packages from PyPI.
        Only pure-Python packages (no C extensions) can be installed.

        Args:
            package: Package name to install (can include version: "requests>=2.28")

        Returns:
            Dict with 'success' boolean and 'message' or 'error'

        Example:
            >>> result = await repl.install_package("requests")
            >>> print(result)
            {'success': True, 'message': 'Installed requests'}
        """
        try:
            pyodide = await self._ensure_pyodide()

            # First try to load if it's a pre-bundled package (numpy, pandas, etc.)
            try:
                await pyodide.loadPackagesFromImports([package.split(">=")[0].split("==")[0]])
                return {
                    "success": True,
                    "message": f"Loaded bundled package: {package}",
                }
            except Exception:
                pass  # Not bundled, try micropip

            # Use micropip for pure-Python packages
            install_code = f"""
import micropip
await micropip.install("{package}")
"""
            await pyodide.runPythonAsync(install_code)
            return {
                "success": True,
                "message": f"Installed {package} via micropip",
            }

        except Exception as e:
            error_msg = str(e)
            # Provide helpful error messages
            if "C extension" in error_msg or "binary" in error_msg.lower():
                return {
                    "success": False,
                    "error": f"Cannot install {package}: requires C extensions (not supported in WASM)",
                }
            return {
                "success": False,
                "error": f"Failed to install {package}: {error_msg}",
            }

    async def list_installed_packages(self) -> list[str]:
        """List packages installed in the Pyodide environment.

        Returns:
            List of installed package names
        """
        try:
            pyodide = await self._ensure_pyodide()
            result = pyodide.runPython("""
import micropip
list(micropip.list().keys())
""")
            return list(result.to_py()) if hasattr(result, "to_py") else list(result)
        except Exception:
            return []

    def get_context(self) -> dict[str, Any]:
        """Get the current shared context.

        Returns:
            Current context dictionary
        """
        return self._context.copy()

    def set_context(self, key: str, value: Any) -> None:
        """Set a value in the shared context.

        Args:
            key: Context key
            value: Value to store
        """
        self._context[key] = value

    def clear_context(self) -> None:
        """Clear all values from the shared context."""
        self._context.clear()

    @property
    def environment_name(self) -> str:
        """Return the environment name."""
        return "wasm"
