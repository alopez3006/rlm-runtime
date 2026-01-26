"""Tests for RLM exception hierarchy."""

from rlm.core.exceptions import (
    BackendAuthError,
    BackendConnectionError,
    BackendError,
    BackendRateLimitError,
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    MaxDepthExceeded,
    REPLError,
    REPLExecutionError,
    REPLImportError,
    REPLSecurityError,
    REPLTimeoutError,
    RLMError,
    TimeoutExceeded,
    TokenBudgetExhausted,
    ToolBudgetExhausted,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)


class TestRLMError:
    """Tests for base RLMError class."""

    def test_message_only(self):
        """Should store message."""
        err = RLMError("Test error")
        assert err.message == "Test error"
        assert str(err) == "Test error"

    def test_message_with_context(self):
        """Should format message with context."""
        err = RLMError("Test error", key="value", num=42)
        assert err.message == "Test error"
        assert err.context == {"key": "value", "num": 42}
        assert "key=value" in str(err)
        assert "num=42" in str(err)

    def test_inherits_from_exception(self):
        """Should inherit from Exception."""
        err = RLMError("Test")
        assert isinstance(err, Exception)


class TestMaxDepthExceeded:
    """Tests for MaxDepthExceeded exception."""

    def test_attributes(self):
        """Should store depth and max_depth."""
        err = MaxDepthExceeded(depth=5, max_depth=4)
        assert err.depth == 5
        assert err.max_depth == 4

    def test_message_format(self):
        """Should format message with depth info."""
        err = MaxDepthExceeded(depth=5, max_depth=4)
        assert "5/4" in str(err)
        assert "depth" in str(err).lower()

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = MaxDepthExceeded(depth=5, max_depth=4)
        assert isinstance(err, RLMError)


class TestTokenBudgetExhausted:
    """Tests for TokenBudgetExhausted exception."""

    def test_attributes(self):
        """Should store tokens_used and budget."""
        err = TokenBudgetExhausted(tokens_used=10000, budget=8000)
        assert err.tokens_used == 10000
        assert err.budget == 8000

    def test_message_format(self):
        """Should format message with token info."""
        err = TokenBudgetExhausted(tokens_used=10000, budget=8000)
        assert "10000" in str(err)
        assert "8000" in str(err)
        assert "token" in str(err).lower()

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = TokenBudgetExhausted(tokens_used=10000, budget=8000)
        assert isinstance(err, RLMError)


class TestToolBudgetExhausted:
    """Tests for ToolBudgetExhausted exception."""

    def test_attributes(self):
        """Should store calls_made and budget."""
        err = ToolBudgetExhausted(calls_made=25, budget=20)
        assert err.calls_made == 25
        assert err.budget == 20

    def test_message_format(self):
        """Should format message with call info."""
        err = ToolBudgetExhausted(calls_made=25, budget=20)
        assert "25" in str(err)
        assert "20" in str(err)

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = ToolBudgetExhausted(calls_made=25, budget=20)
        assert isinstance(err, RLMError)


class TestTimeoutExceeded:
    """Tests for TimeoutExceeded exception."""

    def test_attributes(self):
        """Should store elapsed and timeout seconds."""
        err = TimeoutExceeded(elapsed_seconds=125.5, timeout_seconds=120)
        assert err.elapsed_seconds == 125.5
        assert err.timeout_seconds == 120

    def test_message_format(self):
        """Should format message with time info."""
        err = TimeoutExceeded(elapsed_seconds=125.5, timeout_seconds=120)
        assert "125.5" in str(err)
        assert "120" in str(err)

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = TimeoutExceeded(elapsed_seconds=125.5, timeout_seconds=120)
        assert isinstance(err, RLMError)


class TestREPLError:
    """Tests for REPLError base exception."""

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = REPLError("Test REPL error")
        assert isinstance(err, RLMError)


