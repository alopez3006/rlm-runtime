"""Tool registry for managing available tools."""

from __future__ import annotations

from collections.abc import Iterator

import structlog

from rlm.backends.base import Tool

logger = structlog.get_logger()


class ToolRegistry:
    """Registry for managing tools available to the RLM.

    Tools can be registered manually or discovered via entry points.

    Example:
        ```python
        registry = ToolRegistry()
        registry.register(my_tool)

        # Get a specific tool
        tool = registry.get("my_tool")

        # Get all tools
        all_tools = registry.get_all()
        ```
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in self._tools:
            logger.warning(
                "Tool already registered, overwriting",
                tool_name=tool.name,
            )
        self._tools[tool.name] = tool
        logger.debug("Tool registered", tool_name=tool.name)

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name.

        Args:
            name: Name of the tool to unregister

        Returns:
            True if the tool was removed, False if it wasn't registered
        """
        if name in self._tools:
            del self._tools[name]
            logger.debug("Tool unregistered", tool_name=name)
            return True
        return False

    def get(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools.

        Returns:
            List of all registered tools
        """
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def has(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Name of the tool

        Returns:
            True if registered, False otherwise
        """
        return name in self._tools

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()

    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        """Iterate over registered tools."""
        return iter(self._tools.values())

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
