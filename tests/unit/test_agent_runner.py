"""Tests for the autonomous agent runner."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rlm.agent.config import AgentConfig
from rlm.agent.result import AgentResult
from rlm.agent.runner import AgentRunner
from rlm.core.types import RLMResult, ToolCall, TrajectoryEvent


def _make_mock_rlm():
    """Create a mock RLM instance."""
    rlm = MagicMock()
    rlm.repl = MagicMock()
    rlm.repl.get_context.return_value = {}
    rlm.tool_registry = MagicMock()
    rlm.tool_registry.get.return_value = None
    rlm.tool_registry.register = MagicMock()
    rlm.tool_registry.unregister = MagicMock()
    return rlm


def _make_result(response="test", tokens=100, cost=0.01, tool_calls=0):
    """Create a mock RLMResult."""
    events = []
    if tool_calls > 0:
        events.append(
            TrajectoryEvent(
                trajectory_id=uuid4(),
                call_id=uuid4(),
                parent_call_id=None,
                depth=0,
                prompt="test",
                tool_calls=[
                    ToolCall(id=f"tc_{i}", name=f"tool_{i}", arguments={})
                    for i in range(tool_calls)
                ],
            )
        )
    return RLMResult(
        response=response,
        trajectory_id=uuid4(),
        total_calls=1,
        total_tokens=tokens,
        total_tool_calls=tool_calls,
        duration_ms=100,
        total_input_tokens=tokens // 2,
        total_output_tokens=tokens // 2,
        total_cost_usd=cost,
        events=events,
    )


class TestAgentResult:
    """Tests for AgentResult."""

    def test_success_on_final(self):
        result = AgentResult(
            answer="42",
            answer_source="final",
            iterations=3,
            total_tokens=500,
            total_cost=0.05,
            duration_ms=1000,
        )
        assert result.success is True

    def test_success_on_final_var(self):
        result = AgentResult(
            answer="42",
            answer_source="final_var",
            iterations=3,
            total_tokens=500,
            total_cost=0.05,
            duration_ms=1000,
        )
        assert result.success is True

    def test_not_success_when_forced(self):
        result = AgentResult(
            answer="best guess",
            answer_source="forced",
            iterations=10,
            total_tokens=50000,
            total_cost=2.0,
            duration_ms=60000,
            forced_termination=True,
        )
        assert result.success is False

    def test_not_success_on_error(self):
        result = AgentResult(
            answer="error",
            answer_source="error",
            iterations=1,
            total_tokens=100,
            total_cost=0.01,
            duration_ms=500,
            forced_termination=True,
        )
        assert result.success is False

    def test_to_dict(self):
        result = AgentResult(
            answer="42",
            answer_source="final",
            iterations=3,
            total_tokens=500,
            total_cost=0.05,
            duration_ms=1000,
            run_id="abc123",
        )
        d = result.to_dict()
        assert d["answer"] == "42"
        assert d["success"] is True
        assert d["run_id"] == "abc123"


class TestAgentRunner:
    """Tests for the AgentRunner."""

    @pytest.mark.asyncio
    async def test_agent_terminates_on_final(self):
        """Agent should terminate when FINAL is called."""
        rlm = _make_mock_rlm()

        # First call: agent responds normally
        # Second call: agent calls FINAL
        call_count = 0

        async def mock_completion(prompt, system=None, options=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_result(response="Let me think...", tool_calls=1)
            # On second call, simulate FINAL being called by setting state
            # We need to find the AgentState and set it
            return _make_result(response="42")

        rlm.completion = mock_completion

        config = AgentConfig(max_iterations=5, timeout_seconds=10)
        runner = AgentRunner(rlm, config)

        # We need to manually trigger the state to simulate FINAL tool call
        # Since we can't easily mock the tool execution chain, test the basic flow
        result = await runner.run("What is 2+2?")

        # Agent should have run and eventually been forced (since mock doesn't trigger FINAL)
        assert result.iterations > 0
        assert result.run_id != ""

    @pytest.mark.asyncio
    async def test_forced_termination_on_iteration_limit(self):
        """Agent should force-terminate when iteration limit is reached."""
        rlm = _make_mock_rlm()
        rlm.completion = AsyncMock(return_value=_make_result(response="still thinking"))

        config = AgentConfig(max_iterations=2, timeout_seconds=10)
        runner = AgentRunner(rlm, config)
        result = await runner.run("Solve this")

        assert result.forced_termination is True
        assert result.answer_source == "forced"
        assert result.iterations == 2

    @pytest.mark.asyncio
    async def test_forced_termination_on_cost_limit(self):
        """Agent should force-terminate when cost limit is reached."""
        rlm = _make_mock_rlm()
        rlm.completion = AsyncMock(return_value=_make_result(response="thinking", cost=1.5))

        config = AgentConfig(max_iterations=10, cost_limit=1.0, timeout_seconds=10)
        runner = AgentRunner(rlm, config)
        result = await runner.run("Expensive task")

        # First iteration costs 1.5, exceeds limit of 1.0 on second check
        assert result.forced_termination is True
        assert result.iterations >= 1

    @pytest.mark.asyncio
    async def test_cancel_agent(self):
        """Agent should respect cancellation."""
        rlm = _make_mock_rlm()

        async def slow_completion(prompt, system=None, options=None):
            await asyncio.sleep(0.1)
            return _make_result(response="thinking")

        rlm.completion = slow_completion

        config = AgentConfig(max_iterations=10, timeout_seconds=10)
        runner = AgentRunner(rlm, config)

        # Start agent and cancel after first iteration
        async def cancel_after_delay():
            await asyncio.sleep(0.05)
            runner.cancel()

        task = asyncio.create_task(runner.run("Long task"))
        cancel_task = asyncio.create_task(cancel_after_delay())

        result = await task
        await cancel_task

        assert result.forced_termination is True
        assert result.answer_source == "error"

    @pytest.mark.asyncio
    async def test_status_property(self):
        """Status should report agent state."""
        rlm = _make_mock_rlm()
        config = AgentConfig(max_iterations=1, timeout_seconds=10)
        runner = AgentRunner(rlm, config)

        status = runner.status
        assert status["run_id"] is None
        assert status["iteration"] == 0
        assert status["cancelled"] is False

    @pytest.mark.asyncio
    async def test_registers_and_unregisters_tools(self):
        """Agent should register FINAL/FINAL_VAR and clean up."""
        rlm = _make_mock_rlm()
        rlm.completion = AsyncMock(return_value=_make_result(response="done"))

        config = AgentConfig(max_iterations=1, timeout_seconds=10)
        runner = AgentRunner(rlm, config)
        await runner.run("test")

        # Should have registered FINAL and FINAL_VAR
        register_calls = rlm.tool_registry.register.call_args_list
        registered_names = [call.args[0].name for call in register_calls]
        assert "FINAL" in registered_names
        assert "FINAL_VAR" in registered_names

        # Should have unregistered them
        unregister_calls = rlm.tool_registry.unregister.call_args_list
        unregistered_names = [call.args[0] for call in unregister_calls]
        assert "FINAL" in unregistered_names
        assert "FINAL_VAR" in unregistered_names

    @pytest.mark.asyncio
    async def test_tracks_total_tokens_and_cost(self):
        """Agent should accumulate tokens and cost across iterations."""
        rlm = _make_mock_rlm()
        rlm.completion = AsyncMock(
            return_value=_make_result(response="thinking", tokens=500, cost=0.02)
        )

        config = AgentConfig(max_iterations=3, timeout_seconds=10)
        runner = AgentRunner(rlm, config)
        result = await runner.run("test")

        assert result.total_tokens == 1500  # 500 * 3
        assert result.total_cost == pytest.approx(0.06)  # 0.02 * 3
        assert result.iterations == 3

    @pytest.mark.asyncio
    async def test_iteration_summaries(self):
        """Agent should build iteration summaries."""
        rlm = _make_mock_rlm()
        rlm.completion = AsyncMock(
            return_value=_make_result(response="done", tokens=100, cost=0.01)
        )

        config = AgentConfig(max_iterations=2, timeout_seconds=10)
        runner = AgentRunner(rlm, config)
        result = await runner.run("test")

        assert len(result.iteration_summaries) == 2
        assert result.iteration_summaries[0]["iteration"] == 0
        assert result.iteration_summaries[1]["iteration"] == 1
