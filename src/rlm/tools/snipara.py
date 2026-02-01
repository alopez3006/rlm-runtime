"""Native Snipara tools using HTTP API with OAuth/API key auth.

Provides direct HTTP access to the Snipara API without requiring
the snipara-mcp package. Uses OAuth tokens (preferred) or API keys.

Auth resolution order:
1. OAuth tokens from ~/.snipara/tokens.json
2. SNIPARA_API_KEY environment variable
3. API key from rlm.toml config
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog

from rlm.backends.base import Tool
from rlm.core.exceptions import SniparaAPIError
from rlm.mcp.auth import get_snipara_auth

if TYPE_CHECKING:
    from rlm.core.config import RLMConfig

logger = structlog.get_logger()


class SniparaClient:
    """HTTP client for the Snipara API.

    Resolves auth via get_snipara_auth() which tries:
    1. OAuth tokens from ~/.snipara/tokens.json
    2. SNIPARA_API_KEY environment variable
    3. API key from config

    Args:
        base_url: Snipara API base URL
        project_slug: Project slug
        auth_header: Auth header value ("Bearer <token>" or raw API key)
        timeout: HTTP request timeout in seconds
    """

    def __init__(
        self,
        base_url: str = "https://snipara.com/api/mcp",
        project_slug: str | None = None,
        auth_header: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._project_slug = project_slug
        self._auth_header = auth_header
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_config(cls, config: RLMConfig) -> SniparaClient | None:
        """Create client from RLMConfig, resolving auth automatically.

        Returns None if no auth is available.
        """
        # Try OAuth/env first via auth.py
        auth_header, project_slug = get_snipara_auth()

        # Fall back to config values
        if auth_header is None and config.snipara_api_key:
            auth_header = config.snipara_api_key
        if project_slug is None:
            project_slug = config.snipara_project_slug

        if auth_header is None or project_slug is None:
            return None

        return cls(
            base_url=config.snipara_base_url,
            project_slug=project_slug,
            auth_header=auth_header,
            timeout=30.0,
        )

    @property
    def api_url(self) -> str:
        """Full API URL for this project."""
        return f"{self._base_url}/{self._project_slug}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client."""
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._auth_header:
                if self._auth_header.startswith("Bearer "):
                    headers["Authorization"] = self._auth_header
                else:
                    headers["x-api-key"] = self._auth_header

            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a Snipara API tool endpoint.

        Args:
            tool_name: The tool name (e.g., "rlm_context_query")
            arguments: Tool arguments as a dict

        Returns:
            Parsed JSON response data

        Raises:
            SniparaAPIError: On HTTP errors or API errors
        """
        client = await self._get_client()

        # Strip None values from arguments
        clean_args = {k: v for k, v in arguments.items() if v is not None}

        payload = {
            "tool": tool_name,
            "arguments": clean_args,
        }

        try:
            response = await client.post("/", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            try:
                body = e.response.json()
                message = body.get("error", str(e))
            except Exception:
                message = e.response.text or str(e)

            raise SniparaAPIError(
                tool_name=tool_name,
                status_code=status,
                message=str(message),
            ) from e
        except httpx.TimeoutException as e:
            raise SniparaAPIError(
                tool_name=tool_name,
                status_code=None,
                message=f"Request timed out after {self._timeout}s",
            ) from e
        except httpx.RequestError as e:
            raise SniparaAPIError(
                tool_name=tool_name,
                status_code=None,
                message=f"Request failed: {e}",
            ) from e

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ---------------------------------------------------------------------------
# Tool factory functions
# ---------------------------------------------------------------------------


def get_native_snipara_tools(
    client: SniparaClient,
    memory_enabled: bool = False,
) -> list[Tool]:
    """Create all native Snipara tools using the HTTP client.

    Args:
        client: Configured SniparaClient instance
        memory_enabled: Whether to include memory tools (Tier 2)

    Returns:
        List of Tool instances for registration
    """
    tools: list[Tool] = [
        # Tier 1: Context retrieval
        _create_context_query_tool(client),
        _create_search_tool(client),
        _create_sections_tool(client),
        _create_read_tool(client),
        # Tier 3: Advanced
        _create_shared_context_tool(client),
    ]

    # Tier 2: Memory (gated)
    if memory_enabled:
        tools.extend(
            [
                _create_remember_tool(client),
                _create_recall_tool(client),
                _create_memories_tool(client),
                _create_forget_tool(client),
            ]
        )

    return tools


# ---------------------------------------------------------------------------
# Tier 1: Context retrieval tools
# ---------------------------------------------------------------------------


def _create_context_query_tool(client: SniparaClient) -> Tool:
    """Create the rlm_context_query tool."""

    async def rlm_context_query(
        query: str,
        max_tokens: int = 4000,
        search_mode: str = "hybrid",
        prefer_summaries: bool = False,
        include_metadata: bool = True,
    ) -> Any:
        return await client.call_tool(
            "rlm_context_query",
            {
                "query": query,
                "max_tokens": max_tokens,
                "search_mode": search_mode,
                "prefer_summaries": prefer_summaries,
                "include_metadata": include_metadata,
            },
        )

    return Tool(
        name="rlm_context_query",
        description=(
            "Query optimized context from documentation. Returns ranked sections "
            "within token budget. Use search_mode: keyword, semantic, or hybrid."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Question or topic to search for",
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 4000,
                    "description": "Maximum tokens in response (100-100000)",
                },
                "search_mode": {
                    "type": "string",
                    "enum": ["keyword", "semantic", "hybrid"],
                    "default": "hybrid",
                    "description": "Search mode",
                },
                "prefer_summaries": {
                    "type": "boolean",
                    "default": False,
                    "description": "Prefer summary content over full sections",
                },
                "include_metadata": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include metadata in response",
                },
            },
            "required": ["query"],
        },
        handler=rlm_context_query,
    )


def _create_search_tool(client: SniparaClient) -> Tool:
    """Create the rlm_search tool."""

    async def rlm_search(
        pattern: str,
        max_results: int = 20,
    ) -> Any:
        return await client.call_tool(
            "rlm_search",
            {"pattern": pattern, "max_results": max_results},
        )

    return Tool(
        name="rlm_search",
        description="Search documentation for a regex pattern.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "max_results": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum results to return",
                },
            },
            "required": ["pattern"],
        },
        handler=rlm_search,
    )


def _create_sections_tool(client: SniparaClient) -> Tool:
    """Create the rlm_sections tool."""

    async def rlm_sections(
        filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Any:
        return await client.call_tool(
            "rlm_sections",
            {"filter": filter, "limit": limit, "offset": offset},
        )

    return Tool(
        name="rlm_sections",
        description="List indexed document sections with optional pagination and filtering.",
        parameters={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Filter sections by title prefix (case-insensitive)",
                },
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum sections to return (max: 500)",
                },
                "offset": {
                    "type": "integer",
                    "default": 0,
                    "description": "Number of sections to skip for pagination",
                },
            },
        },
        handler=rlm_sections,
    )


def _create_read_tool(client: SniparaClient) -> Tool:
    """Create the rlm_read tool."""

    async def rlm_read(
        start_line: int,
        end_line: int,
    ) -> Any:
        return await client.call_tool(
            "rlm_read",
            {"start_line": start_line, "end_line": end_line},
        )

    return Tool(
        name="rlm_read",
        description="Read specific lines from documentation.",
        parameters={
            "type": "object",
            "properties": {
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number",
                },
            },
            "required": ["start_line", "end_line"],
        },
        handler=rlm_read,
    )


# ---------------------------------------------------------------------------
# Tier 2: Memory tools (gated by memory_enabled)
# ---------------------------------------------------------------------------


def _create_remember_tool(client: SniparaClient) -> Tool:
    """Create the rlm_remember tool."""

    async def rlm_remember(
        content: str,
        type: str = "fact",
        scope: str = "project",
        category: str | None = None,
        ttl_days: int | None = None,
        related_to: list[str] | None = None,
        document_refs: list[str] | None = None,
    ) -> Any:
        return await client.call_tool(
            "rlm_remember",
            {
                "content": content,
                "type": type,
                "scope": scope,
                "category": category,
                "ttl_days": ttl_days,
                "related_to": related_to,
                "document_refs": document_refs,
            },
        )

    return Tool(
        name="rlm_remember",
        description=(
            "Store a memory for later semantic recall. "
            "Supports types: fact, decision, learning, preference, todo, context."
        ),
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The memory content to store",
                },
                "type": {
                    "type": "string",
                    "enum": ["fact", "decision", "learning", "preference", "todo", "context"],
                    "default": "fact",
                    "description": "Memory type",
                },
                "scope": {
                    "type": "string",
                    "enum": ["agent", "project", "team", "user"],
                    "default": "project",
                    "description": "Memory scope",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category for grouping",
                },
                "ttl_days": {
                    "type": "integer",
                    "description": "Days until expiration (null = permanent)",
                },
                "related_to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of related memories",
                },
                "document_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Referenced document paths",
                },
            },
            "required": ["content"],
        },
        handler=rlm_remember,
    )


def _create_recall_tool(client: SniparaClient) -> Tool:
    """Create the rlm_recall tool."""

    async def rlm_recall(
        query: str,
        limit: int = 5,
        min_relevance: float = 0.5,
        type: str | None = None,
        scope: str | None = None,
        category: str | None = None,
    ) -> Any:
        return await client.call_tool(
            "rlm_recall",
            {
                "query": query,
                "limit": limit,
                "min_relevance": min_relevance,
                "type": type,
                "scope": scope,
                "category": category,
            },
        )

    return Tool(
        name="rlm_recall",
        description=(
            "Semantically recall relevant memories based on a query. "
            "Uses embeddings weighted by confidence decay."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum memories to return",
                },
                "min_relevance": {
                    "type": "number",
                    "default": 0.5,
                    "description": "Minimum relevance score (0-1)",
                },
                "type": {
                    "type": "string",
                    "enum": ["fact", "decision", "learning", "preference", "todo", "context"],
                    "description": "Filter by memory type",
                },
                "scope": {
                    "type": "string",
                    "enum": ["agent", "project", "team", "user"],
                    "description": "Filter by scope",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category",
                },
            },
            "required": ["query"],
        },
        handler=rlm_recall,
    )


def _create_memories_tool(client: SniparaClient) -> Tool:
    """Create the rlm_memories tool."""

    async def rlm_memories(
        type: str | None = None,
        scope: str | None = None,
        category: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Any:
        return await client.call_tool(
            "rlm_memories",
            {
                "type": type,
                "scope": scope,
                "category": category,
                "search": search,
                "limit": limit,
                "offset": offset,
            },
        )

    return Tool(
        name="rlm_memories",
        description="List memories with optional filters.",
        parameters={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["fact", "decision", "learning", "preference", "todo", "context"],
                    "description": "Filter by memory type",
                },
                "scope": {
                    "type": "string",
                    "enum": ["agent", "project", "team", "user"],
                    "description": "Filter by scope",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category",
                },
                "search": {
                    "type": "string",
                    "description": "Text search in content",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum memories to return",
                },
                "offset": {
                    "type": "integer",
                    "default": 0,
                    "description": "Number to skip for pagination",
                },
            },
        },
        handler=rlm_memories,
    )


def _create_forget_tool(client: SniparaClient) -> Tool:
    """Create the rlm_forget tool."""

    async def rlm_forget(
        memory_id: str | None = None,
        type: str | None = None,
        category: str | None = None,
        older_than_days: int | None = None,
    ) -> Any:
        return await client.call_tool(
            "rlm_forget",
            {
                "memory_id": memory_id,
                "type": type,
                "category": category,
                "older_than_days": older_than_days,
            },
        )

    return Tool(
        name="rlm_forget",
        description="Delete memories by ID or filter criteria.",
        parameters={
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "Specific memory ID to delete",
                },
                "type": {
                    "type": "string",
                    "enum": ["fact", "decision", "learning", "preference", "todo", "context"],
                    "description": "Delete all of this type",
                },
                "category": {
                    "type": "string",
                    "description": "Delete all in this category",
                },
                "older_than_days": {
                    "type": "integer",
                    "description": "Delete memories older than N days",
                },
            },
        },
        handler=rlm_forget,
    )


# ---------------------------------------------------------------------------
# Tier 3: Advanced tools
# ---------------------------------------------------------------------------


def _create_shared_context_tool(client: SniparaClient) -> Tool:
    """Create the rlm_shared_context tool."""

    async def rlm_shared_context(
        categories: list[str] | None = None,
        max_tokens: int = 4000,
        include_content: bool = True,
    ) -> Any:
        return await client.call_tool(
            "rlm_shared_context",
            {
                "categories": categories,
                "max_tokens": max_tokens,
                "include_content": include_content,
            },
        )

    return Tool(
        name="rlm_shared_context",
        description=(
            "Get merged context from linked shared collections. "
            "Returns categorized docs with budget allocation. "
            "Categories: MANDATORY, BEST_PRACTICES, GUIDELINES, REFERENCE."
        ),
        parameters={
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["MANDATORY", "BEST_PRACTICES", "GUIDELINES", "REFERENCE"],
                    },
                    "description": "Filter by categories (default: all)",
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 4000,
                    "description": "Maximum tokens in response (100-100000)",
                },
                "include_content": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include merged content",
                },
            },
        },
        handler=rlm_shared_context,
    )
