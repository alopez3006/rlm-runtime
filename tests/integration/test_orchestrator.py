"""Integration tests for RLM orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rlm.backends.base import BackendResponse, Tool
from rlm.core.orchestrator import RLM
from rlm.core.types import CompletionOptions, ToolCall


class TestOrchestratorBasic:
    """Basic orchestrator tests with mocked backend."""

    @pytest.fixture
    def mock_backend_response(self):
        """Create a simple completion response."""
        return BackendResponse(
            content="This is the answer.",
            tool_calls=[],
            input_tokens=20,
            output_tokens=10,
            finish_reason="stop",
        )

    @pytest.mark.asyncio
    async def test_simple_completion(self, mock_backend_response):
        """Test a simple completion without tool calls."""
        with patch("rlm.core.orchestrator.RLM._create_backend") as mock_create:
            backend = MagicMock()
            backend.complete = AsyncMock(return_value=mock_backend_response)
            mock_create.return_value = backend

            rlm = RLM(backend="litellm", model="gpt-4o-mini")
            result = await rlm.completion("What is 2+2?")

            assert result.response == "This is the answer."
            assert result.total_calls == 1
            assert result.success

    @pytest.mark.asyncio
    async def test_completion_with_system_message(self, mock_backend_response):
        """Test completion with system message."""
        with patch("rlm.core.orchestrator.RLM._create_backend") as mock_create:
            backend = MagicMock()
            backend.complete = AsyncMock(return_value=mock_backend_response)
            mock_create.return_value = backend

            rlm = RLM(backend="litellm")
            result = await rlm.completion(
                "Hello",
                system="You are a helpful assistant.",
            )

            assert result.success
            # Verify system message was included
            call_args = backend.complete.call_args
            messages = call_args[0][0]
            assert messages[0].role == "system"

    @pytest.mark.asyncio
    async def test_max_depth_exceeded(self):
        """Test that max depth is enforced."""
        # Create a response that always calls tools
        tool_response = BackendResponse(
            content=None,
            tool_calls=[ToolCall(id="1", name="test_tool", arguments={})],
            input_tokens=10,
            output_tokens=5,
            finish_reason="tool_calls",
        )

        with patch("rlm.core.orchestrator.RLM._create_backend") as mock_create:
            backend = MagicMock()
            backend.complete = AsyncMock(return_value=tool_response)
            mock_create.return_value = backend

            rlm = RLM(backend="litellm")

            # Register a dummy tool
            async def dummy_handler():
                return "ok"

            rlm.tool_registry.register(
                Tool(
                    name="test_tool",
                    description="Test",
                    parameters={"type": "object", "properties": {}},
                    handler=dummy_handler,
                )
            )

            options = CompletionOptions(max_depth=2)
            result = await rlm.completion("Test", options=options)

            # Should have error about max depth
            assert not result.success or "depth" in result.response.lower()


class TestOrchestratorTools:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Test that tools are executed correctly."""
        # First response calls tool, second gives answer
        responses = [
            BackendResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="add", arguments={"x": 2, "y": 3})],
                input_tokens=10,
                output_tokens=5,
                finish_reason="tool_calls",
            ),
            BackendResponse(
                content="The sum is 5.",
                tool_calls=[],
                input_tokens=15,
                output_tokens=10,
                finish_reason="stop",
            ),
        ]

        with patch("rlm.core.orchestrator.RLM._create_backend") as mock_create:
            backend = MagicMock()
            backend.complete = AsyncMock(side_effect=responses)
            mock_create.return_value = backend

            rlm = RLM(backend="litellm")

            # Register add tool
            async def add_handler(x: int, y: int) -> int:
                return x + y

            rlm.tool_registry.register(
                Tool(
                    name="add",
                    description="Add numbers",
                    parameters={
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                        },
                        "required": ["x", "y"],
                    },
                    handler=add_handler,
                )
            )

            result = await rlm.completion("Add 2 and 3")

            assert result.response == "The sum is 5."
            assert result.total_tool_calls == 1
            assert result.total_calls == 2

    @pytest.mark.asyncio
    async def test_unknown_tool_handling(self):
        """Test handling of unknown tool calls."""
        responses = [
            BackendResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="unknown_tool", arguments={})],
                input_tokens=10,
                output_tokens=5,
                finish_reason="tool_calls",
            ),
            BackendResponse(
                content="Tool not found.",
                tool_calls=[],
                input_tokens=15,
                output_tokens=10,
                finish_reason="stop",
            ),
        ]

        with patch("rlm.core.orchestrator.RLM._create_backend") as mock_create:
            backend = MagicMock()
            backend.complete = AsyncMock(side_effect=responses)
            mock_create.return_value = backend

            rlm = RLM(backend="litellm")
            result = await rlm.completion("Call unknown tool")

            # Should handle gracefully
            assert result.success or "unknown" in str(result.events).lower()
