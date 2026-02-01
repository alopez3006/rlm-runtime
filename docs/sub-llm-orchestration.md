# Sub-LLM Orchestration (Phase 8) ✅

## Status: Implemented

Sub-LLM Orchestration enables rlm-runtime to make **recursive LLM calls within a single completion**, allowing the model to spawn focused sub-queries that each get their own context window, depth budget, and token limit.

The key insight from Alex Zhang's RLM paper: a model working on a complex task should be able to delegate sub-problems to fresh LLM calls with targeted context, rather than trying to hold everything in a single conversation.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  User Query                                                     │
│  "Explain how auth and billing interact in this codebase"       │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  Primary LLM Call (depth=0)                                     │
│                                                                  │
│  Model decides: "I need to understand auth and billing          │
│  separately, then synthesize."                                   │
│                                                                  │
│  Calls: rlm_sub_complete("How does authentication work?")       │
│  Calls: rlm_sub_complete("How does billing work?")              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Sub-LLM Call (depth=1) - Auth                            │   │
│  │ • Gets its own Snipara context (auth-focused)            │   │
│  │ • Has own tool access (context_query, execute_python)    │   │
│  │ • Returns focused answer about auth                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Sub-LLM Call (depth=1) - Billing                         │   │
│  │ • Gets its own Snipara context (billing-focused)         │   │
│  │ • Has own tool access                                    │   │
│  │ • Returns focused answer about billing                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Primary model synthesizes both sub-results into final answer   │
└────────────────────────────────────────────────────────────────┘
```

## Implementation

### Source Files

| File | Description |
|------|-------------|
| `src/rlm/tools/sub_llm.py` | Core implementation: `SubCallLimits`, `SubLLMContext`, `get_sub_llm_tools()` |
| `src/rlm/core/orchestrator.py` | `extra_tools` pattern, sub-LLM tool integration |
| `src/rlm/core/config.py` | Configuration fields for sub-call limits |
| `src/rlm/core/types.py` | `sub_call_type` field on `TrajectoryEvent` |
| `src/rlm/core/exceptions.py` | `SubCallBudgetExhausted`, `SubCallDepthExceeded`, `SubCallCostExceeded` |
| `tests/unit/test_sub_llm.py` | 19 comprehensive tests |

### Tools

#### `rlm_sub_complete`

Spawn a sub-LLM call with its own context window and budget.

```python
# Tool schema
{
    "name": "rlm_sub_complete",
    "parameters": {
        "query": "string (required) - The focused question",
        "max_tokens": "integer (default: 4000) - Token budget",
        "system": "string (optional) - Custom system prompt",
        "context_query": "string (optional) - Auto-query Snipara for docs"
    }
}
```

**Budget inheritance**: The sub-call gets `min(requested_tokens, parent_remaining * budget_inheritance)` where `budget_inheritance` defaults to `0.5` (50%).

**Auto-context injection**: When `context_query` is set and a Snipara `rlm_context_query` tool is registered, the sub-call automatically fetches relevant documentation and injects it into the system prompt.

**Return value**:
```json
{
    "response": "The answer from the sub-LLM...",
    "tokens_used": 2847,
    "cost": 0.0142,
    "calls": 3
}
```

#### `rlm_batch_complete`

Spawn multiple sub-LLM calls in parallel with a shared budget.

```python
# Tool schema
{
    "name": "rlm_batch_complete",
    "parameters": {
        "queries": [
            {"query": "How does auth work?", "context_query": "authentication"},
            {"query": "How does billing work?", "context_query": "billing"},
            {"query": "How do they interact?"}
        ],
        "max_parallel": 3,
        "total_budget": 8000
    }
}
```

**Budget splitting**: `total_budget` is divided evenly across queries. Each query gets `total_budget // len(queries)` tokens.

**Parallel execution**: Uses `asyncio.gather()` with `asyncio.Semaphore(max_parallel)`.

**Return value**:
```json
{
    "results": [
        {"query": "How does auth work?", "response": "...", "tokens_used": 2000, "cost": 0.01},
        {"query": "How does billing work?", "response": "...", "tokens_used": 1800, "cost": 0.009}
    ]
}
```

### `extra_tools` Pattern

Sub-LLM tools are passed to `_recursive_complete()` via the `extra_tools` parameter rather than mutating the shared `ToolRegistry`. This ensures:

- No state leakage between completions
- Sub-LLM tools are scoped to the specific completion that needs them
- Thread-safe for concurrent completions

```python
# In orchestrator.py
async def _recursive_complete(
    self, ..., extra_tools: list[Tool] | None = None
) -> RLMResult:
    # extra_tools checked alongside registry tools during execution
```

### Budget Inheritance

