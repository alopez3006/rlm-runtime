"""RLM Runtime exceptions.

This module defines the exception hierarchy for RLM Runtime.
All RLM-specific exceptions inherit from RLMError.

Example:
    ```python
    from rlm.core.exceptions import (
        RLMError,
        MaxDepthExceeded,
        TokenBudgetExhausted,
        REPLExecutionError,
    )

    try:
        result = await rlm.completion("Complex task...")
    except MaxDepthExceeded as e:
        print(f"Hit max depth: {e.depth}/{e.max_depth}")
    except TokenBudgetExhausted as e:
        print(f"Used {e.tokens_used} tokens, budget was {e.budget}")
    except REPLExecutionError as e:
        print(f"Code failed: {e.error}")
    except RLMError as e:
        print(f"RLM error: {e}")
    ```
"""

from __future__ import annotations

from typing import Any


class RLMError(Exception):
    """Base exception for all RLM errors.

    All RLM-specific exceptions inherit from this class.
    """

    def __init__(self, message: str, **context: Any):
        """Initialize the exception.

        Args:
            message: Human-readable error message
            **context: Additional context for debugging
        """
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        if self.context:
            ctx = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx})"
        return self.message


# Recursion and Budget Errors


class MaxDepthExceeded(RLMError):
    """Raised when the maximum recursion depth is exceeded.

    Attributes:
        depth: Current depth when limit was hit
        max_depth: Configured maximum depth
    """

    def __init__(self, depth: int, max_depth: int):
        super().__init__(
            f"Maximum recursion depth exceeded: {depth}/{max_depth}",
            depth=depth,
            max_depth=max_depth,
        )
        self.depth = depth
        self.max_depth = max_depth


class TokenBudgetExhausted(RLMError):
    """Raised when the token budget is exhausted.

    Attributes:
        tokens_used: Number of tokens used
        budget: Configured token budget
    """

    def __init__(self, tokens_used: int, budget: int):
        super().__init__(
            f"Token budget exhausted: {tokens_used}/{budget} tokens used",
            tokens_used=tokens_used,
            budget=budget,
        )
        self.tokens_used = tokens_used
        self.budget = budget


class CostBudgetExhausted(RLMError):
    """Raised when the cost budget is exhausted.

    Attributes:
        cost_used: Amount spent in USD
        budget: Configured cost budget in USD
    """

    def __init__(self, cost_used: float, budget: float):
        super().__init__(
            f"Cost budget exhausted: ${cost_used:.4f}/${budget:.4f} USD",
            cost_used=cost_used,
            budget=budget,
        )
        self.cost_used = cost_used
        self.budget = budget


class ToolBudgetExhausted(RLMError):
    """Raised when the tool call budget is exhausted.

    Attributes:
        calls_made: Number of tool calls made
        budget: Configured tool budget
    """

    def __init__(self, calls_made: int, budget: int):
        super().__init__(
            f"Tool budget exhausted: {calls_made}/{budget} calls made",
            calls_made=calls_made,
            budget=budget,
        )
        self.calls_made = calls_made
        self.budget = budget


class TimeoutExceeded(RLMError):
    """Raised when the execution timeout is exceeded.

    Attributes:
        elapsed_seconds: Time elapsed before timeout
        timeout_seconds: Configured timeout
    """

    def __init__(self, elapsed_seconds: float, timeout_seconds: int):
        super().__init__(
            f"Execution timeout exceeded: {elapsed_seconds:.1f}s/{timeout_seconds}s",
            elapsed_seconds=elapsed_seconds,
            timeout_seconds=timeout_seconds,
        )
        self.elapsed_seconds = elapsed_seconds
        self.timeout_seconds = timeout_seconds


# REPL Errors


class REPLError(RLMError):
    """Base exception for REPL-related errors."""

    pass


class REPLExecutionError(REPLError):
    """Raised when code execution fails in the REPL.

    Attributes:
        code: The code that failed
        error: Error message from execution
        output: Any output before the error
    """

    def __init__(self, code: str, error: str, output: str = ""):
        super().__init__(
            f"REPL execution failed: {error[:100]}",
            code_length=len(code),
            error=error[:200],
        )
        self.code = code
        self.error = error
        self.output = output


class REPLTimeoutError(REPLError):
    """Raised when REPL execution times out.

    Attributes:
        code: The code that timed out
        timeout: Configured timeout in seconds
    """

    def __init__(self, code: str, timeout: int):
        super().__init__(
            f"REPL execution timed out after {timeout}s",
            code_length=len(code),
            timeout=timeout,
        )
        self.code = code
        self.timeout = timeout


