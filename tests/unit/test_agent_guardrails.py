"""Tests for agent guardrails."""

from rlm.agent.config import AgentConfig
from rlm.agent.guardrails import check_iteration_allowed


class TestCheckIterationAllowed:
    """Tests for check_iteration_allowed."""

    def test_allowed_at_start(self):
        config = AgentConfig(max_iterations=10, cost_limit=2.0, token_budget=50000)
        allowed, reason = check_iteration_allowed(0, config, 0.0, 0)
        assert allowed is True
        assert reason is None

    def test_blocked_at_iteration_limit(self):
        config = AgentConfig(max_iterations=5)
        allowed, reason = check_iteration_allowed(5, config, 0.0, 0)
        assert allowed is False
        assert "Iteration limit" in reason

    def test_blocked_at_cost_limit(self):
        config = AgentConfig(cost_limit=1.0)
        allowed, reason = check_iteration_allowed(0, config, 1.5, 0)
        assert allowed is False
        assert "Cost limit" in reason

    def test_blocked_at_token_limit(self):
        config = AgentConfig(token_budget=10000)
        allowed, reason = check_iteration_allowed(0, config, 0.0, 15000)
        assert allowed is False
        assert "Token budget" in reason

    def test_allowed_just_under_limits(self):
        config = AgentConfig(max_iterations=10, cost_limit=2.0, token_budget=50000)
        allowed, reason = check_iteration_allowed(9, config, 1.99, 49999)
        assert allowed is True
        assert reason is None
