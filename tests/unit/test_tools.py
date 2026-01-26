"""Unit tests for tool system."""

import pytest

from rlm.backends.base import Tool
from rlm.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry()


@pytest.fixture
def sample_tool():
    async def handler(x: int) -> int:
        return x * 2

    return Tool(
        name="double",
        description="Double a number",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        },
        handler=handler,
    )


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self, registry, sample_tool):
        """Test registering a tool."""
        registry.register(sample_tool)
        assert registry.has("double")
        assert len(registry) == 1

    def test_get_tool(self, registry, sample_tool):
        """Test getting a registered tool."""
        registry.register(sample_tool)
        tool = registry.get("double")
        assert tool is not None
        assert tool.name == "double"

    def test_get_nonexistent_tool(self, registry):
        """Test getting a tool that doesn't exist."""
        tool = registry.get("nonexistent")
        assert tool is None

    def test_unregister_tool(self, registry, sample_tool):
        """Test unregistering a tool."""
        registry.register(sample_tool)
        result = registry.unregister("double")
        assert result is True
        assert not registry.has("double")

    def test_unregister_nonexistent(self, registry):
        """Test unregistering a tool that doesn't exist."""
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get_all_tools(self, registry, sample_tool):
        """Test getting all tools."""
        registry.register(sample_tool)
        tools = registry.get_all()
        assert len(tools) == 1
        assert tools[0].name == "double"

    def test_list_names(self, registry, sample_tool):
        """Test listing tool names."""
        registry.register(sample_tool)
        names = registry.list_names()
        assert names == ["double"]

    def test_clear(self, registry, sample_tool):
        """Test clearing all tools."""
        registry.register(sample_tool)
        registry.clear()
        assert len(registry) == 0

    def test_iteration(self, registry, sample_tool):
        """Test iterating over tools."""
        registry.register(sample_tool)
        tools = list(registry)
        assert len(tools) == 1

    def test_contains(self, registry, sample_tool):
        """Test 'in' operator."""
        registry.register(sample_tool)
        assert "double" in registry
        assert "nonexistent" not in registry


class TestTool:
    """Tests for Tool class."""

    @pytest.mark.asyncio
    async def test_tool_execution(self, sample_tool):
        """Test executing a tool."""
        result = await sample_tool.execute(x=5)
        assert result == 10

    def test_openai_format(self, sample_tool):
        """Test conversion to OpenAI format."""
        formatted = sample_tool.to_openai_format()
        assert formatted["type"] == "function"
        assert formatted["function"]["name"] == "double"
        assert "properties" in formatted["function"]["parameters"]

    def test_anthropic_format(self, sample_tool):
        """Test conversion to Anthropic format."""
        formatted = sample_tool.to_anthropic_format()
        assert formatted["name"] == "double"
        assert "input_schema" in formatted