class TestREPLExecutionError:
    """Tests for REPLExecutionError exception."""

    def test_attributes(self):
        """Should store code, error, and output."""
        err = REPLExecutionError(
            code="print(undefined)",
            error="NameError: name 'undefined' is not defined",
            output="",
        )
        assert err.code == "print(undefined)"
        assert err.error == "NameError: name 'undefined' is not defined"
        assert err.output == ""

    def test_default_output(self):
        """Should default output to empty string."""
        err = REPLExecutionError(code="x", error="error")
        assert err.output == ""

    def test_truncates_long_error(self):
        """Should truncate long error in message."""
        long_error = "x" * 300
        err = REPLExecutionError(code="x", error=long_error)
        # Message should be truncated, but full error stored
        assert len(err.error) == 300
        assert len(err.message) < 300

    def test_inherits_from_repl_error(self):
        """Should inherit from REPLError."""
        err = REPLExecutionError(code="x", error="y")
        assert isinstance(err, REPLError)


class TestREPLTimeoutError:
    """Tests for REPLTimeoutError exception."""

    def test_attributes(self):
        """Should store code and timeout."""
        err = REPLTimeoutError(code="while True: pass", timeout=30)
        assert err.code == "while True: pass"
        assert err.timeout == 30

    def test_message_format(self):
        """Should include timeout in message."""
        err = REPLTimeoutError(code="x", timeout=30)
        assert "30" in str(err)
        assert "timeout" in str(err).lower()

    def test_inherits_from_repl_error(self):
        """Should inherit from REPLError."""
        err = REPLTimeoutError(code="x", timeout=30)
        assert isinstance(err, REPLError)


class TestREPLImportError:
    """Tests for REPLImportError exception."""

    def test_attributes(self):
        """Should store module and allowed list."""
        err = REPLImportError(module="os", allowed=["math", "json"])
        assert err.module == "os"
        assert err.allowed == ["math", "json"]

    def test_default_allowed(self):
        """Should default allowed to empty list."""
        err = REPLImportError(module="os")
        assert err.allowed == []

    def test_message_format(self):
        """Should include module name in message."""
        err = REPLImportError(module="subprocess")
        assert "subprocess" in str(err)
        assert "blocked" in str(err).lower()

    def test_inherits_from_repl_error(self):
        """Should inherit from REPLError."""
        err = REPLImportError(module="os")
        assert isinstance(err, REPLError)


class TestREPLSecurityError:
    """Tests for REPLSecurityError exception."""

    def test_attributes(self):
        """Should store violation description."""
        err = REPLSecurityError(violation="Attempted file system access")
        assert err.violation == "Attempted file system access"

    def test_message_format(self):
        """Should include violation in message."""
        err = REPLSecurityError(violation="network access")
        assert "network access" in str(err)
        assert "security" in str(err).lower()

    def test_inherits_from_repl_error(self):
        """Should inherit from REPLError."""
        err = REPLSecurityError(violation="test")
        assert isinstance(err, REPLError)


class TestToolError:
    """Tests for ToolError base exception."""

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = ToolError("Test tool error")
        assert isinstance(err, RLMError)


class TestToolNotFoundError:
    """Tests for ToolNotFoundError exception."""

    def test_attributes(self):
        """Should store tool_name and available_tools."""
        err = ToolNotFoundError(
            tool_name="unknown_tool",
            available_tools=["tool1", "tool2"],
        )
        assert err.tool_name == "unknown_tool"
        assert err.available_tools == ["tool1", "tool2"]

    def test_default_available_tools(self):
        """Should default available_tools to empty list."""
        err = ToolNotFoundError(tool_name="unknown")
        assert err.available_tools == []

    def test_message_format(self):
        """Should include tool name in message."""
        err = ToolNotFoundError(tool_name="missing_tool")
        assert "missing_tool" in str(err)
        assert "not found" in str(err).lower()

    def test_inherits_from_tool_error(self):
        """Should inherit from ToolError."""
        err = ToolNotFoundError(tool_name="x")
        assert isinstance(err, ToolError)


