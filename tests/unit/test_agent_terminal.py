"""Tests for agent terminal tools."""

import pytest

from rlm.agent.terminal import AgentState, get_terminal_tools


class TestAgentState:
    """Tests for AgentState."""

    def test_initial_state(self):
        state = AgentState()
        assert state.is_terminal is False
        assert state.terminal_value is None
        assert state.terminal_type is None


class TestTerminalTools:
    """Tests for FINAL and FINAL_VAR tools."""

    def _make_mock_repl(self, context=None):
        from unittest.mock import MagicMock

        repl = MagicMock()
        repl.get_context.return_value = context or {}
        return repl

    def test_creates_two_tools(self):
        state = AgentState()
        repl = self._make_mock_repl()
        tools = get_terminal_tools(state, repl)

        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "FINAL" in names
        assert "FINAL_VAR" in names

    @pytest.mark.asyncio
    async def test_final_sets_state(self):
        state = AgentState()
        repl = self._make_mock_repl()
        tools = get_terminal_tools(state, repl)
        final_tool = [t for t in tools if t.name == "FINAL"][0]

        result = await final_tool.execute(answer="The answer is 42")

        assert state.is_terminal is True
        assert state.terminal_value == "The answer is 42"
        assert state.terminal_type == "final"
        assert "42" in result

    @pytest.mark.asyncio
    async def test_final_var_reads_context(self):
        state = AgentState()
        repl = self._make_mock_repl(context={"result": 42, "data": [1, 2, 3]})
        tools = get_terminal_tools(state, repl)
        final_var_tool = [t for t in tools if t.name == "FINAL_VAR"][0]

        await final_var_tool.execute(variable_name="result")

        assert state.is_terminal is True
        assert state.terminal_value == "42"
        assert state.terminal_type == "final_var"

    @pytest.mark.asyncio
    async def test_final_var_missing_variable(self):
        state = AgentState()
        repl = self._make_mock_repl(context={"other": 1})
        tools = get_terminal_tools(state, repl)
        final_var_tool = [t for t in tools if t.name == "FINAL_VAR"][0]

        result = await final_var_tool.execute(variable_name="missing")

        assert state.is_terminal is False  # Should not terminate on error
        assert "not found" in result
