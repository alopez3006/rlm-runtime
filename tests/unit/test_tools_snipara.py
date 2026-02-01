"""Tests for native Snipara tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from rlm.backends.base import Tool
from rlm.core.config import RLMConfig
from rlm.core.exceptions import SniparaAPIError
from rlm.tools.snipara import SniparaClient, get_native_snipara_tools

# ---------------------------------------------------------------------------
# SniparaClient tests
# ---------------------------------------------------------------------------


class TestSniparaClientFromConfig:
    """Tests for SniparaClient.from_config()."""

    def test_creates_client_with_oauth(self):
        """Should create client when OAuth tokens are available."""
        with patch("rlm.tools.snipara.get_snipara_auth") as mock_auth:
            mock_auth.return_value = ("Bearer oauth_token_123", "my-project")
            config = RLMConfig()
            client = SniparaClient.from_config(config)

            assert client is not None
            assert client._auth_header == "Bearer oauth_token_123"
            assert client._project_slug == "my-project"

    def test_creates_client_with_config_api_key(self):
        """Should create client when API key is in config."""
        with patch("rlm.tools.snipara.get_snipara_auth") as mock_auth:
            mock_auth.return_value = (None, None)

            config = RLMConfig()
            # Manually set since env override won't be present
            config.snipara_api_key = "rlm_test_key"
            config.snipara_project_slug = "test-project"

            client = SniparaClient.from_config(config)

            assert client is not None
            assert client._auth_header == "rlm_test_key"
            assert client._project_slug == "test-project"

    def test_returns_none_when_no_auth(self):
        """Should return None when no auth available."""
        with patch("rlm.tools.snipara.get_snipara_auth") as mock_auth:
            mock_auth.return_value = (None, None)
            config = RLMConfig()
            # Override any env vars that BaseSettings may have picked up
            config.snipara_api_key = None
            config.snipara_project_slug = None
            client = SniparaClient.from_config(config)

            assert client is None

    def test_returns_none_when_no_project_slug(self):
        """Should return None when auth exists but no project slug."""
        with patch("rlm.tools.snipara.get_snipara_auth") as mock_auth:
            mock_auth.return_value = ("Bearer token", None)
            config = RLMConfig()
            # Override any env vars that BaseSettings may have picked up
            config.snipara_project_slug = None
            client = SniparaClient.from_config(config)

            assert client is None

    def test_oauth_takes_precedence_over_config(self):
        """OAuth auth should be preferred over config API key."""
        with patch("rlm.tools.snipara.get_snipara_auth") as mock_auth:
            mock_auth.return_value = ("Bearer oauth_token", "oauth-project")

            config = RLMConfig()
            config.snipara_api_key = "config_key"
            config.snipara_project_slug = "config-project"

            client = SniparaClient.from_config(config)

            assert client is not None
            assert client._auth_header == "Bearer oauth_token"
            assert client._project_slug == "oauth-project"

    def test_uses_config_base_url(self):
        """Should use base URL from config."""
        with patch("rlm.tools.snipara.get_snipara_auth") as mock_auth:
            mock_auth.return_value = ("Bearer token", "my-project")

            config = RLMConfig()
            config.snipara_base_url = "https://custom.snipara.com/api/mcp"

            client = SniparaClient.from_config(config)

            assert client is not None
            assert client._base_url == "https://custom.snipara.com/api/mcp"


class TestSniparaClientApiUrl:
    """Tests for SniparaClient.api_url property."""

    def test_constructs_correct_url(self):
        client = SniparaClient(
            base_url="https://api.snipara.com/mcp",
            project_slug="my-project",
            auth_header="Bearer token",
        )
        assert client.api_url == "https://api.snipara.com/mcp/my-project"

    def test_strips_trailing_slash(self):
        client = SniparaClient(
            base_url="https://api.snipara.com/mcp/",
            project_slug="proj",
            auth_header="key",
        )
        assert client.api_url == "https://api.snipara.com/mcp/proj"


class TestSniparaClientCallTool:
    """Tests for SniparaClient.call_tool()."""

    @pytest.fixture
    def client(self):
        return SniparaClient(
            base_url="https://api.snipara.com/mcp",
            project_slug="test",
            auth_header="Bearer test_token",
        )

    @pytest.mark.asyncio
    async def test_success_returns_json(self, client):
        """Should return parsed JSON on success."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"sections": [{"title": "Test"}]}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_response
        mock_http.is_closed = False
        client._client = mock_http

        result = await client.call_tool("rlm_context_query", {"query": "test"})

        assert result == {"sections": [{"title": "Test"}]}
        mock_http.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self, client):
        """Should POST with {tool, arguments} payload."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_response
        mock_http.is_closed = False
        client._client = mock_http

        await client.call_tool("rlm_search", {"pattern": "error", "max_results": 10})

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload == {
            "tool": "rlm_search",
            "arguments": {"pattern": "error", "max_results": 10},
        }

    @pytest.mark.asyncio
    async def test_strips_none_values(self, client):
        """Should strip None values from arguments."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_response
        mock_http.is_closed = False
        client._client = mock_http

        await client.call_tool(
            "rlm_sections",
            {"filter": None, "limit": 50, "offset": 0},
        )

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "filter" not in payload["arguments"]
        assert payload["arguments"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_http_error_raises_snipara_api_error(self, client):
        """Should raise SniparaAPIError on HTTP 4xx/5xx."""
        mock_request = MagicMock(spec=httpx.Request)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=mock_request, response=mock_response
        )

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_response
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(SniparaAPIError) as exc_info:
            await client.call_tool("rlm_context_query", {"query": "test"})

        assert exc_info.value.status_code == 401
        assert exc_info.value.tool_name == "rlm_context_query"

    @pytest.mark.asyncio
    async def test_timeout_raises_snipara_api_error(self, client):
        """Should raise SniparaAPIError on timeout."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.side_effect = httpx.TimeoutException("timed out")
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(SniparaAPIError) as exc_info:
            await client.call_tool("rlm_search", {"pattern": "test"})

        assert exc_info.value.status_code is None
        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connection_error_raises_snipara_api_error(self, client):
        """Should raise SniparaAPIError on connection failure."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.side_effect = httpx.ConnectError("Connection refused")
        mock_http.is_closed = False
        client._client = mock_http

        with pytest.raises(SniparaAPIError) as exc_info:
            await client.call_tool("rlm_read", {"start_line": 1, "end_line": 10})

        assert exc_info.value.status_code is None
        assert "rlm_read" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Should close the httpx client."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.is_closed = False
        client._client = mock_http

        await client.close()
        mock_http.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tool factory tests