class TestToolExecutionError:
    """Tests for ToolExecutionError exception."""

    def test_attributes(self):
        """Should store tool_name, error, and arguments."""
        err = ToolExecutionError(
            tool_name="my_tool",
            error="Execution failed",
            arguments={"arg1": "val1"},
        )
        assert err.tool_name == "my_tool"
        assert err.error == "Execution failed"
        assert err.arguments == {"arg1": "val1"}

    def test_default_arguments(self):
        """Should default arguments to empty dict."""
        err = ToolExecutionError(tool_name="x", error="y")
        assert err.arguments == {}

    def test_truncates_long_error(self):
        """Should truncate long error in message."""
        long_error = "e" * 300
        err = ToolExecutionError(tool_name="x", error=long_error)
        assert len(err.error) == 300  # Full error stored

    def test_inherits_from_tool_error(self):
        """Should inherit from ToolError."""
        err = ToolExecutionError(tool_name="x", error="y")
        assert isinstance(err, ToolError)


class TestToolValidationError:
    """Tests for ToolValidationError exception."""

    def test_attributes(self):
        """Should store tool_name, validation_error, and arguments."""
        err = ToolValidationError(
            tool_name="my_tool",
            validation_error="Missing required argument",
            arguments={"incomplete": True},
        )
        assert err.tool_name == "my_tool"
        assert err.validation_error == "Missing required argument"
        assert err.arguments == {"incomplete": True}

    def test_default_arguments(self):
        """Should default arguments to empty dict."""
        err = ToolValidationError(tool_name="x", validation_error="y")
        assert err.arguments == {}

    def test_message_format(self):
        """Should include validation error in message."""
        err = ToolValidationError(tool_name="tool", validation_error="invalid type")
        assert "tool" in str(err)
        assert "invalid type" in str(err)

    def test_inherits_from_tool_error(self):
        """Should inherit from ToolError."""
        err = ToolValidationError(tool_name="x", validation_error="y")
        assert isinstance(err, ToolError)


class TestBackendError:
    """Tests for BackendError base exception."""

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = BackendError("Test backend error")
        assert isinstance(err, RLMError)


class TestBackendConnectionError:
    """Tests for BackendConnectionError exception."""

    def test_attributes(self):
        """Should store backend, provider, and error."""
        err = BackendConnectionError(
            backend="litellm",
            provider="openai",
            error="Connection refused",
        )
        assert err.backend == "litellm"
        assert err.provider == "openai"
        assert err.error == "Connection refused"

    def test_message_format(self):
        """Should include backend and provider in message."""
        err = BackendConnectionError(
            backend="litellm",
            provider="anthropic",
            error="timeout",
        )
        assert "litellm" in str(err)
        assert "anthropic" in str(err)

    def test_inherits_from_backend_error(self):
        """Should inherit from BackendError."""
        err = BackendConnectionError(backend="x", provider="y", error="z")
        assert isinstance(err, BackendError)


class TestBackendRateLimitError:
    """Tests for BackendRateLimitError exception."""

    def test_attributes(self):
        """Should store retry_after."""
        err = BackendRateLimitError(message="Rate limited", retry_after=60)
        assert err.retry_after == 60

    def test_default_retry_after(self):
        """Should default retry_after to None."""
        err = BackendRateLimitError(message="Rate limited")
        assert err.retry_after is None

    def test_inherits_from_backend_error(self):
        """Should inherit from BackendError."""
        err = BackendRateLimitError(message="x")
        assert isinstance(err, BackendError)


class TestBackendAuthError:
    """Tests for BackendAuthError exception."""

    def test_attributes(self):
        """Should store provider."""
        err = BackendAuthError(provider="openai")
        assert err.provider == "openai"

    def test_message_format(self):
        """Should include provider in message."""
        err = BackendAuthError(provider="anthropic")
        assert "anthropic" in str(err)
        assert "authentication" in str(err).lower() or "api key" in str(err).lower()

    def test_inherits_from_backend_error(self):
        """Should inherit from BackendError."""
        err = BackendAuthError(provider="x")
        assert isinstance(err, BackendError)


