"""RLM Orchestrator - the main entry point for recursive completions."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from rlm.core.config import RLMConfig, load_config
from rlm.core.exceptions import (
    CostBudgetExhausted,
    MaxDepthExceeded,
    TimeoutExceeded,
    TokenBudgetExhausted,
    ToolExecutionError,
    ToolNotFoundError,
)
from rlm.core.pricing import estimate_cost
from rlm.core.types import (
    CompletionOptions,
    Message,
    RLMResult,
    StreamOptions,
    ToolCall,
    ToolResult,
    TrajectoryEvent,
)

if TYPE_CHECKING:
    from rlm.backends.base import BaseBackend, Tool
    from rlm.repl.base import BaseREPL

logger = structlog.get_logger()


class RLM:
    """Recursive Language Model runtime.

    The main entry point for recursive LLM completions with tool use
    and sandboxed code execution.

    Example:
        ```python
        from rlm import RLM

        rlm = RLM(model="gpt-4o-mini", environment="docker")
        result = await rlm.completion("Analyze data.csv")
        print(result.response)
        ```
    """

    def __init__(
        self,
        backend: str | BaseBackend = "litellm",
        model: str = "gpt-4o-mini",
        environment: str | BaseREPL = "local",
        config: RLMConfig | None = None,
        tools: list[Tool] | None = None,
        verbose: bool = False,
        snipara_api_key: str | None = None,
        snipara_project_slug: str | None = None,
    ):
        """Initialize the RLM runtime.

        Args:
            backend: LLM backend ("litellm", "openai", "anthropic") or instance
            model: Model name to use (e.g., "gpt-4o-mini", "claude-3-sonnet")
            environment: REPL environment ("local", "docker") or instance
            config: Optional RLMConfig instance
            tools: Optional list of custom tools to register
            verbose: Enable verbose logging
            snipara_api_key: Snipara API key (or set SNIPARA_API_KEY env var)
            snipara_project_slug: Snipara project slug (or set SNIPARA_PROJECT_SLUG)
        """
        self.config = config or load_config()
        self.verbose = verbose or self.config.verbose

        # Override config with explicit parameters
        if snipara_api_key:
            self.config.snipara_api_key = snipara_api_key
        if snipara_project_slug:
            self.config.snipara_project_slug = snipara_project_slug

        # Setup backend
        if isinstance(backend, str):
            self.backend = self._create_backend(backend, model)
        else:
            self.backend = backend

        # Setup REPL
        if isinstance(environment, str):
            self.repl = self._create_repl(environment)
        else:
            self.repl = environment

        # Setup tools
        from rlm.tools.registry import ToolRegistry

        self.tool_registry = ToolRegistry()

        # Register builtin tools
        self._register_builtin_tools()

        # Register custom tools
        if tools:
            for tool in tools:
                self.tool_registry.register(tool)

        # Auto-register Snipara tools if available
        self._register_snipara_tools()

        # Setup logging
        from rlm.logging.trajectory import TrajectoryLogger

        self.trajectory_logger = TrajectoryLogger(
            log_dir=self.config.log_dir,
            verbose=self.verbose,
        )

        if self.verbose:
            logger.info(
                "RLM initialized",
                backend=backend if isinstance(backend, str) else type(backend).__name__,
                model=model,
                environment=environment if isinstance(environment, str) else type(environment).__name__,
                tools_count=len(self.tool_registry),
                snipara_enabled=self.config.snipara_enabled,
            )

    def _create_backend(self, backend: str, model: str) -> BaseBackend:
        """Create backend from string identifier."""
        from rlm.backends.litellm import LiteLLMBackend

        if backend == "litellm":
            return LiteLLMBackend(model=model, temperature=self.config.temperature)
        if backend == "openai":
            return LiteLLMBackend(model=model, temperature=self.config.temperature)
        if backend == "anthropic":
            return LiteLLMBackend(model=model, temperature=self.config.temperature)

        raise ValueError(f"Unknown backend: {backend}. Supported: litellm, openai, anthropic")

    def _create_repl(self, environment: str) -> BaseREPL:
        """Create REPL from string identifier."""
        from rlm.repl.local import LocalREPL

        if environment == "local":
            return LocalREPL(timeout=self.config.docker_timeout)

        if environment == "docker":
            try:
                from rlm.repl.docker import DockerREPL

                return DockerREPL(
                    image=self.config.docker_image,
                    cpus=self.config.docker_cpus,
                    memory=self.config.docker_memory,
                    timeout=self.config.docker_timeout,
                    network_disabled=self.config.docker_network_disabled,
                )
            except ImportError:
                raise ImportError(
                    "Docker support requires 'docker' package. "
                    "Install with: pip install rlm-runtime[docker]"
                ) from None

        if environment == "wasm":
            try:
                from rlm.repl.wasm import WasmREPL

                return WasmREPL(timeout=self.config.docker_timeout)
            except ImportError:
                raise ImportError(
                    "WebAssembly support requires 'pyodide' package. "
                    "Install with: pip install pyodide-py"
                ) from None

        raise ValueError(f"Unknown environment: {environment}. Supported: local, docker, wasm")

    def _register_builtin_tools(self) -> None:
        """Register builtin tools."""
        from rlm.tools.builtin import get_builtin_tools

        for tool in get_builtin_tools(self.repl, self.config.allowed_paths):
            self.tool_registry.register(tool)

    def _register_snipara_tools(self) -> None:
        """Register Snipara tools if snipara-mcp is installed and configured."""
        if not self.config.snipara_enabled:
            logger.debug("Snipara not configured, skipping tool registration")
            return

        try:
            from snipara_mcp.rlm_tools import get_snipara_tools

            tools = get_snipara_tools(
                api_key=self.config.snipara_api_key,
                project_slug=self.config.snipara_project_slug,
            )
            for tool in tools:
                self.tool_registry.register(tool)
            logger.info("Snipara tools registered", count=len(tools))
        except ImportError:
            logger.debug(
                "snipara-mcp not installed, skipping Snipara tools. "
                "Install with: pip install rlm-runtime[snipara]"
            )

    async def completion(
        self,
        prompt: str,
        system: str | None = None,
        options: CompletionOptions | None = None,
    ) -> RLMResult:
        """Execute a recursive completion.

        The LLM can call tools, execute code in the REPL, and spawn
        sub-completions up to the configured depth limit.

        Args:
            prompt: The user's prompt/question
            system: Optional system message for context
            options: Completion options (limits, budgets, etc.)

        Returns:
            RLMResult with the response and execution trajectory

        Example:
            ```python
            result = await rlm.completion(
                "Find all TODO comments in the codebase",
                system="You are a code analyst.",
                options=CompletionOptions(max_depth=3),
            )
            print(result.response)
            ```
        """
        options = options or CompletionOptions(
            max_depth=self.config.max_depth,
            max_subcalls=self.config.max_subcalls,
            token_budget=self.config.token_budget,
            tool_budget=self.config.tool_budget,
            timeout_seconds=self.config.timeout_seconds,
        )

        trajectory_id = uuid4()
        start_time = time.time()
        events: list[TrajectoryEvent] = []

        # Build initial messages
        messages: list[Message] = []
        if system:
            messages.append(Message(role="system", content=system))
        messages.append(Message(role="user", content=prompt))

        if self.verbose:
            logger.info(
                "Starting completion",
                trajectory_id=str(trajectory_id),
                prompt_length=len(prompt),
            )

        # Execute recursive completion with timeout enforcement
        try:
            response, events = await asyncio.wait_for(
                self._recursive_complete(
                    messages=messages,
                    trajectory_id=trajectory_id,
                    parent_call_id=None,
                    depth=0,
                    options=options,
                    events=events,
                ),
                timeout=float(options.timeout_seconds),
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(
                "Completion timed out",
                timeout=options.timeout_seconds,
                elapsed=elapsed,
                trajectory_id=str(trajectory_id),
            )
            raise TimeoutExceeded(
                elapsed_seconds=elapsed,
                timeout_seconds=options.timeout_seconds,
            ) from None
        except Exception as e:
            logger.error("Completion failed", error=str(e), trajectory_id=str(trajectory_id))
            events.append(
                TrajectoryEvent(
                    trajectory_id=trajectory_id,
                    call_id=uuid4(),
                    parent_call_id=None,
                    depth=0,
                    prompt=prompt,
                    error=str(e),
                )
            )
            response = f"Error: {e}"

        # Calculate totals
        total_input_tokens = sum(e.input_tokens for e in events)
        total_output_tokens = sum(e.output_tokens for e in events)
        total_tokens = total_input_tokens + total_output_tokens
        total_tool_calls = sum(len(e.tool_calls) for e in events)
        duration_ms = int((time.time() - start_time) * 1000)

        # Calculate total cost (sum of event costs, or None if any are unknown)
        event_costs = [e.estimated_cost_usd for e in events]
        if all(c is not None for c in event_costs):
            total_cost_usd = sum(c for c in event_costs if c is not None)
        else:
            total_cost_usd = None

        # Log trajectory
        self.trajectory_logger.log_trajectory(trajectory_id, events)

        if self.verbose:
            from rlm.core.pricing import format_cost

            logger.info(
                "Completion finished",
                trajectory_id=str(trajectory_id),
                total_calls=len(events),
                total_tokens=total_tokens,
                total_cost=format_cost(total_cost_usd),
                duration_ms=duration_ms,
            )

        return RLMResult(
            response=response,
            trajectory_id=trajectory_id,
            total_calls=len(events),
            total_tokens=total_tokens,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tool_calls=total_tool_calls,
            duration_ms=duration_ms,
            total_cost_usd=total_cost_usd,
            events=events if options.include_trajectory else [],
        )

    async def _recursive_complete(
        self,
        messages: list[Message],
        trajectory_id: UUID,
        parent_call_id: UUID | None,
        depth: int,
        options: CompletionOptions,
        events: list[TrajectoryEvent],
    ) -> tuple[str, list[TrajectoryEvent]]:
        """Internal recursive completion loop."""
        call_id = uuid4()

        # Check depth limit
        if depth >= options.max_depth:
            raise MaxDepthExceeded(depth=depth, max_depth=options.max_depth)

        # Check subcall limit
        if len(events) >= options.max_subcalls:
            raise MaxDepthExceeded(depth=len(events), max_depth=options.max_subcalls)

        # Check token budget
        current_tokens = sum(e.input_tokens + e.output_tokens for e in events)
        if current_tokens >= options.token_budget:
            raise TokenBudgetExhausted(tokens_used=current_tokens, budget=options.token_budget)

        # Check cost budget
        if options.cost_budget_usd is not None:
            current_cost = sum(e.estimated_cost_usd or 0 for e in events)
            if current_cost >= options.cost_budget_usd:
                raise CostBudgetExhausted(cost_used=current_cost, budget=options.cost_budget_usd)

        # Get available tools
        tools = self.tool_registry.get_all()

        # Call backend
        start_time = time.time()
        response = await self.backend.complete(messages, tools=tools)
        duration_ms = int((time.time() - start_time) * 1000)

        # Calculate estimated cost for this call
        event_cost = estimate_cost(
            model=self.backend.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        # Create event
        event = TrajectoryEvent(
            trajectory_id=trajectory_id,
            call_id=call_id,
            parent_call_id=parent_call_id,
            depth=depth,
            prompt=messages[-1].content,
            response=response.content,
            tool_calls=response.tool_calls,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            duration_ms=duration_ms,
            estimated_cost_usd=event_cost,
        )

        # Handle tool calls
        if response.tool_calls:
            tool_results: list[ToolResult] = []

            for tool_call in response.tool_calls:
                # Check tool budget
                total_tool_calls = sum(len(e.tool_calls) for e in events) + len(tool_results)
                if total_tool_calls >= options.tool_budget:
                    tool_results.append(
                        ToolResult(
                            tool_call_id=tool_call.id,
                            content="Error: Tool budget exceeded. No more tool calls will be executed.",
                            is_error=True,
                        )
                    )
                    break  # Stop processing additional tool calls

                # Execute tool
                result = await self._execute_tool(tool_call)
                tool_results.append(result)

                if self.verbose:
                    logger.debug(
                        "Tool executed",
                        tool=tool_call.name,
                        is_error=result.is_error,
                    )

            event.tool_results = tool_results
            events.append(event)

            # Add assistant message with tool calls
            messages.append(
                Message(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            # Add tool results
            for result in tool_results:
                messages.append(
                    Message(
                        role="tool",
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                    )
                )

            # Recurse
            return await self._recursive_complete(
                messages=messages,
                trajectory_id=trajectory_id,
                parent_call_id=call_id,
                depth=depth + 1,
                options=options,
                events=events,
            )

        # No tool calls - we're done
        events.append(event)
        return response.content or "", events

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        try:
            tool = self.tool_registry.get(tool_call.name)
            if tool is None:
                available = [t.name for t in self.tool_registry.get_all()]
                error = ToolNotFoundError(tool_call.name, available)
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content=str(error),
                    is_error=True,
                )

            # Execute tool handler
            result = await tool.execute(**tool_call.arguments)

            return ToolResult(
                tool_call_id=tool_call.id,
                content=str(result),
            )

        except ToolExecutionError as e:
            logger.error("Tool execution failed", tool=tool_call.name, error=str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                content=str(e),
                is_error=True,
            )
        except Exception as e:
            logger.error("Tool execution failed", tool=tool_call.name, error=str(e))
            exec_error = ToolExecutionError(tool_call.name, str(e), tool_call.arguments)
            return ToolResult(
                tool_call_id=tool_call.id,
                content=str(exec_error),
                is_error=True,
            )

    async def stream(
        self,
        prompt: str,
        system: str | None = None,
        options: StreamOptions | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a simple completion (no tool use).

        This method streams tokens as they arrive from the LLM.
        Note: Streaming does not support tool calls - use completion()
        for tasks that require tool use.

        Args:
            prompt: The user's prompt/question
            system: Optional system message for context
            options: Optional streaming options (cost budget, timeout)

        Yields:
            str: Content chunks as they arrive

        Raises:
            CostBudgetExhausted: If estimated cost exceeds budget before starting

        Example:
            ```python
            async for chunk in rlm.stream("Explain quantum computing"):
                print(chunk, end="", flush=True)
            ```
        """
        from rlm.core.pricing import estimate_cost

        options = options or StreamOptions()
        messages: list[Message] = []
        if system:
            messages.append(Message(role="system", content=system))
        messages.append(Message(role="user", content=prompt))

        # Estimate input tokens (rough: ~4 chars per token)
        total_chars = sum(len(m.content) for m in messages)
        estimated_input_tokens = total_chars // 4

        # Check cost budget before starting (input tokens only)
        if options.cost_budget_usd is not None:
            input_cost = estimate_cost(self.backend.model, estimated_input_tokens, 0)
            if input_cost is not None and input_cost >= options.cost_budget_usd:
                raise CostBudgetExhausted(
                    cost_used=input_cost,
                    budget=options.cost_budget_usd,
                )

        if self.verbose:
            logger.info(
                "Starting stream",
                prompt_length=len(prompt),
                estimated_input_tokens=estimated_input_tokens,
            )

        output_chars = 0
        async for chunk in self.backend.stream(messages):
            output_chars += len(chunk)
            yield chunk

        # Log final cost estimate
        estimated_output_tokens = output_chars // 4
        final_cost = estimate_cost(
            self.backend.model, estimated_input_tokens, estimated_output_tokens
        )
        if self.verbose:
            logger.info(
                "Stream completed",
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                estimated_cost_usd=final_cost,
            )
