"""Unit tests for core types."""

from uuid import uuid4

from rlm.core.types import (
    CompletionOptions,
    Message,
    REPLResult,
    RLMResult,
    ToolCall,
    ToolResult,
    TrajectoryEvent,
)


class TestMessage:
    """Tests for Message dataclass."""

    def test_basic_message(self):
        """Test creating a basic message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls == []

    def test_message_with_tool_calls(self):
        """Test message with tool calls."""
        tool_call = ToolCall(id="1", name="test", arguments={"x": 1})
        msg = Message(role="assistant", content="", tool_calls=[tool_call])
        assert len(msg.tool_calls) == 1

    def test_message_to_dict(self):
        """Test message serialization."""
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_tool_call(self):
        """Test creating a tool call."""
        tc = ToolCall(id="abc", name="test_tool", arguments={"a": 1, "b": 2})
        assert tc.id == "abc"
        assert tc.name == "test_tool"
        assert tc.arguments == {"a": 1, "b": 2}

    def test_tool_call_to_dict(self):
        """Test tool call serialization."""
        tc = ToolCall(id="abc", name="test", arguments={})
        d = tc.to_dict()
        assert d["id"] == "abc"
        assert d["name"] == "test"


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self):
        """Test successful tool result."""
        tr = ToolResult(tool_call_id="1", content="result data")
        assert tr.is_error is False

    def test_error_result(self):
        """Test error tool result."""
        tr = ToolResult(tool_call_id="1", content="error message", is_error=True)
        assert tr.is_error is True


class TestREPLResult:
    """Tests for REPLResult dataclass."""

    def test_success_result(self):
        """Test successful REPL result."""
        result = REPLResult(output="42", execution_time_ms=10)
        assert result.success
        assert result.output == "42"

    def test_error_result(self):
        """Test REPL error result."""
        result = REPLResult(output="", error="SyntaxError")
        assert not result.success

    def test_truncated_result(self):
        """Test truncated REPL result."""
        result = REPLResult(output="...", truncated=True)
        assert result.truncated


class TestTrajectoryEvent:
    """Tests for TrajectoryEvent dataclass."""

    def test_basic_event(self):
        """Test creating a basic event."""
        event = TrajectoryEvent(
            trajectory_id=uuid4(),
            call_id=uuid4(),
            parent_call_id=None,
            depth=0,
            prompt="test prompt",
        )
        assert event.depth == 0
        assert event.prompt == "test prompt"

    def test_event_to_dict(self):
        """Test event serialization."""
        tid = uuid4()
        cid = uuid4()
        event = TrajectoryEvent(
            trajectory_id=tid,
            call_id=cid,
            parent_call_id=None,
            depth=0,
            prompt="test",
            response="response",
            input_tokens=10,
            output_tokens=5,
        )
        d = event.to_dict()
        assert d["trajectory_id"] == str(tid)
        assert d["call_id"] == str(cid)
        assert d["input_tokens"] == 10


class TestRLMResult:
    """Tests for RLMResult dataclass."""

    def test_successful_result(self):
        """Test successful RLM result."""
        result = RLMResult(
            response="answer",
            trajectory_id=uuid4(),
            total_calls=2,
            total_tokens=100,
            total_tool_calls=1,
            duration_ms=500,
        )
        assert result.success
        assert result.response == "answer"

    def test_result_with_error(self):
        """Test RLM result with error event."""
        event = TrajectoryEvent(
            trajectory_id=uuid4(),
            call_id=uuid4(),
            parent_call_id=None,
            depth=0,
            prompt="test",
            error="Something went wrong",
        )
        result = RLMResult(
            response="",
            trajectory_id=uuid4(),
            total_calls=1,
            total_tokens=0,
            total_tool_calls=0,
            duration_ms=100,
            events=[event],
        )
        assert not result.success


class TestCompletionOptions:
    """Tests for CompletionOptions dataclass."""

    def test_default_options(self):
        """Test default completion options."""
        opts = CompletionOptions()
        assert opts.max_depth == 4
        assert opts.max_subcalls == 12
        assert opts.token_budget == 8000

    def test_custom_options(self):
        """Test custom completion options."""
        opts = CompletionOptions(
            max_depth=2,
            token_budget=4000,
            include_trajectory=True,
        )
        assert opts.max_depth == 2
        assert opts.token_budget == 4000
        assert opts.include_trajectory is True
