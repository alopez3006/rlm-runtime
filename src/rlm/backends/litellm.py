"""LiteLLM backend adapter supporting 100+ LLM providers."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import litellm
from litellm import acompletion

from rlm.backends.base import BackendResponse, BaseBackend, Tool
from rlm.core.types import Message, ToolCall

logger = logging.getLogger(__name__)


class LiteLLMBackend(BaseBackend):
    """LiteLLM backend supporting OpenAI, Anthropic, and 100+ other providers.

    This is the default and recommended backend as it provides a unified
    interface across all major LLM providers.

    Example:
        ```python
        # OpenAI
        backend = LiteLLMBackend(model="gpt-4o-mini")

        # Anthropic
        backend = LiteLLMBackend(model="claude-3-sonnet-20240229")

        # OpenRouter
        backend = LiteLLMBackend(model="openrouter/anthropic/claude-3-opus")
        ```
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ):
        """Initialize the LiteLLM backend.

        Args:
            model: Model identifier (e.g., "gpt-4o-mini", "claude-3-sonnet")
            temperature: Sampling temperature (0.0 = deterministic)
            api_key: Optional API key (usually set via environment)
            api_base: Optional custom API base URL
            **kwargs: Additional parameters passed to litellm
        """
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.api_base = api_base
        self.kwargs = kwargs

        # Disable LiteLLM's verbose logging
        litellm.suppress_debug_info = True

    def _messages_to_openai(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to OpenAI format."""
        result: list[dict[str, Any]] = []

        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}

            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]

            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id

            if m.name:
                msg["name"] = m.name

            result.append(msg)

        return result

    def _parse_tool_calls(self, tool_calls: list[Any] | None) -> list[ToolCall]:
        """Parse tool calls from LiteLLM response."""
        if not tool_calls:
            return []

        result: list[ToolCall] = []
        for tc in tool_calls:
            try:
                arguments = tc.function.arguments
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)

                result.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )
            except (json.JSONDecodeError, AttributeError) as e:
                # Log but don't fail on malformed tool calls
                result.append(
                    ToolCall(
                        id=getattr(tc, "id", "unknown"),
                        name=getattr(tc.function, "name", "unknown")
                        if hasattr(tc, "function")
                        else "unknown",
                        arguments={"_error": str(e), "_raw": str(tc)},
                    )
                )

        return result

    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> BackendResponse:
        """Generate a completion using LiteLLM.

        Args:
            messages: Conversation messages
            tools: Available tools for function calling
            **kwargs: Additional parameters for the LLM

        Returns:
            BackendResponse with content and/or tool calls
        """
        openai_messages = self._messages_to_openai(messages)

        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            **self.kwargs,
            **kwargs,
        }

        if self.api_key:
            call_kwargs["api_key"] = self.api_key

        if self.api_base:
            call_kwargs["api_base"] = self.api_base

        if tools:
            call_kwargs["tools"] = [t.to_openai_format() for t in tools]
            call_kwargs["tool_choice"] = "auto"

        # Support structured outputs via response_format
        response_format = kwargs.pop("response_format", None)
        if response_format is not None:
            call_kwargs["response_format"] = response_format

        response = await acompletion(**call_kwargs)

        choice = response.choices[0]
        tool_calls = self._parse_tool_calls(getattr(choice.message, "tool_calls", None))

        # Parse JSON output when response_format was used
        parsed_output = None
        if response_format is not None and choice.message.content:
            try:
                parsed_output = json.loads(choice.message.content)
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse structured output as JSON",
                    extra={"content_preview": choice.message.content[:100]},
                )

        return BackendResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
            model=response.model,
            raw_response=response,
            parsed_output=parsed_output,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion using LiteLLM.

        Args:
            messages: Conversation messages
            tools: Available tools for function calling
            **kwargs: Additional parameters for the LLM

        Yields:
            Content chunks as they arrive
        """
        openai_messages = self._messages_to_openai(messages)

        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "stream": True,
            **self.kwargs,
            **kwargs,
        }

        if self.api_key:
            call_kwargs["api_key"] = self.api_key

        if self.api_base:
            call_kwargs["api_base"] = self.api_base

        if tools:
            call_kwargs["tools"] = [t.to_openai_format() for t in tools]

        response = await acompletion(**call_kwargs)

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
