"""Tests for LiteLLM backend adapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rlm.backends.base import Tool
from rlm.backends.litellm import LiteLLMBackend
from rlm.core.types import Message, ToolCall


class TestLiteLLMBackendInit:
    """Tests for LiteLLMBackend initialization."""

    def test_default_values(self):
        """Should use default values."""
        backend = LiteLLMBackend()
        assert backend.model == "gpt-4o-mini"
        assert backend.temperature == 0.0
        assert backend.api_key is None
        assert backend.api_base is None

    def test_custom_model(self):
        """Should accept custom model."""
        backend = LiteLLMBackend(model="claude-3-sonnet-20240229")
        assert backend.model == "claude-3-sonnet-20240229"

    def test_custom_temperature(self):
        """Should accept custom temperature."""
        backend = LiteLLMBackend(temperature=0.7)
        assert backend.temperature == 0.7

    def test_custom_api_key(self):
        """Should accept custom API key."""
        backend = LiteLLMBackend(api_key="sk-test-key")
        assert backend.api_key == "sk-test-key"

    def test_custom_api_base(self):
        """Should accept custom API base."""
        backend = LiteLLMBackend(api_base="https://custom.api.com")
        assert backend.api_base == "https://custom.api.com"

    def test_extra_kwargs(self):
        """Should store extra kwargs."""
        backend = LiteLLMBackend(max_tokens=1000, top_p=0.9)
        assert backend.kwargs == {"max_tokens": 1000, "top_p": 0.9}


class TestMessagesToOpenAI:
    """Tests for _messages_to_openai method."""

    @pytest.fixture
    def backend(self):
        """Create backend instance."""
        return LiteLLMBackend()

    def test_simple_message(self, backend):
        """Should convert simple message."""
        messages = [Message(role="user", content="Hello")]
        result = backend._messages_to_openai(messages)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_system_message(self, backend):
        """Should convert system message."""
        messages = [Message(role="system", content="You are helpful")]
        result = backend._messages_to_openai(messages)

        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are helpful"

    def test_message_with_tool_calls(self, backend):
        """Should convert message with tool calls."""
        messages = [
            Message(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="tc1", name="get_weather", arguments={"city": "London"})],
            )
        ]
        result = backend._messages_to_openai(messages)

        assert "tool_calls" in result[0]
        assert len(result[0]["tool_calls"]) == 1
        assert result[0]["tool_calls"][0]["id"] == "tc1"
        assert result[0]["tool_calls"][0]["function"]["name"] == "get_weather"
        assert json.loads(result[0]["tool_calls"][0]["function"]["arguments"]) == {"city": "London"}

    def test_tool_result_message(self, backend):
        """Should convert tool result message."""
        messages = [Message(role="tool", content="Temperature: 20C", tool_call_id="tc1")]
        result = backend._messages_to_openai(messages)

        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "tc1"

    def test_message_with_name(self, backend):
        """Should include name if present."""
        messages = [Message(role="user", content="Hello", name="Alice")]
        result = backend._messages_to_openai(messages)

        assert result[0]["name"] == "Alice"


class TestParseToolCalls:
    """Tests for _parse_tool_calls method."""

    @pytest.fixture
    def backend(self):
        """Create backend instance."""
        return LiteLLMBackend()

    def test_empty_tool_calls(self, backend):
        """Should return empty list for None."""
        result = backend._parse_tool_calls(None)
        assert result == []

    def test_empty_list(self, backend):
        """Should return empty list for empty list."""
        result = backend._parse_tool_calls([])
        assert result == []

    def test_parse_single_tool_call(self, backend):
        """Should parse single tool call."""
        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.function.name = "get_weather"
        tool_call.function.arguments = '{"city": "London"}'

        result = backend._parse_tool_calls([tool_call])

        assert len(result) == 1
        assert result[0].id == "tc1"
        assert result[0].name == "get_weather"
        assert result[0].arguments == {"city": "London"}

    def test_parse_multiple_tool_calls(self, backend):
        """Should parse multiple tool calls."""
        tc1 = MagicMock()
        tc1.id = "tc1"
        tc1.function.name = "get_weather"
        tc1.function.arguments = '{"city": "London"}'

        tc2 = MagicMock()
        tc2.id = "tc2"
        tc2.function.name = "get_time"
        tc2.function.arguments = '{"timezone": "UTC"}'

        result = backend._parse_tool_calls([tc1, tc2])

        assert len(result) == 2
        assert result[0].name == "get_weather"
        assert result[1].name == "get_time"

    def test_parse_already_parsed_arguments(self, backend):
        """Should handle already-parsed arguments."""
        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.function.name = "test"
        tool_call.function.arguments = {"already": "parsed"}

        result = backend._parse_tool_calls([tool_call])

        assert result[0].arguments == {"already": "parsed"}

    def test_handles_malformed_json(self, backend):
        """Should handle malformed JSON gracefully."""
        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.function.name = "test"
        tool_call.function.arguments = "not valid json"

        result = backend._parse_tool_calls([tool_call])

        assert len(result) == 1
        assert "_error" in result[0].arguments


class TestComplete:
    """Tests for complete method."""

    @pytest.fixture
    def backend(self):
        """Create backend instance."""
        return LiteLLMBackend()

    @pytest.mark.asyncio
    async def test_basic_completion(self, backend):
        """Should make completion call and return response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello there!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model = "gpt-4o-mini"

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response

            messages = [Message(role="user", content="Hello")]
            result = await backend.complete(messages)

            assert result.content == "Hello there!"
            assert result.input_tokens == 10
            assert result.output_tokens == 5
            assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_completion_with_tools(self, backend):
        """Should include tools in request."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [MagicMock()]
        mock_response.choices[0].message.tool_calls[0].id = "tc1"
        mock_response.choices[0].message.tool_calls[0].function.name = "get_weather"
        mock_response.choices[0].message.tool_calls[0].function.arguments = '{"city": "London"}'
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 15
        mock_response.model = "gpt-4o-mini"

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response

            tools = [
                Tool(
                    name="get_weather",
                    description="Get weather",
                    parameters={"type": "object", "properties": {}},
                    handler=AsyncMock(),
                )
            ]
            messages = [Message(role="user", content="What's the weather?")]
            result = await backend.complete(messages, tools=tools)

            # Verify tools were passed
            call_kwargs = mock_complete.call_args[1]
            assert "tools" in call_kwargs
            assert call_kwargs["tool_choice"] == "auto"

            # Verify response
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_completion_with_api_key(self):
        """Should pass API key to request."""
        backend = LiteLLMBackend(api_key="sk-test")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.model = "gpt-4o-mini"

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response

            await backend.complete([Message(role="user", content="Hi")])

            call_kwargs = mock_complete.call_args[1]
            assert call_kwargs["api_key"] == "sk-test"

    @pytest.mark.asyncio
    async def test_completion_with_api_base(self):
        """Should pass API base to request."""
        backend = LiteLLMBackend(api_base="https://custom.api.com")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.model = "gpt-4o-mini"

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response

            await backend.complete([Message(role="user", content="Hi")])

            call_kwargs = mock_complete.call_args[1]
            assert call_kwargs["api_base"] == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_completion_handles_no_usage(self, backend):
        """Should handle missing usage data."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None
        mock_response.model = "gpt-4o-mini"

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_response

            result = await backend.complete([Message(role="user", content="Hi")])

            assert result.input_tokens == 0
            assert result.output_tokens == 0


