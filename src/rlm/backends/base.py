"""Abstract backend interface for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from rlm.core.types import Message, ToolCall


@dataclass
class Tool:
    """Tool definition for LLM function calling.

    Example:
        ```python
        async def get_weather(city: str) -> dict:
            return {"city": city, "temp": 72}

        tool = Tool(
            name="get_weather",
            description="Get current weather for a city",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            },
            handler=get_weather,
        )
        ```
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool handler with the given arguments."""
        return await self.handler(**kwargs)


@dataclass
class BackendResponse:
    """Response from an LLM backend."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"
    model: str | None = None
    raw_response: Any = None
    parsed_output: dict[str, Any] | None = None  # Parsed JSON when response_format is used

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


class BaseBackend(ABC):
    """Abstract base class for LLM backends.

    Implement this class to add support for new LLM providers.
    """

    model: str  # Subclasses must set this

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> BackendResponse:
        """Generate a completion.

        Args:
            messages: Conversation messages
            tools: Available tools for function calling
            **kwargs: Additional provider-specific parameters

        Returns:
            BackendResponse with content and/or tool calls
        """
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion.

        Args:
            messages: Conversation messages
            tools: Available tools for function calling
            **kwargs: Additional provider-specific parameters

        Yields:
            Content chunks as they arrive
        """
        ...

    def supports_tools(self) -> bool:
        """Check if this backend supports tool/function calling."""
        return True

    def supports_streaming(self) -> bool:
        """Check if this backend supports streaming."""
        return True
