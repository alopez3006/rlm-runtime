"""Autonomous agent runner."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from rlm.agent.config import AgentConfig
from rlm.agent.guardrails import check_iteration_allowed
from rlm.agent.prompts import AGENT_SYSTEM_PROMPT, build_iteration_prompt
from rlm.agent.result import AgentResult
from rlm.agent.terminal import AgentState, get_terminal_tools
from rlm.core.types import CompletionOptions

if TYPE_CHECKING:
    from rlm.core.orchestrator import RLM

logger = structlog.get_logger()


class AgentRunner:
    """Autonomous agent that loops until task completion.

    Each iteration is a single `rlm.completion()` call. The agent
    can use any registered tools and terminates via FINAL/FINAL_VAR.
    """

    def __init__(self, rlm: RLM, config: AgentConfig | None = None):
        """Initialize the agent runner.

        Args:
            rlm: RLM instance for making completions
            config: Agent configuration (uses defaults if not provided)
        """
        self.rlm = rlm
        self.config = config or AgentConfig()
        self._run_id: str | None = None
        self._cancelled = False
        self._state: AgentState | None = None
        self._iteration = 0
        self._total_tokens = 0
        self._total_cost = 0.0

    async def run(self, task: str) -> AgentResult:
        """Run the agent on a task until completion or limit.

        Args:
            task: The task to solve

        Returns:
            AgentResult with the answer and execution details
        """
        self._run_id = str(uuid4())[:8]
        self._cancelled = False
        self._iteration = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        start_time = time.time()

        # Create terminal tools
        state = AgentState()
        self._state = state
        terminal_tools = get_terminal_tools(state, self.rlm.repl)

        # Register terminal tools
        for tool in terminal_tools:
            self.rlm.tool_registry.register(tool)

        previous_actions: list[str] = []
        all_events = []
        iteration_summaries = []

        try:
            # Auto-context on first iteration
            system_prompt = AGENT_SYSTEM_PROMPT
            if self.config.auto_context:
                snipara_tool = self.rlm.tool_registry.get("rlm_context_query")
                if snipara_tool:
                    try:
                        context = await snipara_tool.execute(
                            query=task, max_tokens=self.config.context_budget
                        )
                        system_prompt = (
                            f"{system_prompt}\n\nRelevant context for this task:\n{context}"
                        )
                    except Exception as e:
                        logger.warning("Auto-context failed", error=str(e))

            while self._iteration < self.config.max_iterations:
                # Check cancellation
                if self._cancelled:
                    return AgentResult(
                        answer="Agent was cancelled.",
                        answer_source="error",
                        iterations=self._iteration,
                        total_tokens=self._total_tokens,
                        total_cost=self._total_cost,
                        duration_ms=int((time.time() - start_time) * 1000),
                        forced_termination=True,
                        run_id=self._run_id,
                        trajectory=all_events,
                        iteration_summaries=iteration_summaries,
                    )

                # Check guardrails
                allowed, reason = check_iteration_allowed(
                    self._iteration,
                    self.config,
                    self._total_cost,
                    self._total_tokens,
                )
                if not allowed:
                    logger.info("Agent limit reached", reason=reason)
                    break

                # Build iteration prompt
                remaining = self.config.token_budget - self._total_tokens
                prompt = build_iteration_prompt(
                    task=task,
                    iteration=self._iteration,
                    max_iterations=self.config.max_iterations,
                    previous_actions=previous_actions,
                    remaining_budget=remaining,
                )

                # Build per-iteration options
                options = CompletionOptions(
                    max_depth=self.config.max_depth,
                    token_budget=min(
                        remaining, self.config.token_budget // self.config.max_iterations * 2
                    ),
                    tool_budget=self.config.tool_budget,
                    timeout_seconds=self.config.timeout_seconds,
                    include_trajectory=self.config.trajectory_log,
                )

                logger.debug(
                    "Agent iteration",
                    run_id=self._run_id,
                    iteration=self._iteration,
                    tokens_used=self._total_tokens,
                    cost=self._total_cost,
                )

                # Execute one completion
                try:
                    result = await asyncio.wait_for(
                        self.rlm.completion(prompt, system=system_prompt, options=options),
                        timeout=float(self.config.timeout_seconds),
                    )
                except asyncio.TimeoutError:
                    return AgentResult(
                        answer="Agent timed out.",
                        answer_source="error",
                        iterations=self._iteration,
                        total_tokens=self._total_tokens,
                        total_cost=self._total_cost,
                        duration_ms=int((time.time() - start_time) * 1000),
                        forced_termination=True,
                        run_id=self._run_id,
                        trajectory=all_events,
                        iteration_summaries=iteration_summaries,
                    )

                # Track totals
                self._total_tokens += result.total_tokens
                self._total_cost += result.total_cost_usd or 0
                all_events.extend(result.events)

                # Build iteration summary
                summary = {
                    "iteration": self._iteration,
                    "tokens": result.total_tokens,
                    "cost": result.total_cost_usd,
                    "tool_calls": result.total_tool_calls,
                    "response_preview": result.response[:200] if result.response else "",
                }
                iteration_summaries.append(summary)

                # Summarize actions for next iteration context
                action_summary = f"[Iter {self._iteration + 1}] "
                if result.total_tool_calls > 0:
                    tool_names = []
                    for evt in result.events:
                        for tc in evt.tool_calls:
                            tool_names.append(tc.name)
                    action_summary += f"Tools: {', '.join(tool_names[:5])}"
                    if result.response:
                        action_summary += f" → {result.response[:80]}"
                else:
                    action_summary += (
                        f"Response: {result.response[:100]}" if result.response else "No response"
                    )
                previous_actions.append(action_summary)

                self._iteration += 1

                # Check if agent terminated
                if state.is_terminal:
                    return AgentResult(
                        answer=state.terminal_value or "",
                        answer_source=state.terminal_type or "final",
                        iterations=self._iteration,
                        total_tokens=self._total_tokens,
                        total_cost=self._total_cost,
                        duration_ms=int((time.time() - start_time) * 1000),
                        forced_termination=False,
                        run_id=self._run_id,
                        trajectory=all_events,
                        iteration_summaries=iteration_summaries,
                    )

            # Iteration limit reached without FINAL
            logger.warning(
                "Agent forced termination",
                run_id=self._run_id,
                iterations=self._iteration,
            )
            return AgentResult(
                answer=previous_actions[-1] if previous_actions else "No answer produced.",
                answer_source="forced",
                iterations=self._iteration,
                total_tokens=self._total_tokens,
                total_cost=self._total_cost,
                duration_ms=int((time.time() - start_time) * 1000),
                forced_termination=True,
                run_id=self._run_id,
                trajectory=all_events,
                iteration_summaries=iteration_summaries,
            )

        finally:
            # Unregister terminal tools
            for tool in terminal_tools:
                self.rlm.tool_registry.unregister(tool.name)

    def cancel(self) -> None:
        """Cancel the running agent."""
        self._cancelled = True

    @property
    def status(self) -> dict:
        """Get current agent status."""
        return {
            "run_id": self._run_id,
            "iteration": self._iteration,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "is_terminal": self._state.is_terminal if self._state else False,
            "cancelled": self._cancelled,
        }
