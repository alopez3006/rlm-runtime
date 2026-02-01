"""Tests for agent configuration."""

from rlm.agent.config import (
    ABSOLUTE_MAX_COST,
    ABSOLUTE_MAX_DEPTH,
    ABSOLUTE_MAX_ITERATIONS,
    ABSOLUTE_MAX_TIMEOUT,
    AgentConfig,
)


class TestAgentConfig:
    """Tests for AgentConfig defaults and clamping."""

    def test_defaults(self):
        config = AgentConfig()
        assert config.max_iterations == 10
        assert config.max_depth == 3
        assert config.token_budget == 50000
        assert config.cost_limit == 2.0
        assert config.timeout_seconds == 120
        assert config.auto_context is True
        assert config.context_budget == 8000
        assert config.trajectory_log is True

    def test_clamp_max_iterations(self):
        config = AgentConfig(max_iterations=100)
        assert config.max_iterations == ABSOLUTE_MAX_ITERATIONS  # 50

    def test_clamp_max_depth(self):
        config = AgentConfig(max_depth=20)
        assert config.max_depth == ABSOLUTE_MAX_DEPTH  # 5

    def test_clamp_cost_limit(self):
        config = AgentConfig(cost_limit=50.0)
        assert config.cost_limit == ABSOLUTE_MAX_COST  # 10.0

    def test_clamp_timeout(self):
        config = AgentConfig(timeout_seconds=3600)
        assert config.timeout_seconds == ABSOLUTE_MAX_TIMEOUT  # 600

    def test_values_within_limits_not_clamped(self):
        config = AgentConfig(
            max_iterations=5,
            max_depth=2,
            cost_limit=1.0,
            timeout_seconds=60,
        )
        assert config.max_iterations == 5
        assert config.max_depth == 2
        assert config.cost_limit == 1.0
        assert config.timeout_seconds == 60

    def test_hard_limits(self):
        assert ABSOLUTE_MAX_ITERATIONS == 50
        assert ABSOLUTE_MAX_COST == 10.0
        assert ABSOLUTE_MAX_TIMEOUT == 600
        assert ABSOLUTE_MAX_DEPTH == 5
