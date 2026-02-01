"""Tests for sub-LLM orchestration tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rlm.core.exceptions import SubCallBudgetExhausted, SubCallCostExceeded
from rlm.core.types import CompletionOptions, RLMResult
from rlm.tools.sub_llm import (
    SubCallLimits,
    SubLLMContext,
    _calculate_inherited_budget,
    get_sub_llm_tools,
)


class TestSubCallLimits:
    """Tests for SubCallLimits dataclass."""

    def test_default_values(self):
        limits = SubCallLimits()
        assert limits.enabled is True
        assert limits.max_per_turn == 5
        assert limits.budget_inheritance == 0.5
        assert limits.max_cost_per_session == 1.0

    def test_custom_values(self):
        limits = SubCallLimits(
            enabled=False,
            max_per_turn=10,
            budget_inheritance=0.3,
            max_cost_per_session=5.0,
        )
        assert limits.enabled is False
        assert limits.max_per_turn == 10
        assert limits.budget_inheritance == 0.3
        assert limits.max_cost_per_session == 5.0


class TestSubLLMContext:
    """Tests for SubLLMContext tracking."""

    def test_initial_state(self):
        ctx = SubLLMContext()
        assert ctx.calls_this_turn == 0
        assert ctx.session_cost == 0.0

    def test_record_call(self):
        ctx = SubLLMContext()
        ctx.record_call(0.05)
        assert ctx.calls_this_turn == 1
        assert ctx.session_cost == pytest.approx(0.05)

        ctx.record_call(0.03)
        assert ctx.calls_this_turn == 2
        assert ctx.session_cost == pytest.approx(0.08)

    def test_check_budget_passes(self):
        ctx = SubLLMContext(limits=SubCallLimits(max_per_turn=5))
        ctx.check_budget()  # Should not raise

    def test_check_budget_exceeds_per_turn(self):
        ctx = SubLLMContext(
            calls_this_turn=5,
            limits=SubCallLimits(max_per_turn=5),
        )
        with pytest.raises(SubCallBudgetExhausted) as exc_info:
            ctx.check_budget()
        assert exc_info.value.calls_made == 5
        assert exc_info.value.max_per_turn == 5

    def test_check_budget_exceeds_session_cost(self):
        ctx = SubLLMContext(
            session_cost=1.5,
            limits=SubCallLimits(max_cost_per_session=1.0),
        )
        with pytest.raises(SubCallCostExceeded) as exc_info:
            ctx.check_budget()
        assert exc_info.value.session_cost == pytest.approx(1.5)
        assert exc_info.value.max_cost == pytest.approx(1.0)


class TestBudgetInheritance:
    """Tests for budget inheritance calculation."""

    def test_auto_budget(self):
        result = _calculate_inherited_budget(None, 8000, 0.5)
        assert result == 4000

    def test_requested_within_limit(self):
        result = _calculate_inherited_budget(2000, 8000, 0.5)
        assert result == 2000

    def test_requested_exceeds_inherited(self):
        result = _calculate_inherited_budget(6000, 8000, 0.5)
        assert result == 4000  # clamped to 50% of 8000

    def test_custom_inheritance_fraction(self):
        result = _calculate_inherited_budget(None, 10000, 0.3)
        assert result == 3000


class TestGetSubLLMTools:
    """Tests for sub-LLM tool creation."""

    def _make_mock_rlm(self):
        rlm = MagicMock()
        rlm.tool_registry = MagicMock()
        rlm.tool_registry.get.return_value = None  # No snipara tools by default
        return rlm

    def _make_mock_result(self, response="test response", tokens=100, cost=0.01):
        return RLMResult(
            response=response,
            trajectory_id=uuid4(),
            total_calls=1,
            total_tokens=tokens,
            total_tool_calls=0,
            duration_ms=100,
            total_input_tokens=tokens // 2,
            total_output_tokens=tokens // 2,
            total_cost_usd=cost,
        )

    def test_returns_two_tools(self):
        rlm = self._make_mock_rlm()
        ctx = SubLLMContext()
        options = CompletionOptions(token_budget=8000)

        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=0)

        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "rlm_sub_complete" in names
        assert "rlm_batch_complete" in names

    @pytest.mark.asyncio
    async def test_sub_complete_calls_rlm(self):
        rlm = self._make_mock_rlm()
        mock_result = self._make_mock_result()
        rlm.completion = AsyncMock(return_value=mock_result)

        ctx = SubLLMContext()
        options = CompletionOptions(token_budget=8000)
        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=0)

        sub_complete = tools[0]
        result = await sub_complete.execute(query="What is 2+2?")

        rlm.completion.assert_awaited_once()
        assert result["response"] == "test response"
        assert result["tokens_used"] == 100
        assert result["cost"] == pytest.approx(0.01)
        assert ctx.calls_this_turn == 1

    @pytest.mark.asyncio
    async def test_sub_complete_constrained_budget(self):
        rlm = self._make_mock_rlm()
        mock_result = self._make_mock_result()
        rlm.completion = AsyncMock(return_value=mock_result)

        ctx = SubLLMContext(limits=SubCallLimits(budget_inheritance=0.5))
        options = CompletionOptions(token_budget=8000)
        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=2000)

        await tools[0].execute(query="test")

        # Verify the sub-call options have constrained budget
        call_args = rlm.completion.call_args
        sub_options = call_args.kwargs["options"]
        # Parent remaining: 8000 - 2000 = 6000, inherited: 6000 * 0.5 = 3000
        assert sub_options.token_budget == 3000

    @pytest.mark.asyncio
    async def test_sub_complete_respects_budget_limit(self):
        rlm = self._make_mock_rlm()
        ctx = SubLLMContext(
            calls_this_turn=5,
            limits=SubCallLimits(max_per_turn=5),
        )
        options = CompletionOptions(token_budget=8000)
        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=0)

        with pytest.raises(SubCallBudgetExhausted):
            await tools[0].execute(query="test")

    @pytest.mark.asyncio
    async def test_batch_complete_parallel(self):
        rlm = self._make_mock_rlm()
        mock_result = self._make_mock_result()
        rlm.completion = AsyncMock(return_value=mock_result)

        ctx = SubLLMContext()
        options = CompletionOptions(token_budget=8000)
        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=0)

        batch_tool = tools[1]
        result = await batch_tool.execute(
            queries=[
                {"query": "Task 1"},
                {"query": "Task 2"},
                {"query": "Task 3"},
            ],
            max_parallel=2,
        )

        assert len(result["results"]) == 3
        assert rlm.completion.call_count == 3
        assert ctx.calls_this_turn == 3

    @pytest.mark.asyncio
    async def test_batch_complete_empty(self):
        rlm = self._make_mock_rlm()
        ctx = SubLLMContext()
        options = CompletionOptions(token_budget=8000)
        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=0)

        result = await tools[1].execute(queries=[])
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_sub_complete_with_snipara_context(self):
        rlm = self._make_mock_rlm()
        mock_result = self._make_mock_result()
        rlm.completion = AsyncMock(return_value=mock_result)

        # Mock Snipara tool
        snipara_tool = MagicMock()
        snipara_tool.execute = AsyncMock(return_value="Relevant documentation here")
        rlm.tool_registry.get.side_effect = lambda name: (
            snipara_tool if name == "rlm_context_query" else None
        )

        ctx = SubLLMContext()
        options = CompletionOptions(token_budget=8000)
        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=0)

        await tools[0].execute(query="test", context_query="search docs")

        # Verify Snipara was called
        snipara_tool.execute.assert_awaited_once()
        # Verify system prompt includes context
        call_args = rlm.completion.call_args
        assert "Relevant documentation here" in call_args.kwargs["system"]

    @pytest.mark.asyncio
    async def test_sub_complete_explicit_max_tokens(self):
        rlm = self._make_mock_rlm()
        mock_result = self._make_mock_result()
        rlm.completion = AsyncMock(return_value=mock_result)

        ctx = SubLLMContext(limits=SubCallLimits(budget_inheritance=0.5))
        options = CompletionOptions(token_budget=8000)
        tools = get_sub_llm_tools(rlm, ctx, options, parent_tokens_used=0)

        await tools[0].execute(query="test", max_tokens=1000)

        call_args = rlm.completion.call_args
        sub_options = call_args.kwargs["options"]
        # Requested 1000, inherited max is 4000 -> use 1000
        assert sub_options.token_budget == 1000