class TestStream:
    """Tests for stream method."""

    @pytest.fixture
    def backend(self):
        """Create backend instance."""
        return LiteLLMBackend()

    @pytest.mark.asyncio
    async def test_basic_streaming(self, backend):
        """Should stream content chunks."""

        async def mock_stream():
            chunks = ["Hello", " ", "World", "!"]
            for chunk_text in chunks:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = chunk_text
                yield chunk

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_stream()

            messages = [Message(role="user", content="Hello")]
            chunks = []
            async for chunk in backend.stream(messages):
                chunks.append(chunk)

            assert chunks == ["Hello", " ", "World", "!"]

    @pytest.mark.asyncio
    async def test_streaming_skips_empty_chunks(self, backend):
        """Should skip chunks with no content."""

        async def mock_stream():
            chunk1 = MagicMock()
            chunk1.choices = [MagicMock()]
            chunk1.choices[0].delta.content = "Hello"
            yield chunk1

            chunk2 = MagicMock()
            chunk2.choices = [MagicMock()]
            chunk2.choices[0].delta.content = None
            yield chunk2

            chunk3 = MagicMock()
            chunk3.choices = [MagicMock()]
            chunk3.choices[0].delta.content = "World"
            yield chunk3

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_stream()

            messages = [Message(role="user", content="Hello")]
            chunks = []
            async for chunk in backend.stream(messages):
                chunks.append(chunk)

            assert chunks == ["Hello", "World"]

    @pytest.mark.asyncio
    async def test_streaming_with_tools(self, backend):
        """Should pass tools in streaming request."""

        async def mock_stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = "Test"
            yield chunk

        with patch("rlm.backends.litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = mock_stream()

            tools = [
                Tool(
                    name="test_tool",
                    description="Test",
                    parameters={"type": "object", "properties": {}},
                    handler=AsyncMock(),
                )
            ]
            messages = [Message(role="user", content="Hello")]

            async for _ in backend.stream(messages, tools=tools):
                pass

            call_kwargs = mock_complete.call_args[1]
            assert "tools" in call_kwargs
            assert call_kwargs["stream"] is True
