"""Tests for the pricing module."""

import pytest

from rlm.core.pricing import (
    ModelPricing,
    MODEL_PRICING,
    get_pricing,
    estimate_cost,
    format_cost,
)


class TestModelPricing:
    """Tests for ModelPricing dataclass."""

    def test_calculate_cost_simple(self):
        """Should calculate cost correctly."""
        pricing = ModelPricing(input_price=0.001, output_price=0.002)
        cost = pricing.calculate_cost(1000, 500)
        # 1000/1000 * 0.001 + 500/1000 * 0.002 = 0.001 + 0.001 = 0.002
        assert cost == pytest.approx(0.002)

    def test_calculate_cost_zero_tokens(self):
        """Should return 0 for zero tokens."""
        pricing = ModelPricing(input_price=0.001, output_price=0.002)
        cost = pricing.calculate_cost(0, 0)
        assert cost == 0.0

    def test_calculate_cost_only_input(self):
        """Should calculate cost with only input tokens."""
        pricing = ModelPricing(input_price=0.01, output_price=0.03)
        cost = pricing.calculate_cost(2000, 0)
        # 2000/1000 * 0.01 = 0.02
        assert cost == pytest.approx(0.02)

    def test_calculate_cost_only_output(self):
        """Should calculate cost with only output tokens."""
        pricing = ModelPricing(input_price=0.01, output_price=0.03)
        cost = pricing.calculate_cost(0, 2000)
        # 2000/1000 * 0.03 = 0.06
        assert cost == pytest.approx(0.06)


class TestModelPricingDict:
    """Tests for MODEL_PRICING dictionary."""

    def test_has_openai_models(self):
        """Should include OpenAI models."""
        assert "gpt-4o" in MODEL_PRICING
        assert "gpt-4o-mini" in MODEL_PRICING
        assert "gpt-4-turbo" in MODEL_PRICING
        assert "gpt-4" in MODEL_PRICING
        assert "gpt-3.5-turbo" in MODEL_PRICING

    def test_has_anthropic_models(self):
        """Should include Anthropic models."""
        assert "claude-3-5-sonnet" in MODEL_PRICING
        assert "claude-3-5-haiku" in MODEL_PRICING
        assert "claude-3-opus" in MODEL_PRICING
        assert "claude-3-sonnet" in MODEL_PRICING
        assert "claude-3-haiku" in MODEL_PRICING

    def test_has_google_models(self):
        """Should include Google models."""
        assert "gemini-1.5-pro" in MODEL_PRICING
        assert "gemini-1.5-flash" in MODEL_PRICING

    def test_has_mistral_models(self):
        """Should include Mistral models."""
        assert "mistral-large" in MODEL_PRICING
        assert "mistral-small" in MODEL_PRICING
        assert "mixtral-8x7b" in MODEL_PRICING

    def test_all_prices_are_positive(self):
        """All prices should be positive."""
        for model, pricing in MODEL_PRICING.items():
            assert pricing.input_price > 0, f"{model} input price should be positive"
            assert pricing.output_price > 0, f"{model} output price should be positive"


class TestGetPricing:
    """Tests for get_pricing function."""

    def test_exact_match(self):
        """Should return pricing for exact model name match."""
        pricing = get_pricing("gpt-4o")
        assert pricing is not None
        assert pricing.input_price == 0.0025
        assert pricing.output_price == 0.01

    def test_prefix_match(self):
        """Should return pricing for versioned model names."""
        # gpt-4o-2024-05-01 should match gpt-4o
        pricing = get_pricing("gpt-4o-2024-05-01")
        assert pricing is not None
        assert pricing.input_price == 0.0025

    def test_litellm_prefix(self):
        """Should handle LiteLLM prefixes (openai/gpt-4o)."""
        pricing = get_pricing("openai/gpt-4o")
        assert pricing is not None
        assert pricing.input_price == 0.0025

    def test_litellm_prefix_with_version(self):
        """Should handle LiteLLM prefixes with versions."""
        pricing = get_pricing("openai/gpt-4o-2024-05-01")
        assert pricing is not None
        assert pricing.input_price == 0.0025

    def test_unknown_model_returns_none(self):
        """Should return None for unknown models."""
        pricing = get_pricing("unknown-model-xyz")
        assert pricing is None

    def test_anthropic_model(self):
        """Should return correct pricing for Anthropic models."""
        pricing = get_pricing("claude-3-5-sonnet")
        assert pricing is not None
        assert pricing.input_price == 0.003
        assert pricing.output_price == 0.015


class TestEstimateCost:
    """Tests for estimate_cost function."""

    def test_known_model(self):
        """Should estimate cost for known models."""
        cost = estimate_cost("gpt-4o-mini", 1000, 500)
        # 1000/1000 * 0.00015 + 500/1000 * 0.0006 = 0.00015 + 0.0003 = 0.00045
        assert cost is not None
        assert cost == pytest.approx(0.00045)

    def test_unknown_model_returns_none(self):
        """Should return None for unknown models."""
        cost = estimate_cost("unknown-model", 1000, 500)
        assert cost is None

    def test_gpt4o_estimate(self):
        """Should estimate GPT-4o cost correctly."""
        cost = estimate_cost("gpt-4o", 10000, 2000)
        # 10000/1000 * 0.0025 + 2000/1000 * 0.01 = 0.025 + 0.02 = 0.045
        assert cost is not None
        assert cost == pytest.approx(0.045)

    def test_claude_estimate(self):
        """Should estimate Claude cost correctly."""
        cost = estimate_cost("claude-3-opus", 5000, 1000)
        # 5000/1000 * 0.015 + 1000/1000 * 0.075 = 0.075 + 0.075 = 0.15
        assert cost is not None
        assert cost == pytest.approx(0.15)


class TestFormatCost:
    """Tests for format_cost function."""

    def test_none_returns_unknown(self):
        """Should return 'unknown' for None."""
        assert format_cost(None) == "unknown"

    def test_small_cost_uses_4_decimals(self):
        """Should use 4 decimal places for costs under $0.01."""
        assert format_cost(0.0025) == "$0.0025"
        assert format_cost(0.00015) == "$0.0001"  # Truncates to 4 decimals

    def test_larger_cost_uses_2_decimals(self):
        """Should use 2 decimal places for costs >= $0.01."""
        assert format_cost(0.01) == "$0.01"
        assert format_cost(0.15) == "$0.15"
        assert format_cost(1.234) == "$1.23"

    def test_zero_cost(self):
        """Should format zero cost."""
        assert format_cost(0.0) == "$0.0000"


class TestRealWorldScenarios:
    """Tests for realistic cost estimation scenarios."""

    def test_simple_chat_cost(self):
        """Typical simple chat interaction cost."""
        # ~100 input tokens, ~50 output tokens with GPT-4o-mini
        cost = estimate_cost("gpt-4o-mini", 100, 50)
        assert cost is not None
        # Should be very cheap
        assert cost < 0.001

    def test_complex_task_cost(self):
        """Complex task with more tokens."""
        # ~8000 input tokens, ~4000 output tokens with GPT-4o
        cost = estimate_cost("gpt-4o", 8000, 4000)
        assert cost is not None
        # 8000/1000 * 0.0025 + 4000/1000 * 0.01 = 0.02 + 0.04 = 0.06
        assert cost == pytest.approx(0.06)

    def test_opus_expensive_task(self):
        """Claude Opus is expensive."""
        cost = estimate_cost("claude-3-opus", 10000, 5000)
        assert cost is not None
        # 10000/1000 * 0.015 + 5000/1000 * 0.075 = 0.15 + 0.375 = 0.525
        assert cost == pytest.approx(0.525)
