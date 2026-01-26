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
- list_sessions: List active REPL sessions
- destroy_session: Destroy a REPL session
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    TextContent,
    Tool,
)

from rlm.core.config import EXECUTION_PROFILES
from rlm.repl.local import LocalREPL

# Default session TTL: 30 minutes
DEFAULT_SESSION_TTL = 30 * 60


@dataclass
class Session:
    """A REPL session with metadata."""

    id: str
    repl: LocalREPL
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Update last access time."""
        self.last_access = time.time()

    def is_expired(self, ttl: float) -> bool:
        """Check if session has expired."""
        return time.time() - self.last_access > ttl


class SessionManager:
    """Manages multiple REPL sessions with TTL-based cleanup."""

    def __init__(self, ttl: float = DEFAULT_SESSION_TTL):
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl
        self._default_session_id = "default"
        # Create default session
        self._sessions[self._default_session_id] = Session(
            id=self._default_session_id,
            repl=LocalREPL(timeout=30),
        )

    def get_or_create(self, session_id: str | None = None) -> Session:
        """Get existing session or create new one."""
        session_id = session_id or self._default_session_id

        # Cleanup expired sessions periodically
        self._cleanup_expired()

        if session_id not in self._sessions:
            self._sessions[session_id] = Session(
                id=session_id,
                repl=LocalREPL(timeout=30),
            )

        session = self._sessions[session_id]
        session.touch()
        return session

    def get(self, session_id: str) -> Session | None:
        """Get session by ID without creating."""
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def destroy(self, session_id: str) -> bool:
        """Destroy a session. Returns True if session existed."""
        if session_id == self._default_session_id:
            # Reset default session instead of destroying
            self._sessions[self._default_session_id] = Session(
                id=self._default_session_id,
                repl=LocalREPL(timeout=30),
            )
            return True
        return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions with metadata."""
        self._cleanup_expired()
        now = time.time()
        return [
            {
                "id": s.id,
                "created_at": s.created_at,
                "last_access": s.last_access,
                "age_seconds": int(now - s.created_at),
                "idle_seconds": int(now - s.last_access),
                "context_keys": list(s.repl.get_context().keys()),
            }
            for s in self._sessions.values()
        ]

    def _cleanup_expired(self) -> None:
        """Remove expired sessions (except default)."""
        expired = [
            sid
            for sid, s in self._sessions.items()
            if sid != self._default_session_id and s.is_expired(self._ttl)
        ]
        for sid in expired:
            del self._sessions[sid]


def create_server() -> Server:
    """Create and configure the MCP server with code sandbox tools."""
    server = Server("rlm-runtime")

    # Session manager for multi-session support
    sessions = SessionManager()

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
                    "Context persists across calls - variables defined remain available. "
                    "Use session_id to maintain separate contexts for different tasks. "
                    "Use profile to set resource limits: quick (5s), default (30s), "
                    "analysis (120s), extended (300s)."
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
                            "description": "Timeout in seconds (overrides profile). Max: 300",
                        },
                        "profile": {
                            "type": "string",
                            "enum": ["quick", "default", "analysis", "extended"],
                            "description": "Execution profile: quick (5s), default (30s), analysis (120s), extended (300s)",
                            "default": "default",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session ID for isolated context (default: 'default')",
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
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID (default: 'default')",
                        },
                    },
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
                        "session_id": {
                            "type": "string",
                            "description": "Session ID (default: 'default')",
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
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID (default: 'default')",
                        },
                    },
                },
            ),
            Tool(
                name="list_sessions",
                description=(
                    "List all active REPL sessions with metadata including "
                    "creation time, last access, and stored variable names."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="destroy_session",
                description=(
                    "Destroy a REPL session and free its resources. "
                    "The 'default' session is reset instead of destroyed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to destroy",
                        },
                    },
                    "required": ["session_id"],
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Handle tool calls."""
        session_id = arguments.get("session_id")

        if name == "execute_python":
            session = sessions.get_or_create(session_id)
            return await _execute_python(session.repl, arguments)

        elif name == "get_repl_context":
            session = sessions.get_or_create(session_id)
            return await _get_repl_context(session.repl)

        elif name == "set_repl_context":
            session = sessions.get_or_create(session_id)
            return await _set_repl_context(session.repl, arguments)

        elif name == "clear_repl_context":
            session = sessions.get_or_create(session_id)
            return await _clear_repl_context(session.repl)

        elif name == "list_sessions":
            return await _list_sessions(sessions)

        elif name == "destroy_session":
            return await _destroy_session(sessions, arguments)

        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )

    return server


async def _execute_python(repl: LocalREPL, arguments: dict[str, Any]) -> CallToolResult:
    """Execute Python code in the sandbox."""
    code = arguments.get("code", "")

    # Determine timeout from profile or explicit value
    profile_name = arguments.get("profile", "default")
    profile = EXECUTION_PROFILES.get(profile_name, EXECUTION_PROFILES["default"])
    timeout = arguments.get("timeout") or profile.timeout
    timeout = min(timeout, 300)  # Cap at 300 seconds (extended profile max)

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


async def _list_sessions(sessions: SessionManager) -> CallToolResult:
    """List all active sessions."""
    session_list = sessions.list_sessions()

    if not session_list:
        return CallToolResult(
            content=[TextContent(type="text", text="No active sessions")],
        )

    lines = [f"Active sessions ({len(session_list)}):"]
    for s in session_list:
        context_info = f", context: {s['context_keys']}" if s["context_keys"] else ""
        lines.append(
            f"  - {s['id']}: idle {s['idle_seconds']}s, age {s['age_seconds']}s{context_info}"
        )

    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(lines))],
    )


async def _destroy_session(
    sessions: SessionManager, arguments: dict[str, Any]
) -> CallToolResult:
    """Destroy a session."""
    session_id = arguments.get("session_id", "")

    if not session_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No session_id provided")],
            isError=True,
        )

    if sessions.destroy(session_id):
        if session_id == "default":
            return CallToolResult(
                content=[TextContent(type="text", text="Default session reset")],
            )
        return CallToolResult(
            content=[TextContent(type="text", text=f"Session '{session_id}' destroyed")],
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Session '{session_id}' not found")],
            isError=True,
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