# ---------------------------------------------------------------------------


class TestGetNativeSniparaTools:
    """Tests for the tool factory function."""

    @pytest.fixture
    def mock_client(self):
        return MagicMock(spec=SniparaClient)

    def test_returns_5_tools_without_memory(self, mock_client):
        """Should return Tier 1 + Tier 3 tools when memory disabled."""
        tools = get_native_snipara_tools(mock_client, memory_enabled=False)
        assert len(tools) == 5
        names = {t.name for t in tools}
        assert names == {
            "rlm_context_query",
            "rlm_search",
            "rlm_sections",
            "rlm_read",
            "rlm_shared_context",
        }

    def test_returns_9_tools_with_memory(self, mock_client):
        """Should return all 9 tools when memory enabled."""
        tools = get_native_snipara_tools(mock_client, memory_enabled=True)
        assert len(tools) == 9
        names = {t.name for t in tools}
        assert "rlm_remember" in names
        assert "rlm_recall" in names
        assert "rlm_memories" in names
        assert "rlm_forget" in names

    def test_all_are_tool_instances(self, mock_client):
        """All returned items should be Tool instances with required fields."""
        tools = get_native_snipara_tools(mock_client, memory_enabled=True)
        for tool in tools:
            assert isinstance(tool, Tool)
            assert tool.name
            assert tool.description
            assert tool.parameters.get("type") == "object"
            assert "properties" in tool.parameters
            assert callable(tool.handler)

    def test_tools_have_openai_format(self, mock_client):
        """Tools should convert to OpenAI function calling format."""
        tools = get_native_snipara_tools(mock_client, memory_enabled=False)
        for tool in tools:
            fmt = tool.to_openai_format()
            assert fmt["type"] == "function"
            assert "function" in fmt
            assert fmt["function"]["name"] == tool.name

    def test_tools_have_anthropic_format(self, mock_client):
        """Tools should convert to Anthropic tool format."""
        tools = get_native_snipara_tools(mock_client, memory_enabled=False)
        for tool in tools:
            fmt = tool.to_anthropic_format()
            assert fmt["name"] == tool.name
            assert "input_schema" in fmt


# ---------------------------------------------------------------------------
# Tool execution tests
# ---------------------------------------------------------------------------