class REPLImportError(REPLError):
    """Raised when an import is blocked by the sandbox.

    Attributes:
        module: The module that was blocked
        allowed: List of allowed modules
    """

    def __init__(self, module: str, allowed: list[str] | None = None):
        super().__init__(
            f"Import blocked: '{module}' is not in the allowed list",
            module=module,
        )
        self.module = module
        self.allowed = allowed or []


class REPLSecurityError(REPLError):
    """Raised when a security violation is detected.

    Attributes:
        violation: Description of the security violation
    """

    def __init__(self, violation: str):
        super().__init__(
            f"Security violation: {violation}",
            violation=violation,
        )
        self.violation = violation


class REPLResourceExceeded(REPLError):
    """Raised when a resource limit is exceeded during REPL execution.

    Attributes:
        resource: Type of resource exceeded (memory, cpu, timeout)
        limit: Configured limit value
        actual: Actual usage (if known)
    """

    def __init__(self, resource: str, limit: str, actual: str | None = None):
        if actual:
            message = f"Resource limit exceeded: {resource} ({actual}/{limit})"
        else:
            message = f"Resource limit exceeded: {resource} (limit: {limit})"
        super().__init__(
            message,
            resource=resource,
            limit=limit,
        )
        self.resource = resource
        self.limit = limit
        self.actual = actual


# Tool Errors


class ToolError(RLMError):
    """Base exception for tool-related errors."""

    pass


class ToolNotFoundError(ToolError):
    """Raised when a tool is not found in the registry.

    Attributes:
        tool_name: Name of the tool that was not found
        available_tools: List of available tool names
    """

    def __init__(self, tool_name: str, available_tools: list[str] | None = None):
        super().__init__(
            f"Tool not found: '{tool_name}'",
            tool_name=tool_name,
            available_count=len(available_tools) if available_tools else 0,
        )
        self.tool_name = tool_name
        self.available_tools = available_tools or []


class ToolExecutionError(ToolError):
    """Raised when a tool execution fails.

    Attributes:
        tool_name: Name of the tool that failed
        error: Error message from execution
        arguments: Arguments passed to the tool
    """

    def __init__(self, tool_name: str, error: str, arguments: dict[str, Any] | None = None):
        super().__init__(
            f"Tool '{tool_name}' failed: {error[:100]}",
            tool_name=tool_name,
            error=error[:200],
        )
        self.tool_name = tool_name
        self.error = error
        self.arguments = arguments or {}


class ToolValidationError(ToolError):
    """Raised when tool arguments fail validation.

    Attributes:
        tool_name: Name of the tool
        validation_error: Description of the validation error
        arguments: Invalid arguments
    """

    def __init__(self, tool_name: str, validation_error: str, arguments: dict[str, Any] | None = None):
        super().__init__(
            f"Tool '{tool_name}' validation failed: {validation_error}",
            tool_name=tool_name,
            validation_error=validation_error,
        )
        self.tool_name = tool_name
        self.validation_error = validation_error
        self.arguments = arguments or {}


# Backend Errors


class BackendError(RLMError):
    """Base exception for LLM backend errors."""

    pass


class BackendConnectionError(BackendError):
    """Raised when connection to the LLM backend fails.

    Attributes:
        backend: Name of the backend
        provider: LLM provider name
    """

    def __init__(self, backend: str, provider: str, error: str):
        super().__init__(
            f"Failed to connect to {backend}/{provider}: {error[:100]}",
            backend=backend,
            provider=provider,
        )
        self.backend = backend
        self.provider = provider
        self.error = error


class BackendRateLimitError(BackendError):
    """Raised when the LLM backend rate limit is hit.

    Attributes:
        retry_after: Seconds to wait before retrying (if available)
    """

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(
            message,
            retry_after=retry_after,
        )
        self.retry_after = retry_after


class BackendAuthError(BackendError):
    """Raised when LLM backend authentication fails.

    Attributes:
        provider: LLM provider name
    """

    def __init__(self, provider: str):
        super().__init__(
            f"Authentication failed for {provider}. Check your API key.",
            provider=provider,
        )
        self.provider = provider


# Configuration Errors


class ConfigError(RLMError):
    """Base exception for configuration errors."""

    pass


class ConfigNotFoundError(ConfigError):
    """Raised when a configuration file is not found.

    Attributes:
        path: Path to the missing config file
    """

    def __init__(self, path: str):
        super().__init__(
            f"Configuration file not found: {path}",
            path=path,
        )
        self.path = path


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails.

    Attributes:
        field: The field that failed validation
        value: The invalid value
        expected: Description of expected value
    """

    def __init__(self, field: str, value: Any, expected: str):
        super().__init__(
            f"Invalid config '{field}': got {value!r}, expected {expected}",
            field=field,
            value=value,
            expected=expected,
        )
        self.field = field
        self.value = value
        self.expected = expected
