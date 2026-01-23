"""Model pricing data for cost estimation.

This module provides pricing data for various LLM models to estimate
the cost of API calls based on token usage.

Prices are in USD per 1,000 tokens as of January 2025.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """Pricing for a model (per 1K tokens in USD)."""

    input_price: float  # USD per 1K input tokens
    output_price: float  # USD per 1K output tokens

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for given token counts.

        Args:
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens

        Returns:
            Estimated cost in USD
        """
        return (input_tokens / 1000) * self.input_price + (output_tokens / 1000) * self.output_price


# Model pricing data (as of January 2025)
# Prices are per 1K tokens in USD
MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI models
    "gpt-4o": ModelPricing(input_price=0.0025, output_price=0.01),
    "gpt-4o-mini": ModelPricing(input_price=0.00015, output_price=0.0006),
    "gpt-4-turbo": ModelPricing(input_price=0.01, output_price=0.03),
    "gpt-4": ModelPricing(input_price=0.03, output_price=0.06),
    "gpt-3.5-turbo": ModelPricing(input_price=0.0005, output_price=0.0015),
    "o1": ModelPricing(input_price=0.015, output_price=0.06),
    "o1-mini": ModelPricing(input_price=0.003, output_price=0.012),
    # Anthropic models
    "claude-3-5-sonnet": ModelPricing(input_price=0.003, output_price=0.015),
    "claude-3-5-haiku": ModelPricing(input_price=0.0008, output_price=0.004),
    "claude-3-opus": ModelPricing(input_price=0.015, output_price=0.075),
    "claude-3-sonnet": ModelPricing(input_price=0.003, output_price=0.015),
    "claude-3-haiku": ModelPricing(input_price=0.00025, output_price=0.00125),
    # Google models
    "gemini-1.5-pro": ModelPricing(input_price=0.00125, output_price=0.005),
    "gemini-1.5-flash": ModelPricing(input_price=0.000075, output_price=0.0003),
    # Mistral models
    "mistral-large": ModelPricing(input_price=0.002, output_price=0.006),
    "mistral-small": ModelPricing(input_price=0.0002, output_price=0.0006),
    "mixtral-8x7b": ModelPricing(input_price=0.0007, output_price=0.0007),
}


def get_pricing(model: str) -> ModelPricing | None:
    """Get pricing for a model.

    Attempts exact match first, then prefix match for versioned model names.

    Args:
        model: Model name (e.g., "gpt-4o", "gpt-4o-2024-05-01")

    Returns:
        ModelPricing if found, None if unknown
    """
    # Try exact match first
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # Try prefix match for versioned models (e.g., "gpt-4o-2024-05-01" -> "gpt-4o")
    for prefix, pricing in MODEL_PRICING.items():
        if model.startswith(prefix):
            return pricing

    # Handle LiteLLM prefixes (e.g., "openai/gpt-4o" -> "gpt-4o")
    if "/" in model:
        model_name = model.split("/")[-1]
        return get_pricing(model_name)

    return None


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate cost for a completion.

    Args:
        model: Model name
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Estimated cost in USD, or None if pricing unknown

    Example:
        >>> cost = estimate_cost("gpt-4o-mini", 1000, 500)
        >>> print(f"${cost:.4f}")  # ~$0.0005
    """
    pricing = get_pricing(model)
    if pricing is None:
        return None
    return pricing.calculate_cost(input_tokens, output_tokens)


def format_cost(cost: float | None) -> str:
    """Format a cost value for display.

    Args:
        cost: Cost in USD, or None

    Returns:
        Formatted string (e.g., "$0.0025" or "unknown")
    """
    if cost is None:
        return "unknown"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"
