"""RLM Runtime - Recursive Language Model execution environment."""

from rlm.core.config import RLMConfig, load_config
from rlm.core.orchestrator import RLM
from rlm.core.types import (
    CompletionOptions,
    Message,
    REPLResult,
    RLMResult,
    ToolCall,
    ToolResult,
    TrajectoryEvent,
)
from rlm.tools.base import Tool
from rlm.tools.registry import ToolRegistry

__version__ = "0.1.0"

__all__ = [
    # Main class
    "RLM",
    # Types
    "CompletionOptions",
    "Message",
    "REPLResult",
    "RLMResult",
    "ToolCall",
    "ToolResult",
    "TrajectoryEvent",
    # Config
    "RLMConfig",
    "load_config",
    # Tools
    "Tool",
    "ToolRegistry",
]
