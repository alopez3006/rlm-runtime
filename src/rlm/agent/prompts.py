"""Agent prompt templates."""

from __future__ import annotations

AGENT_SYSTEM_PROMPT = """\
You are an autonomous agent that solves tasks by observing, thinking, and acting.

Available actions:
- **execute_python**: Run Python code in a sandboxed REPL to compute, analyze, or process data
- **get_repl_context / set_repl_context**: Read/write persistent variables across code executions
- **rlm_context_query**: Search documentation for relevant context (Snipara)
- **rlm_search**: Regex search across documentation
- **rlm_remember / rlm_recall**: Store and recall information across sessions
- **rlm_sub_complete**: Delegate a sub-problem to a fresh LLM call
- **rlm_batch_complete**: Run multiple sub-problems in parallel
- **FINAL(answer)**: Terminate and return your answer as text
- **FINAL_VAR(variable_name)**: Terminate and return the value of a REPL variable

Strategy:
1. Break the problem into steps
2. Use tools to gather information and compute results
3. Store intermediate results in REPL variables
4. Call FINAL or FINAL_VAR when you have the answer

Important:
- Always call FINAL or FINAL_VAR when done - do not just output text
- If you're running low on iterations, call FINAL with your best answer
- Be efficient with tool calls - plan before acting
"""


def build_iteration_prompt(
    task: str,
    iteration: int,
    max_iterations: int,
    previous_actions: list[str],
    remaining_budget: int | None = None,
) -> str:
    """Build the prompt for a single agent iteration.

    Args:
        task: The original task
        iteration: Current iteration number (0-based)
        max_iterations: Maximum iterations allowed
        previous_actions: Summary of actions from previous iterations
        remaining_budget: Remaining token budget (if known)

    Returns:
        Formatted prompt string
    """
    parts = [f"Task: {task}"]

    parts.append(f"\nIteration: {iteration + 1}/{max_iterations}")

    if remaining_budget is not None:
        parts.append(f"Remaining token budget: {remaining_budget}")

    if previous_actions:
        parts.append("\nPrevious actions:")
        for i, action in enumerate(previous_actions[-5:], 1):  # Last 5 actions
            parts.append(f"  {i}. {action}")

    # Warning on final iteration
    if iteration >= max_iterations - 1:
        parts.append(
            "\n⚠️ THIS IS YOUR FINAL ITERATION. You MUST call FINAL or FINAL_VAR now "
            "with your best answer."
        )

    return "\n".join(parts)
