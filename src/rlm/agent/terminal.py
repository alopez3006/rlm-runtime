"""Terminal tools for agent termination protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rlm.backends.base import Tool

if TYPE_CHECKING:
    from rlm.repl.base import BaseREPL


@dataclass
class AgentState:
    """Mutable state tracking agent termination."""

    is_terminal: bool = False
    terminal_value: str | None = None
    terminal_type: str | None = None  # "final" or "final_var"


def get_terminal_tools(state: AgentState, repl: BaseREPL) -> list[Tool]:
    """Create FINAL and FINAL_VAR termination tools.

    Args:
        state: Mutable agent state for tracking termination
        repl: REPL instance for reading variables (FINAL_VAR)

    Returns:
        List of Tool instances
    """

    async def final_handler(answer: str) -> str:
        """Terminate the agent with a natural language answer."""
        state.is_terminal = True
        state.terminal_value = answer
        state.terminal_type = "final"
        return f"Agent terminated with answer: {answer[:100]}"

    async def final_var_handler(variable_name: str) -> str:
        """Terminate the agent, returning the value of a REPL variable."""
        context = repl.get_context()
        if variable_name not in context:
            return f"Error: Variable '{variable_name}' not found in REPL context. Available: {list(context.keys())}"

        value = context[variable_name]
        state.is_terminal = True
        state.terminal_value = str(value)
        state.terminal_type = "final_var"
        return f"Agent terminated with variable '{variable_name}' = {str(value)[:100]}"

    return [
        Tool(
            name="FINAL",
            description=(
                "Terminate the agent and return your answer. Call this when you have "
                "fully solved the task and are ready to report the result."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "The final answer to the task",
                    },
                },
                "required": ["answer"],
            },
            handler=final_handler,
        ),
        Tool(
            name="FINAL_VAR",
            description=(
                "Terminate the agent and return the value of a REPL variable. "
                "Use this when the answer is stored in a computed variable."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "variable_name": {
                        "type": "string",
                        "description": "Name of the REPL variable to return",
                    },
                },
                "required": ["variable_name"],
            },
            handler=final_var_handler,
        ),
    ]
