"""Sub-LLM orchestration tools.

Enables the model to delegate focused sub-problems to fresh LLM calls
with their own context window and budget.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from rlm.backends.base import Tool
from rlm.core.exceptions import SubCallBudgetExhausted, SubCallCostExceeded
from rlm.core.types import CompletionOptions

if TYPE_CHECKING:
    from rlm.core.orchestrator import RLM

logger = structlog.get_logger()


@dataclass
class SubCallLimits:
    """Limits for sub-LLM calls."""

    enabled: bool = True
    max_per_turn: int = 5
    budget_inheritance: float = 0.5  # Fraction of parent's remaining budget
    max_cost_per_session: float = 1.0  # Dollar cap for all sub-calls in a session


@dataclass
class SubLLMContext:
    """Tracks sub-call state for a single completion session."""

    calls_this_turn: int = 0
    session_cost: float = 0.0
    limits: SubCallLimits = field(default_factory=SubCallLimits)

    def check_budget(self) -> None:
        """Check if sub-call budgets allow another call."""
        if self.calls_this_turn >= self.limits.max_per_turn:
            raise SubCallBudgetExhausted(
                calls_made=self.calls_this_turn,
                max_per_turn=self.limits.max_per_turn,
            )
        if self.session_cost >= self.limits.max_cost_per_session:
            raise SubCallCostExceeded(
                session_cost=self.session_cost,
                max_cost=self.limits.max_cost_per_session,
            )

    def record_call(self, cost: float) -> None:
        """Record a completed sub-call."""
        self.calls_this_turn += 1
        self.session_cost += cost


def _calculate_inherited_budget(
    requested: int | None,
    parent_remaining: int,
    inheritance_fraction: float,
) -> int:
    """Calculate the token budget for a sub-call.

    Args:
        requested: Explicitly requested budget (or None for auto)
        parent_remaining: Parent's remaining token budget
        inheritance_fraction: Fraction of parent budget to inherit

    Returns:
        Token budget for the sub-call
    """
    inherited = int(parent_remaining * inheritance_fraction)
    if requested is not None:
        return min(requested, inherited)
    return inherited


def get_sub_llm_tools(
    rlm: RLM,
    context: SubLLMContext,
    parent_options: CompletionOptions,
    parent_tokens_used: int,
) -> list[Tool]:
    """Create sub-LLM tools bound to the current completion context.

    Args:
        rlm: The RLM instance to use for sub-calls
        context: Sub-call tracking context
        parent_options: The parent completion's options
        parent_tokens_used: Tokens already used by the parent

    Returns:
        List of Tool instances for rlm_sub_complete and rlm_batch_complete
    """

    async def rlm_sub_complete(
        query: str,
        max_tokens: int | None = None,
        system: str | None = None,
        context_query: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a sub-LLM call with its own context and budget.

        Args:
            query: The sub-problem to solve
            max_tokens: Optional token budget (auto-calculated if not set)
            system: Optional system prompt for the sub-call
            context_query: Optional Snipara query to auto-inject context
        """
        context.check_budget()

        # Calculate inherited budget
        parent_remaining = parent_options.token_budget - parent_tokens_used
        sub_budget = _calculate_inherited_budget(
            max_tokens, parent_remaining, context.limits.budget_inheritance
        )

        # Auto-inject Snipara context if requested
        if context_query and system is None:
            system = ""
        if context_query:
            snipara_tool = rlm.tool_registry.get("rlm_context_query")
            if snipara_tool:
                try:
                    ctx_result = await snipara_tool.execute(
                        query=context_query, max_tokens=min(sub_budget // 2, 4000)
                    )
                    system = (
                        f"{system}\n\nRelevant context:\n{ctx_result}"
                        if system
                        else f"Relevant context:\n{ctx_result}"
                    )
                except Exception as e:
                    logger.warning("Snipara context query failed", error=str(e))

        # Build constrained options for sub-call
        sub_options = CompletionOptions(
            max_depth=min(2, parent_options.max_depth - 1),
            max_subcalls=min(4, parent_options.max_subcalls),
            token_budget=sub_budget,
            tool_budget=min(10, parent_options.tool_budget),
            timeout_seconds=min(60, parent_options.timeout_seconds),
            cost_budget_usd=context.limits.max_cost_per_session - context.session_cost
            if parent_options.cost_budget_usd
            else None,
        )

        logger.debug(
            "Starting sub-LLM call",
            query_length=len(query),
            sub_budget=sub_budget,
            calls_this_turn=context.calls_this_turn,
        )

        result = await rlm.completion(query, system=system, options=sub_options)

        # Record the call
        context.record_call(result.total_cost_usd or 0)

        return {
            "response": result.response,
            "tokens_used": result.total_tokens,
            "cost": result.total_cost_usd,
            "calls": result.total_calls,
        }

    async def rlm_batch_complete(
        queries: list[dict[str, str]],
        max_parallel: int = 3,
        total_budget: int | None = None,
    ) -> dict[str, Any]:
        """Execute multiple sub-LLM calls in parallel with shared budget.

        Args:
            queries: List of {"query": str, "system"?: str} objects
            max_parallel: Maximum concurrent sub-calls
            total_budget: Total token budget split across all queries
        """
        if not queries:
            return {"results": []}

        # Calculate per-query budget
        parent_remaining = parent_options.token_budget - parent_tokens_used
        if total_budget is None:
            total_budget = _calculate_inherited_budget(
                None, parent_remaining, context.limits.budget_inheritance
            )
        per_query_budget = total_budget // len(queries)

        semaphore = asyncio.Semaphore(max_parallel)
        results: list[dict[str, Any]] = []

        async def _run_one(q: dict[str, str]) -> dict[str, Any]:
            async with semaphore:
                context.check_budget()
                sub_options = CompletionOptions(
                    max_depth=min(2, parent_options.max_depth - 1),
                    max_subcalls=min(4, parent_options.max_subcalls),
                    token_budget=per_query_budget,
                    tool_budget=min(10, parent_options.tool_budget),
                    timeout_seconds=min(60, parent_options.timeout_seconds),
                )
                try:
                    result = await rlm.completion(
                        q["query"],
                        system=q.get("system"),
                        options=sub_options,
                    )
                    context.record_call(result.total_cost_usd or 0)
                    return {
                        "query": q["query"],
                        "response": result.response,
                        "tokens_used": result.total_tokens,
                        "cost": result.total_cost_usd,
                    }
                except Exception as e:
                    return {
                        "query": q["query"],
                        "response": None,
                        "error": str(e),
                        "tokens_used": 0,
                        "cost": 0,
                    }

        batch_results = await asyncio.gather(
            *[_run_one(q) for q in queries],
            return_exceptions=True,
        )

        for r in batch_results:
            if isinstance(r, Exception):
                results.append({"error": str(r), "tokens_used": 0, "cost": 0})
            else:
                results.append(r)

        return {"results": results}

    tools = [
        Tool(
            name="rlm_sub_complete",
            description=(
                "Delegate a focused sub-problem to a fresh LLM call with its own "
                "context window and budget. Use this when the current task can be "
                "broken into independent sub-tasks."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The sub-problem to solve",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Optional token budget for the sub-call",
                    },
                    "system": {
                        "type": "string",
                        "description": "Optional system prompt for the sub-call",
                    },
                    "context_query": {
                        "type": "string",
                        "description": "Optional Snipara query to auto-inject relevant documentation",
                    },
                },
                "required": ["query"],
            },
            handler=rlm_sub_complete,
        ),
        Tool(
            name="rlm_batch_complete",
            description=(
                "Execute multiple sub-LLM calls in parallel. Each query gets an "
                "equal share of the total budget. Use for independent sub-tasks "
                "that can run concurrently."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "system": {"type": "string"},
                            },
                            "required": ["query"],
                        },
                        "description": "List of sub-problems to solve in parallel",
                    },
                    "max_parallel": {
                        "type": "integer",
                        "description": "Maximum concurrent sub-calls (default: 3)",
                    },
                    "total_budget": {
                        "type": "integer",
                        "description": "Total token budget split across all queries",
                    },
                },
                "required": ["queries"],
            },
            handler=rlm_batch_complete,
        ),
    ]

    return tools
