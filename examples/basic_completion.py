#!/usr/bin/env python3
"""
Basic RLM Runtime Example

This example demonstrates the simplest usage of RLM Runtime
for recursive language model completion.
"""

import asyncio

from rlm import RLM


async def main():
    """Run a basic completion."""
    # Create RLM instance with default settings
    rlm = RLM(
        model="gpt-4o-mini",
        # Other options:
        # environment="local",  # local, docker, or wasm
        # max_depth=4,
        # token_budget=8000,
    )

    # Simple completion
    print("=== Basic Completion ===")
    result = await rlm.completion("What is 2 + 2?")
    print(f"Response: {result.response}")
    print(f"Calls: {result.total_calls}, Tokens: {result.total_tokens}")
    print()

    # Completion with system prompt
    print("=== With System Prompt ===")
    result = await rlm.completion(
        prompt="Solve this math problem: 15 * 7",
        system="You are a math tutor. Show your work step by step.",
    )
    print(f"Response: {result.response}")
    print()

    # Streaming completion
    print("=== Streaming ===")
    print("Streaming response: ", end="", flush=True)
    async for chunk in rlm.stream("Write a haiku about code"):
        print(chunk, end="", flush=True)
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
