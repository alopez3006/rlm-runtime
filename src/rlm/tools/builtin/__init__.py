"""Builtin tools for RLM runtime."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rlm.backends.base import Tool

if TYPE_CHECKING:
    from rlm.repl.base import BaseREPL


def get_builtin_tools(repl: BaseREPL) -> list[Tool]:
    """Get builtin tools with the given REPL instance.

    Args:
        repl: REPL instance for code execution

    Returns:
        List of builtin tools
    """
    return [
        _create_execute_code_tool(repl),
        _create_file_read_tool(),
        _create_list_files_tool(),
    ]


def _create_execute_code_tool(repl: BaseREPL) -> Tool:
    """Create the execute_code tool."""

    async def execute_code(code: str) -> dict[str, Any]:
        """Execute Python code in the sandboxed REPL.

        Use this tool when you need to:
        - Perform calculations or data processing
        - Parse and analyze files
        - Transform data formats
        - Run algorithms

        The code runs in a restricted environment with limited imports.
        Use the 'result' variable to return a value.

        Args:
            code: Python code to execute

        Returns:
            Dictionary with output, error (if any), and execution time
        """
        result = await repl.execute(code)
        return {
            "output": result.output,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
            "success": result.success,
        }

    return Tool(
        name="execute_code",
        description=(
            "Execute Python code in a sandboxed REPL environment. "
            "Use for calculations, data processing, file parsing, and algorithms. "
            "Set the 'result' variable to return a value. "
            "Available modules: json, re, math, datetime, collections, itertools, csv, statistics."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Use 'result = ...' to return a value.",
                }
            },
            "required": ["code"],
        },
        handler=execute_code,
    )


def _create_file_read_tool() -> Tool:
    """Create the file_read tool."""

    async def file_read(
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
        max_lines: int = 100,
    ) -> dict[str, Any]:
        """Read contents of a file.

        Args:
            path: Path to the file to read
            start_line: Line number to start from (1-indexed)
            end_line: Optional line number to end at (inclusive)
            max_lines: Maximum number of lines to return

        Returns:
            Dictionary with file content and metadata
        """
        file_path = Path(path).resolve()

        if not file_path.exists():
            return {"error": f"File not found: {path}", "content": None}

        if not file_path.is_file():
            return {"error": f"Not a file: {path}", "content": None}

        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start_idx = max(0, start_line - 1)
            end_idx = end_line if end_line else start_idx + max_lines
            end_idx = min(end_idx, start_idx + max_lines, total_lines)

            selected_lines = lines[start_idx:end_idx]
            content = "".join(selected_lines)

            return {
                "content": content,
                "path": str(file_path),
                "start_line": start_idx + 1,
                "end_line": end_idx,
                "total_lines": total_lines,
                "truncated": end_idx < total_lines,
            }

        except Exception as e:
            return {"error": f"Error reading file: {e}", "content": None}

    return Tool(
        name="file_read",
        description=(
            "Read the contents of a file. "
            "Returns the content along with line numbers and file metadata. "
            "Use start_line and end_line to read specific portions of large files."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
                "start_line": {
                    "type": "integer",
                    "default": 1,
                    "description": "Line number to start reading from (1-indexed)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional line number to stop reading at (inclusive)",
                },
                "max_lines": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum number of lines to return",
                },
            },
            "required": ["path"],
        },
        handler=file_read,
    )


def _create_list_files_tool() -> Tool:
    """Create the list_files tool."""

    async def list_files(
        path: str = ".",
        pattern: str = "*",
        recursive: bool = False,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """List files in a directory.

        Args:
            path: Directory path to list
            pattern: Glob pattern to filter files (e.g., "*.py", "*.md")
            recursive: Whether to search recursively
            max_results: Maximum number of results to return

        Returns:
            Dictionary with list of files and metadata
        """
        dir_path = Path(path).resolve()

        if not dir_path.exists():
            return {"error": f"Path not found: {path}", "files": []}

        if not dir_path.is_dir():
            return {"error": f"Not a directory: {path}", "files": []}

        try:
            if recursive:
                matches = list(dir_path.rglob(pattern))
            else:
                matches = list(dir_path.glob(pattern))

            # Sort by path and limit results
            matches = sorted(matches)[:max_results]

            files = []
            for match in matches:
                try:
                    stat = match.stat()
                    files.append({
                        "path": str(match),
                        "name": match.name,
                        "is_dir": match.is_dir(),
                        "size": stat.st_size if match.is_file() else None,
                    })
                except (OSError, PermissionError):
                    files.append({
                        "path": str(match),
                        "name": match.name,
                        "is_dir": match.is_dir(),
                        "size": None,
                    })

            return {
                "files": files,
                "count": len(files),
                "truncated": len(matches) >= max_results,
                "directory": str(dir_path),
            }

        except Exception as e:
            return {"error": f"Error listing files: {e}", "files": []}

    return Tool(
        name="list_files",
        description=(
            "List files in a directory with optional glob pattern filtering. "
            "Use recursive=true to search subdirectories. "
            "Returns file paths, names, sizes, and whether each is a directory."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Directory path to list",
                },
                "pattern": {
                    "type": "string",
                    "default": "*",
                    "description": "Glob pattern to filter files (e.g., '*.py', '*.md')",
                },
                "recursive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Search subdirectories recursively",
                },
                "max_results": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum number of files to return",
                },
            },
        },
        handler=list_files,
    )


def register(registry: Any) -> None:
    """Entry point for tool discovery.

    This function is called by the plugin system to register builtin tools.
    """
    # This is a placeholder - actual registration happens in orchestrator
    # because we need the REPL instance
    pass
