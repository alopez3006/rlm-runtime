"""MCP Server implementation for RLM Runtime.

This module provides an MCP (Model Context Protocol) server that exposes
a sandboxed Python execution environment to Claude Desktop, Claude Code,
and other MCP clients.

Zero API keys required - designed to work within Claude Code's billing.
For Snipara context retrieval, use snipara-mcp separately (with OAuth).

Tools provided:
- execute_python: Run Python code in a sandboxed environment
- get_repl_context: Get the current REPL context
- set_repl_context: Set variables in the REPL context
- clear_repl_context: Clear the REPL context
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    TextContent,
    Tool,
)

from rlm.repl.local import LocalREPL


def create_server() -> Server:
    """Create and configure the MCP server with code sandbox tools."""
    server = Server("rlm-runtime")

    # Shared REPL state - persists across tool calls
    repl = LocalREPL(timeout=30)

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[Tool]:
        """List available RLM tools."""
        return [
            Tool(
                name="execute_python",
                description=(
                    "Execute Python code in a sandboxed environment with RestrictedPython. "
                    "Safe for math, data processing, and algorithm work. "
                    "Allowed imports: json, re, math, datetime, collections, itertools, "
                    "functools, operator, string, random, hashlib, base64, urllib.parse. "
                    "Blocked: os, subprocess, socket, file I/O, network access. "
                    "Use 'result = <value>' to return a value. Use print() for output. "
                    "Context persists across calls - variables defined remain available."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default: 30, max: 60)",
                            "default": 30,
                        },
                    },
                    "required": ["code"],
                },
            ),
            Tool(
                name="get_repl_context",
                description=(
                    "Get the current REPL context. Returns all variables stored "
                    "in the persistent execution context from previous execute_python calls."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="set_repl_context",
                description=(
                    "Set a variable in the REPL context. The variable will persist "
                    "across multiple execute_python calls. Value should be JSON-encoded."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Variable name",
                        },
                        "value": {
                            "type": "string",
                            "description": "JSON-encoded value to store",
                        },
                    },
                    "required": ["key", "value"],
                },
            ),
            Tool(
                name="clear_repl_context",
                description="Clear all variables from the REPL context and reset to clean state.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Handle tool calls."""

        if name == "execute_python":
            return await _execute_python(repl, arguments)

        elif name == "get_repl_context":
            return await _get_repl_context(repl)

        elif name == "set_repl_context":
            return await _set_repl_context(repl, arguments)

        elif name == "clear_repl_context":
            return await _clear_repl_context(repl)

        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )

    return server


async def _execute_python(repl: LocalREPL, arguments: dict[str, Any]) -> CallToolResult:
    """Execute Python code in the sandbox."""
    code = arguments.get("code", "")
    timeout = min(arguments.get("timeout", 30), 60)  # Cap at 60 seconds

    if not code.strip():
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No code provided")],
            isError=True,
        )

    result = await repl.execute(code, timeout=timeout)

    if result.success:
        output = result.output or "(no output)"
        if result.truncated:
            output += "\n... (output truncated)"
        return CallToolResult(
            content=[TextContent(type="text", text=output)],
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {result.error}")],
            isError=True,
        )


async def _get_repl_context(repl: LocalREPL) -> CallToolResult:
    """Get the current REPL context."""
    context = repl.get_context()

    if not context:
        return CallToolResult(
            content=[TextContent(type="text", text="Context is empty")],
        )

    # Format context as readable output
    lines = ["Current REPL context:"]
    for key, value in context.items():
        try:
            value_str = json.dumps(value, indent=2, default=str)
        except (TypeError, ValueError):
            value_str = repr(value)
        lines.append(f"  {key} = {value_str}")

    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
    )


async def _set_repl_context(repl: LocalREPL, arguments: dict[str, Any]) -> CallToolResult:
    """Set a variable in the REPL context."""
    key = arguments.get("key", "")
    value_str = arguments.get("value", "")

    if not key:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No key provided")],
            isError=True,
        )

    try:
        value = json.loads(value_str)
    except json.JSONDecodeError:
        # If not valid JSON, store as string
        value = value_str

    repl.set_context(key, value)

    return CallToolResult(
        content=[TextContent(type="text", text=f"Set context['{key}'] = {repr(value)}")],
    )


async def _clear_repl_context(repl: LocalREPL) -> CallToolResult:
    """Clear the REPL context."""
    repl.clear_context()
    return CallToolResult(
        content=[TextContent(type="text", text="REPL context cleared")],
    )


def run_server() -> None:
    """Run the MCP server using stdio transport."""
    server = create_server()

    async def main() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(main())


if __name__ == "__main__":
    run_server()
