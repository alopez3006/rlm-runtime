"""Native Snipara tools using HTTP API with OAuth/API key auth.

This module provides direct HTTP access to the Snipara context retrieval
and memory API without requiring the ``snipara-mcp`` package as a runtime
dependency.  It uses ``httpx`` (already a core dependency) to call the
Snipara REST endpoint at ``/api/mcp/{project_slug}``.

Architecture
~~~~~~~~~~~~

::

    Orchestrator._register_snipara_tools()
        │
        ├─ Attempt 1: Native (this module)
        │   SniparaClient.from_config(config)
        │       → resolves auth automatically
        │       → returns None when no credentials found
        │   get_native_snipara_tools(client, memory_enabled)
        │       → returns 5 tools (Tiers 1+3) or 9 tools (all tiers)
        │
        └─ Attempt 2: snipara-mcp package (backward compat fallback)
            from snipara_mcp.rlm_tools import get_snipara_tools

Auth Resolution Order
~~~~~~~~~~~~~~~~~~~~~

Credentials are resolved top-down; the first match wins:

1. **OAuth tokens** from ``~/.snipara/tokens.json`` — obtained via
   ``snipara-mcp-login`` (browser-based OAuth Device Flow).  Returned as
   ``"Bearer <access_token>"`` by ``get_snipara_auth()``.  No API key
   copying needed.
2. **SNIPARA_API_KEY** environment variable — for open-source or
   non-Snipara users who prefer plain API keys.
3. **snipara_api_key** field in ``rlm.toml`` config — last resort
   static configuration.

If none of the above are available, ``SniparaClient.from_config()``
returns ``None`` and the orchestrator falls through to the
``snipara-mcp`` package fallback.

Tool Tiers
~~~~~~~~~~

Tools are organised in three tiers to control what the LLM can access:

* **Tier 1 — Context retrieval** (always registered):
  ``rlm_context_query``, ``rlm_search``, ``rlm_sections``, ``rlm_read``
* **Tier 2 — Memory** (gated by ``config.memory_enabled``):
  ``rlm_remember``, ``rlm_recall``, ``rlm_memories``, ``rlm_forget``
* **Tier 3 — Advanced** (always registered):
  ``rlm_shared_context``

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

The following env vars influence behaviour (all optional):

* ``SNIPARA_API_KEY`` — raw API key used when OAuth is unavailable
* ``SNIPARA_PROJECT_SLUG`` — project slug for URL construction
* ``RLM_SNIPARA_BASE_URL`` — override the default API base URL
  (default: ``https://api.snipara.com/mcp``)
* ``RLM_MEMORY_ENABLED`` — set to ``true`` to register Tier 2 memory
  tools

Example
~~~~~~~

::

    from rlm.tools.snipara import SniparaClient, get_native_snipara_tools

    client = SniparaClient.from_config(config)
    if client is not None:
        tools = get_native_snipara_tools(client, memory_enabled=True)
        for tool in tools:
            registry.register(tool)
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
    """Async HTTP client for the Snipara REST API.

    This client wraps ``httpx.AsyncClient`` and provides a single
    ``call_tool()`` method that POSTs JSON payloads to the Snipara MCP
    endpoint.  It handles:

    * **Auth header selection** — ``Authorization: Bearer <token>`` for
      OAuth tokens (prefixed with ``"Bearer "``), or ``x-api-key: <key>``
      for raw API keys.
    * **Lazy client creation** — the underlying ``httpx.AsyncClient`` is
      instantiated on the first ``call_tool()`` invocation, avoiding event
      loop issues when the orchestrator constructs tools synchronously
      during ``__init__``.
    * **None-stripping** — ``None`` values in tool arguments are
      automatically removed before sending the request, matching the MCP
      server's expectation.

    The recommended way to create a client is via the ``from_config()``
    classmethod which automatically resolves credentials:

    ::

        client = SniparaClient.from_config(config)  # None if no auth
        if client:
            result = await client.call_tool("rlm_context_query", {"query": "..."})

    For testing or advanced use, you can instantiate directly:

    ::

        client = SniparaClient(
            base_url="https://api.snipara.com/mcp",
            project_slug="my-project",
            auth_header="Bearer eyJ...",
        )

    Args:
        base_url: Snipara API base URL.  Trailing slashes are stripped.
            Default: ``https://api.snipara.com/mcp``.  Override via
            ``RLM_SNIPARA_BASE_URL`` env var or ``snipara_base_url`` in
            ``rlm.toml``.
        project_slug: Snipara project slug used to construct the full
            endpoint URL (``{base_url}/{project_slug}``).
        auth_header: The raw auth value.  If it starts with
            ``"Bearer "``, it is sent as an ``Authorization`` header;
            otherwise it is sent as an ``x-api-key`` header.
        timeout: HTTP request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        base_url: str = "https://api.snipara.com/mcp",
        project_slug: str | None = None,
        auth_header: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._project_slug = project_slug
        self._auth_header = auth_header
        self._timeout = timeout
        # Lazy-initialised in _get_client() to avoid event-loop issues
        # when the orchestrator builds tools during synchronous __init__.
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_config(cls, config: RLMConfig) -> SniparaClient | None:
        """Create a client by resolving auth from all available sources.

        Resolution order:

        1. ``get_snipara_auth()`` — checks OAuth tokens at
           ``~/.snipara/tokens.json``, then ``SNIPARA_API_KEY`` env var.
        2. ``config.snipara_api_key`` — static key from ``rlm.toml``
           or ``RLM_SNIPARA_API_KEY`` env var (via pydantic-settings).
        3. ``config.snipara_project_slug`` — project slug from config
           or ``SNIPARA_PROJECT_SLUG`` env var.

        Both ``auth_header`` and ``project_slug`` are required.  If
        either is missing after trying all sources, returns ``None``
        to signal that native tools are unavailable (the orchestrator
        will fall back to the ``snipara-mcp`` package).

        Args:
            config: The RLMConfig instance (carries env var overrides).

        Returns:
            A configured ``SniparaClient``, or ``None`` if credentials
            could not be resolved.
        """
        # Step 1: Try OAuth tokens / SNIPARA_API_KEY env via auth.py
        auth_header, project_slug = get_snipara_auth()

        # Step 2: Fall back to rlm.toml / pydantic-settings values
        if auth_header is None and config.snipara_api_key:
            auth_header = config.snipara_api_key
        if project_slug is None:
            project_slug = config.snipara_project_slug

        # Both are required to construct the API URL and authenticate
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
        """Get or lazily create the ``httpx.AsyncClient``.

        The client is created on first call (not in ``__init__``) to
        avoid binding to an event loop that may not exist yet when the
        orchestrator is constructing tools synchronously.

        Auth header logic:
        - If ``_auth_header`` starts with ``"Bearer "``, it's an OAuth
          access token → sent as ``Authorization: Bearer <token>``.
        - Otherwise it's a raw API key → sent as ``x-api-key: <key>``.

        The client is created *without* a ``base_url``; callers pass
        the full ``api_url`` to each request.  This avoids trailing-slash
        redirects (HTTP 307) that can strip authentication headers.

        Returns:
            The shared ``httpx.AsyncClient`` instance.
        """
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._auth_header:
                # OAuth tokens arrive as "Bearer <token>" from auth.py;
                # raw API keys are plain strings without the prefix.
                if self._auth_header.startswith("Bearer "):
                    headers["Authorization"] = self._auth_header
                else:
                    headers["x-api-key"] = self._auth_header

            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a Snipara MCP tool endpoint via HTTP POST (JSON-RPC 2.0).

        Sends a JSON-RPC payload to ``POST {api_url}`` with the structure::

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "rlm_context_query",
                    "arguments": {"query": "...", "max_tokens": 4000}
                }
            }

        ``None`` values in *arguments* are stripped before sending —
        the Snipara API treats absent keys as "use default", which
        matches the MCP server's behaviour.

        Args:
            tool_name: Snipara tool name (e.g., ``"rlm_context_query"``).
            arguments: Keyword arguments for the tool.  ``None`` values
                are automatically removed.

        Returns:
            The parsed JSON response from the API.  For tool results
            containing text content, the text is parsed as JSON.

        Raises:
            SniparaAPIError: On any HTTP error (4xx/5xx), timeout,
                or connection failure.  The ``status_code`` attribute is
                set for HTTP errors; it is ``None`` for timeouts and
                connection errors.
        """
        client = await self._get_client()

        # Strip None values — the API treats absent keys as defaults.
        clean_args = {k: v for k, v in arguments.items() if v is not None}

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": clean_args,
            },
        }

        try:
            response = await client.post(self.api_url, json=payload)
            response.raise_for_status()
            data = response.json()

            # Parse JSON-RPC response
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                raise SniparaAPIError(
                    tool_name=tool_name,
                    status_code=None,
                    message=f"JSON-RPC error: {error_msg}",
                )

            # Extract result — MCP tools return content blocks
            rpc_result = data.get("result", {})
            content = rpc_result.get("content", [])
            if content and content[0].get("type") == "text":
                import json as _json

                try:
                    return _json.loads(content[0].get("text", "{}"))
                except _json.JSONDecodeError:
                    return content[0].get("text", "")

            return rpc_result
        except httpx.HTTPStatusError as e:
            # Extract a human-readable message from the response body
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
        """Close the underlying ``httpx.AsyncClient`` and release resources.

        Safe to call multiple times or if the client was never opened.
        """
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ---------------------------------------------------------------------------
# Tool factory functions
# ---------------------------------------------------------------------------


def get_native_snipara_tools(
    client: SniparaClient,
    memory_enabled: bool = False,
) -> list[Tool]:
    """Create all native Snipara tools bound to a ``SniparaClient``.

    Each tool is a ``Tool`` instance whose async handler delegates to
    ``client.call_tool(name, arguments)``.  The tools are organised
    into three tiers:

    **Tier 1 — Context retrieval** (always registered, 4 tools):

    +-----------------------+-------------------------------------------+
    | Tool                  | Purpose                                   |
    +=======================+===========================================+
    | ``rlm_context_query`` | Semantic/keyword/hybrid doc search        |
    | ``rlm_search``        | Regex pattern search across documentation |
    | ``rlm_sections``      | List indexed sections with pagination     |
    | ``rlm_read``          | Read specific lines from documentation    |
    +-----------------------+-------------------------------------------+

    **Tier 2 — Memory** (gated by ``memory_enabled``, 4 tools):

    +--------------------+---------------------------------------------+
    | Tool               | Purpose                                     |
    +====================+=============================================+
    | ``rlm_remember``   | Store a memory (fact/decision/learning/...) |
    | ``rlm_recall``     | Semantic recall by query                    |
    | ``rlm_memories``   | List memories with filters                  |
    | ``rlm_forget``     | Delete memories by ID/type/category/age     |
    +--------------------+---------------------------------------------+

    **Tier 3 — Advanced** (always registered, 1 tool):

    +------------------------+------------------------------------------+
    | Tool                   | Purpose                                  |
    +========================+==========================================+
    | ``rlm_shared_context`` | Merged team docs (MANDATORY, GUIDELINES) |
    +------------------------+------------------------------------------+

    Args:
        client: A configured ``SniparaClient`` instance with valid auth.
        memory_enabled: When ``True``, include Tier 2 memory tools.
            Controlled by ``config.memory_enabled`` (default ``False``).

    Returns:
        List of ``Tool`` instances ready for registration in the
        ``ToolRegistry``.  5 tools without memory, 9 with memory.
    """
    # Tier 1 (always) + Tier 3 (always)
    tools: list[Tool] = [
        # Tier 1: Context retrieval
        _create_context_query_tool(client),
        _create_search_tool(client),
        _create_sections_tool(client),
        _create_read_tool(client),
        # Tier 3: Advanced
        _create_shared_context_tool(client),
    ]

    # Tier 2: Memory (gated by config.memory_enabled)
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
    """Create the ``rlm_context_query`` tool.

    Primary context retrieval tool.  The LLM sends a natural-language
    query and receives ranked documentation sections within a token
    budget.  Supports three search modes:

    - ``keyword`` — fast TF-IDF matching
    - ``semantic`` — embedding-based similarity
    - ``hybrid`` — combines both (default, best quality)
    """

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
    """Create the ``rlm_search`` tool.

    Regex-based pattern search across all indexed documentation.
    Useful when the LLM knows the exact term or pattern to look for
    (e.g., function names, error codes).
    """

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
    """Create the ``rlm_sections`` tool.

    Lists the indexed documentation structure with optional title-prefix
    filtering and pagination.  Helps the LLM discover what documentation
    is available before issuing targeted queries.
    """

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
    """Create the ``rlm_read`` tool.

    Reads a specific line range from the indexed documentation.
    Complementary to ``rlm_sections`` — once the LLM knows which
    section to look at, it can read the exact lines.
    """

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
    """Create the ``rlm_remember`` tool (Tier 2 — Memory).

    Stores a memory in the Snipara memory system for later semantic
    recall.  Memories have a type (fact, decision, learning, preference,
    todo, context), a scope (agent, project, team, user), and an
    optional TTL for auto-expiration.
    """

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
    """Create the ``rlm_recall`` tool (Tier 2 — Memory).

    Semantically searches stored memories using embedding-based
    similarity weighted by confidence decay (older memories rank
    lower).  Supports filtering by type, scope, and category.
    """

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
    """Create the ``rlm_memories`` tool (Tier 2 — Memory).

    Lists stored memories with optional filters (type, scope, category,
    text search) and pagination.  Unlike ``rlm_recall``, this does not
    use semantic search — it's a structured listing.
    """

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
    """Create the ``rlm_forget`` tool (Tier 2 — Memory).

    Deletes memories by specific ID, by type/category filter, or by
    age (``older_than_days``).  All filter parameters are optional;
    at least one should be provided to avoid deleting nothing.
    """

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
    """Create the ``rlm_shared_context`` tool (Tier 3 — Advanced).

    Retrieves merged context from linked shared collections (team-level
    docs).  Collections are categorised as MANDATORY, BEST_PRACTICES,
    GUIDELINES, or REFERENCE, and the API allocates token budget across
    categories proportionally.
    """

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