class TestToolExecution:
    """Tests for individual tool handler execution."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock(spec=SniparaClient)
        client.call_tool = AsyncMock(return_value={"result": "success"})
        return client

    def _get_tool(self, tools: list[Tool], name: str) -> Tool:
        return next(t for t in tools if t.name == name)

    @pytest.mark.asyncio
    async def test_context_query_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_context_query")

        await tool.execute(query="What is RLM?")

        mock_client.call_tool.assert_awaited_once_with(
            "rlm_context_query",
            {
                "query": "What is RLM?",
                "max_tokens": 4000,
                "search_mode": "hybrid",
                "prefer_summaries": False,
                "include_metadata": True,
            },
        )

    @pytest.mark.asyncio
    async def test_context_query_custom_params(self, mock_client):
        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_context_query")

        await tool.execute(
            query="test",
            max_tokens=2000,
            search_mode="keyword",
            prefer_summaries=True,
            include_metadata=False,
        )

        args = mock_client.call_tool.call_args[0][1]
        assert args["max_tokens"] == 2000
        assert args["search_mode"] == "keyword"
        assert args["prefer_summaries"] is True
        assert args["include_metadata"] is False

    @pytest.mark.asyncio
    async def test_search_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_search")

        await tool.execute(pattern="error.*handling")

        mock_client.call_tool.assert_awaited_once_with(
            "rlm_search",
            {"pattern": "error.*handling", "max_results": 20},
        )

    @pytest.mark.asyncio
    async def test_sections_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_sections")

        await tool.execute(filter="API", limit=10)

        mock_client.call_tool.assert_awaited_once_with(
            "rlm_sections",
            {"filter": "API", "limit": 10, "offset": 0},
        )

    @pytest.mark.asyncio
    async def test_read_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_read")

        await tool.execute(start_line=10, end_line=20)

        mock_client.call_tool.assert_awaited_once_with(
            "rlm_read",
            {"start_line": 10, "end_line": 20},
        )

    @pytest.mark.asyncio
    async def test_shared_context_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_shared_context")

        await tool.execute(categories=["MANDATORY"], max_tokens=2000)

        mock_client.call_tool.assert_awaited_once_with(
            "rlm_shared_context",
            {
                "categories": ["MANDATORY"],
                "max_tokens": 2000,
                "include_content": True,
            },
        )

    @pytest.mark.asyncio
    async def test_remember_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client, memory_enabled=True)
        tool = self._get_tool(tools, "rlm_remember")

        await tool.execute(content="User prefers dark mode", type="preference")

        call_args = mock_client.call_tool.call_args[0]
        assert call_args[0] == "rlm_remember"
        assert call_args[1]["content"] == "User prefers dark mode"
        assert call_args[1]["type"] == "preference"

    @pytest.mark.asyncio
    async def test_recall_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client, memory_enabled=True)
        tool = self._get_tool(tools, "rlm_recall")

        await tool.execute(query="dark mode", limit=3)

        call_args = mock_client.call_tool.call_args[0]
        assert call_args[0] == "rlm_recall"
        assert call_args[1]["query"] == "dark mode"
        assert call_args[1]["limit"] == 3

    @pytest.mark.asyncio
    async def test_memories_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client, memory_enabled=True)
        tool = self._get_tool(tools, "rlm_memories")

        await tool.execute(type="fact", search="auth")

        call_args = mock_client.call_tool.call_args[0]
        assert call_args[0] == "rlm_memories"
        assert call_args[1]["type"] == "fact"
        assert call_args[1]["search"] == "auth"

    @pytest.mark.asyncio
    async def test_forget_forwards_args(self, mock_client):
        tools = get_native_snipara_tools(mock_client, memory_enabled=True)
        tool = self._get_tool(tools, "rlm_forget")

        await tool.execute(memory_id="abc123")

        call_args = mock_client.call_tool.call_args[0]
        assert call_args[0] == "rlm_forget"
        assert call_args[1]["memory_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_tool_propagates_api_error(self, mock_client):
        """Tool should propagate SniparaAPIError from client."""
        mock_client.call_tool = AsyncMock(
            side_effect=SniparaAPIError(
                tool_name="rlm_context_query",
                status_code=500,
                message="Internal error",
            )
        )
        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_context_query")

        with pytest.raises(SniparaAPIError):
            await tool.execute(query="test")

    @pytest.mark.asyncio
    async def test_tool_returns_client_response(self, mock_client):
        """Tool should return whatever the client returns."""
        expected = {"sections": [{"title": "Auth Guide", "content": "..."}]}
        mock_client.call_tool = AsyncMock(return_value=expected)

        tools = get_native_snipara_tools(mock_client)
        tool = self._get_tool(tools, "rlm_context_query")

        result = await tool.execute(query="auth")
        assert result == expected


# ---------------------------------------------------------------------------
# SniparaAPIError tests
# ---------------------------------------------------------------------------


class TestSniparaAPIError:
    """Tests for the SniparaAPIError exception."""

    def test_with_status_code(self):
        err = SniparaAPIError(tool_name="rlm_search", status_code=401, message="Unauthorized")
        assert err.tool_name == "rlm_search"
        assert err.status_code == 401
        assert "HTTP 401" in str(err)
        assert "rlm_search" in str(err)

    def test_without_status_code(self):
        err = SniparaAPIError(tool_name="rlm_read", status_code=None, message="Connection refused")
        assert err.status_code is None
        assert "HTTP" not in str(err)
        assert "rlm_read" in str(err)

    def test_inherits_from_tool_error(self):
        from rlm.core.exceptions import ToolError

        err = SniparaAPIError(tool_name="test", status_code=500, message="error")
        assert isinstance(err, ToolError)

    def test_message_truncated(self):
        long_msg = "x" * 500
        err = SniparaAPIError(tool_name="test", status_code=500, message=long_msg)
        # Should be truncated to 200 chars in the formatted message
        assert len(str(err)) < 300
