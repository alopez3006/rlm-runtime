"""Agent result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rlm.core.types import TrajectoryEvent


@dataclass
class AgentResult:
    """Result from an autonomous agent run."""

    answer: str
    answer_source: str  # "final", "final_var", "forced", "error"
    iterations: int
    total_tokens: int
    total_cost: float | None
    duration_ms: int
    forced_termination: bool = False
    run_id: str = ""
    trajectory: list[TrajectoryEvent] = field(default_factory=list)
    iteration_summaries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True when agent terminated naturally via FINAL/FINAL_VAR."""
        return not self.forced_termination and self.answer_source in ("final", "final_var")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "answer": self.answer,
            "answer_source": self.answer_source,
            "iterations": self.iterations,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "duration_ms": self.duration_ms,
            "forced_termination": self.forced_termination,
            "run_id": self.run_id,
            "success": self.success,
            "iteration_summaries": self.iteration_summaries,
        }