```python
def _calculate_inherited_budget(
    requested: int,
    parent_remaining: int,
    inheritance_factor: float = 0.5,
) -> int:
    """Calculate the token budget for a sub-call.

    Returns min(requested, parent_remaining * inheritance_factor).
    """
    inherited = int(parent_remaining * inheritance_factor)
    return min(requested, inherited)
```

Example:
```
Parent has 10,000 tokens remaining
Sub-call requests 4,000 tokens
Inheritance factor: 0.5

Inherited budget = min(4000, 10000 * 0.5) = min(4000, 5000) = 4000
```

### Cost Guardrails

```python
@dataclass
class SubCallLimits:
    """Safety limits for sub-LLM orchestration."""
    enabled: bool = True
    max_per_turn: int = 5              # Max sub-calls in one LLM turn
    budget_inheritance: float = 0.5    # Fraction of parent's remaining budget
    max_cost_per_session: float = 1.0  # Dollar cap across all sub-calls
```

**Enforcement points**:
1. **Per-turn limit**: `SubLLMContext.calls_this_turn` tracked and checked before each sub-call
2. **Session cost**: `SubLLMContext.session_cost` accumulated and checked against `max_cost_per_session`
3. **Depth limit**: `max_depth` in `CompletionOptions` prevents infinite recursion
4. **Token budget**: Budget inheritance naturally reduces available tokens at each depth level

### Trajectory Logging

Sub-calls are logged with `sub_call_type` in `TrajectoryEvent`:

```python
@dataclass
class TrajectoryEvent:
    # ... existing fields ...
    sub_call_type: str | None = None  # "sub_complete" or "batch_complete"
```

## Configuration

### Python API

```python
from rlm.core.orchestrator import RLM
from rlm.core.types import CompletionOptions

rlm = RLM(model="gpt-4o-mini")

# Sub-calls are enabled by default
result = await rlm.completion(
    "Analyze this codebase architecture",
    options=CompletionOptions(
        max_depth=3,          # Sub-calls can recurse 3 levels
        token_budget=50000,
    ),
)
```

### Configuration File

```toml
# rlm.toml
[rlm]
sub_calls_enabled = true
sub_calls_max_per_turn = 5
sub_calls_budget_inheritance = 0.5
sub_calls_max_cost_per_session = 1.0
```

### Environment Variables

```bash
RLM_SUB_CALLS_ENABLED=true
RLM_SUB_CALLS_MAX_PER_TURN=5
RLM_SUB_CALLS_BUDGET_INHERITANCE=0.5
RLM_SUB_CALLS_MAX_COST_PER_SESSION=1.0
```

### CLI Flags

```bash
# Enable/disable sub-calls
rlm run "Complex query" --sub-calls        # Enabled (default)
rlm run "Simple query" --no-sub-calls      # Disabled

# Control max sub-calls per turn
rlm run "Query" --max-sub-calls 10
```

## Exception Hierarchy

```python
from rlm.core.exceptions import (
    SubCallBudgetExhausted,   # Per-turn sub-call limit reached
    SubCallDepthExceeded,     # Max recursion depth exceeded
    SubCallCostExceeded,      # Session cost cap exceeded
)
```

These exceptions are caught internally and returned as error messages to the LLM, allowing it to adapt its strategy rather than crashing.

## Safety Considerations

| Risk | Mitigation |
|------|------------|
| Runaway recursion | Hard `max_depth` limit (configurable, clamped to 5) |
| Cost explosion | Per-session dollar cap + budget inheritance (50% per level) |
| Infinite loops | Per-turn call counter with forced termination |
| Context pollution | Each sub-call gets a fresh conversation history |
| Prompt injection via docs | Sub-calls inherit parent's safety system prompt |

## Testing

19 tests in `tests/unit/test_sub_llm.py` covering:

- Budget inheritance math (50% of remaining)
- `SubCallLimits` enforcement (max_per_turn, session cost cap)
- Mock `rlm.completion()` to verify constrained options
- Event merging into parent trajectory with adjusted depth
- Batch parallel execution with budget split
- Depth limit prevents further sub-calls at max depth
- Snipara auto-context injection (mock `rlm_context_query` tool)
- Sub-call tracking (calls_this_turn, session_cost accumulation)
- Error handling for tool creation without RLM instance

## Relationship to Snipara

rlm-runtime handles the LLM orchestration. Snipara provides the context:

```
rlm-runtime (client-side, user's keys)
├── Manages sub-LLM calls
├── Enforces budgets and depth limits
├── Logs trajectories
└── Calls Snipara for context (when context_query is set)
    └── Snipara MCP Server
        ├── rlm_context_query → ranked documentation sections
        ├── rlm_search → regex pattern search
        ├── rlm_remember → store memories
        └── rlm_recall → semantic memory recall
```

Snipara never runs LLM inference. It only provides optimized documentation context that sub-LLM calls consume.
