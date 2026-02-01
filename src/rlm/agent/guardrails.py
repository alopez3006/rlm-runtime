"""Agent guardrails for safety limit checking."""

from __future__ import annotations

from rlm.agent.config import AgentConfig


def check_iteration_allowed(
    iteration: int,
    config: AgentConfig,
    total_cost: float,
    total_tokens: int,
) -> tuple[bool, str | None]:
    """Check if another agent iteration is allowed.

    Args:
        iteration: Current iteration number (0-based)
        config: Agent configuration with limits
        total_cost: Total cost accumulated so far
        total_tokens: Total tokens used so far

    Returns:
        Tuple of (allowed, reason). If not allowed, reason explains why.
    """
    if iteration >= config.max_iterations:
        return False, f"Iteration limit reached ({iteration}/{config.max_iterations})"

    if total_cost >= config.cost_limit:
        return False, f"Cost limit reached (${total_cost:.4f}/${config.cost_limit:.4f})"

    if total_tokens >= config.token_budget:
        return False, f"Token budget exhausted ({total_tokens}/{config.token_budget})"

    return True, None
