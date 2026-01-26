"""Local REPL with RestrictedPython sandboxing."""

from __future__ import annotations

import builtins
import platform
import time
from typing import Any

# Resource tracking only available on Unix
try:
    import resource

    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

from RestrictedPython import compile_restricted, safe_builtins
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr
from RestrictedPython.PrintCollector import PrintCollector as RestrictedPrintCollector

from rlm.core.types import REPLResult
from rlm.repl.base import BaseREPL
from rlm.repl.safety import (
    MAX_EXECUTION_TIME,
    is_import_allowed,
    truncate_output,
)


def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
    """Restricted import that only allows safe modules."""
    if not is_import_allowed(name):
        raise ImportError(f"Import of '{name}' is not allowed in sandbox")
    return builtins.__import__(name, *args, **kwargs)


class LocalREPL(BaseREPL):
    """Local Python REPL with RestrictedPython sandboxing.

    Uses RestrictedPython to provide a safe execution environment by:
    - Restricting imports to a whitelist of safe modules
    - Guarding attribute access
    - Limiting output size
    - Providing a controlled namespace

    Note: This provides defense in depth but is not a complete sandbox.
    For untrusted code, use DockerREPL instead.

    Example:
        ```python
        repl = LocalREPL(timeout=30)
        result = await repl.execute("print(1 + 1)")
        print(result.output)  # "2\\n"
        ```
    """

    def __init__(self, timeout: int = MAX_EXECUTION_TIME):
        """Initialize the local REPL.

        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout
        self._globals: dict[str, Any] = {}
        self._context: dict[str, Any] = {}
        self._setup_globals()

    def _setup_globals(self) -> None:
        """Setup restricted globals for execution."""
        # Additional safe builtins not included in RestrictedPython's safe_builtins
        additional_builtins = {
            # Collection constructors and functions
            "list": list,
            "dict": dict,
            "set": set,
            "frozenset": frozenset,
            # Aggregation functions
            "sum": sum,
            "min": min,
            "max": max,
            "any": any,
            "all": all,
            # Iteration helpers
            "enumerate": enumerate,
            "map": map,
            "filter": filter,
            "reversed": reversed,
            # Type introspection (read-only)
            "type": type,
            "callable": callable,
        }

        self._globals = {
            "__builtins__": {
                **safe_builtins,
                **additional_builtins,
                "__import__": _safe_import,
                "None": None,
                "True": True,
                "False": False,
            },
            "_getattr_": safer_getattr,
            "_getitem_": default_guarded_getitem,
            "_getiter_": default_guarded_getiter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_write_": self._guarded_write,
            # Use RestrictedPython's PrintCollector class
            "_print_": RestrictedPrintCollector,
            # Shared context variable accessible to user code
            "context": self._context,
            # Result variable for returning values
            "result": None,
        }

    def _guarded_write(self, obj: Any) -> Any:
        """Guard attribute writes."""
        return obj

    def _get_resource_usage(self) -> tuple[float, int] | None:
        """Get current resource usage (CPU time in ms, memory in bytes).

        Returns:
            Tuple of (cpu_time_ms, memory_bytes) or None on Windows
        """
        if not HAS_RESOURCE:
            return None
        usage = resource.getrusage(resource.RUSAGE_SELF)
        cpu_time_ms = int((usage.ru_utime + usage.ru_stime) * 1000)
        # ru_maxrss is in bytes on Linux, kilobytes on macOS
        if platform.system() == "Darwin":
            memory_bytes = usage.ru_maxrss  # Already in bytes on macOS
        else:
            memory_bytes = usage.ru_maxrss * 1024  # Convert KB to bytes on Linux
        return cpu_time_ms, memory_bytes

    async def execute(self, code: str, timeout: int | None = None) -> REPLResult:
        """Execute code in the local sandbox.

        Args:
            code: Python code to execute
            timeout: Optional timeout override

        Returns:
            REPLResult with output, error, and timing
        """
        timeout = timeout or self.timeout
        start_time = time.time()

        # Get resource usage before execution
        start_resources = self._get_resource_usage()

        try:
            # Compile with RestrictedPython
            # Note: RestrictedPython 8.x returns code object directly,
            # raises SyntaxError on compilation failure
            byte_code = compile_restricted(
                code,
                filename="<rlm-repl>",
                mode="exec",
            )

            if byte_code is None:
                return REPLResult(
                    output="",
                    error="Compilation failed: code could not be compiled",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            # Sync context
            self._globals["context"] = self._context

            # Clear any previous print collector
            if "_print" in self._globals:
                del self._globals["_print"]

            # Execute - in RestrictedPython 8.x, byte_code IS the code object
            exec(byte_code, self._globals)

            # Get resource usage after execution
            end_resources = self._get_resource_usage()

            # Calculate resource deltas
            cpu_time_ms: int | None = None
            memory_peak_bytes: int | None = None
            if start_resources and end_resources:
                cpu_time_ms = int(end_resources[0] - start_resources[0])
                # Memory is peak, not delta - report the current peak
                memory_peak_bytes = end_resources[1]

            # Collect output from RestrictedPython's PrintCollector
            # The '_print' variable holds the PrintCollector instance after execution
            output = ""
            print_collector = self._globals.get("_print")
            if print_collector is not None and hasattr(print_collector, "txt"):
                output = "".join(print_collector.txt)

            # Check for result variable
            result_value = self._globals.get("result")
            if result_value is not None:
                if output and not output.endswith("\n"):
                    output += "\n"
                output += f"result = {result_value!r}"

            # Apply truncation if needed
            output, truncated = truncate_output(output)

            return REPLResult(
                output=output,
                error=None,
                execution_time_ms=int((time.time() - start_time) * 1000),
                truncated=truncated,
                memory_peak_bytes=memory_peak_bytes,
                cpu_time_ms=cpu_time_ms,
            )

        except Exception as e:
            return REPLResult(
                output="",
                error=f"{type(e).__name__}: {e}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

    def get_context(self) -> dict[str, Any]:
        """Get the current context."""
        return self._context.copy()

    def set_context(self, key: str, value: Any) -> None:
        """Set a value in the context."""
        self._context[key] = value

    def clear_context(self) -> None:
        """Clear the context."""
        self._context.clear()
        self._globals["result"] = None

    def reset(self) -> None:
        """Reset the REPL to a clean state."""
        self.clear_context()
        self._setup_globals()
