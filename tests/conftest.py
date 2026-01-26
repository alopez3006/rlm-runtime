"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rlm.backends.base import BackendResponse, Tool
from rlm.repl.local import LocalREPL


@pytest.fixture
def local_repl():
    """Create a LocalREPL instance for testing."""
    return LocalREPL(timeout=10)


@pytest.fixture
def mock_backend():
    """Create a mock LLM backend."""
    backend = MagicMock()
    backend.complete = AsyncMock(
        return_value=BackendResponse(
            content="Test response",
            tool_calls=[],
            input_tokens=10,
            output_tokens=5,
            finish_reason="stop",
        )
    )
    return backend


@pytest.fixture
def sample_tool():
    """Create a sample tool for testing."""

    async def handler(x: int, y: int) -> int:
        return x + y

    return Tool(
        name="add",
        description="Add two numbers",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
        handler=handler,
    )


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary log directory."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def sample_code():
    """Sample Python code for REPL tests."""
    return """
x = 1 + 1
result = x * 2
print(f"x = {x}")
"""