class TestConfigError:
    """Tests for ConfigError base exception."""

    def test_inherits_from_rlm_error(self):
        """Should inherit from RLMError."""
        err = ConfigError("Test config error")
        assert isinstance(err, RLMError)


class TestConfigNotFoundError:
    """Tests for ConfigNotFoundError exception."""

    def test_attributes(self):
        """Should store path."""
        err = ConfigNotFoundError(path="/path/to/config.toml")
        assert err.path == "/path/to/config.toml"

    def test_message_format(self):
        """Should include path in message."""
        err = ConfigNotFoundError(path="/config/rlm.toml")
        assert "/config/rlm.toml" in str(err)
        assert "not found" in str(err).lower()

    def test_inherits_from_config_error(self):
        """Should inherit from ConfigError."""
        err = ConfigNotFoundError(path="x")
        assert isinstance(err, ConfigError)


class TestConfigValidationError:
    """Tests for ConfigValidationError exception."""

    def test_attributes(self):
        """Should store field, value, and expected."""
        err = ConfigValidationError(
            field="max_depth",
            value=-1,
            expected="positive integer",
        )
        assert err.field == "max_depth"
        assert err.value == -1
        assert err.expected == "positive integer"

    def test_message_format(self):
        """Should include field, value, and expected in message."""
        err = ConfigValidationError(
            field="timeout",
            value="invalid",
            expected="integer in seconds",
        )
        assert "timeout" in str(err)
        assert "invalid" in str(err)
        assert "integer in seconds" in str(err)

    def test_inherits_from_config_error(self):
        """Should inherit from ConfigError."""
        err = ConfigValidationError(field="x", value="y", expected="z")
        assert isinstance(err, ConfigError)


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_all_inherit_from_rlm_error(self):
        """All custom exceptions should inherit from RLMError."""
        exceptions = [
            MaxDepthExceeded(1, 1),
            TokenBudgetExhausted(1, 1),
            ToolBudgetExhausted(1, 1),
            TimeoutExceeded(1.0, 1),
            REPLError("test"),
            REPLExecutionError("x", "y"),
            REPLTimeoutError("x", 1),
            REPLImportError("x"),
            REPLSecurityError("x"),
            ToolError("test"),
            ToolNotFoundError("x"),
            ToolExecutionError("x", "y"),
            ToolValidationError("x", "y"),
            BackendError("test"),
            BackendConnectionError("x", "y", "z"),
            BackendRateLimitError("x"),
            BackendAuthError("x"),
            ConfigError("test"),
            ConfigNotFoundError("x"),
            ConfigValidationError("x", "y", "z"),
        ]

        for exc in exceptions:
            assert isinstance(exc, RLMError), f"{type(exc).__name__} should inherit from RLMError"

    def test_repl_errors_inherit_from_repl_error(self):
        """REPL exceptions should inherit from REPLError."""
        repl_exceptions = [
            REPLExecutionError("x", "y"),
            REPLTimeoutError("x", 1),
            REPLImportError("x"),
            REPLSecurityError("x"),
        ]

        for exc in repl_exceptions:
            assert isinstance(exc, REPLError)

    def test_tool_errors_inherit_from_tool_error(self):
        """Tool exceptions should inherit from ToolError."""
        tool_exceptions = [
            ToolNotFoundError("x"),
            ToolExecutionError("x", "y"),
            ToolValidationError("x", "y"),
        ]

        for exc in tool_exceptions:
            assert isinstance(exc, ToolError)

    def test_backend_errors_inherit_from_backend_error(self):
        """Backend exceptions should inherit from BackendError."""
        backend_exceptions = [
            BackendConnectionError("x", "y", "z"),
            BackendRateLimitError("x"),
            BackendAuthError("x"),
        ]

        for exc in backend_exceptions:
            assert isinstance(exc, BackendError)

    def test_config_errors_inherit_from_config_error(self):
        """Config exceptions should inherit from ConfigError."""
        config_exceptions = [
            ConfigNotFoundError("x"),
            ConfigValidationError("x", "y", "z"),
        ]

        for exc in config_exceptions:
            assert isinstance(exc, ConfigError)
