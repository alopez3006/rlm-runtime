"""Agent configuration with hard safety limits."""

from __future__ import annotations

from dataclasses import dataclass

# Hard safety limits (non-configurable)
ABSOLUTE_MAX_ITERATIONS = 50
ABSOLUTE_MAX_COST = 10.0
ABSOLUTE_MAX_TIMEOUT = 600
ABSOLUTE_MAX_DEPTH = 5


@dataclass
class AgentConfig:
    """Configuration for an autonomous agent run.

    All values are clamped to absolute safety limits in __post_init__.
    """

    max_iterations: int = 10
    max_depth: int = 3
    token_budget: int = 50000
    cost_limit: float = 2.0
    timeout_seconds: int = 120
    auto_context: bool = True  # Auto-load Snipara context on first iteration
    context_budget: int = 8000
    trajectory_log: bool = True
    tool_budget: int = 50  # Tool calls across all iterations

    def __post_init__(self) -> None:
        """Clamp values to hard safety limits."""
        self.max_iterations = min(self.max_iterations, ABSOLUTE_MAX_ITERATIONS)
        self.max_depth = min(self.max_depth, ABSOLUTE_MAX_DEPTH)
        self.cost_limit = min(self.cost_limit, ABSOLUTE_MAX_COST)
        self.timeout_seconds = min(self.timeout_seconds, ABSOLUTE_MAX_TIMEOUT)
