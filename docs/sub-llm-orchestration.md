# Sub-LLM Orchestration (Phase: Planned)

## Overview

Sub-LLM Orchestration enables rlm-runtime to make **recursive LLM calls within a single completion**, allowing the model to spawn focused sub-queries that each get their own context window, depth budget, and token limit. This builds on the existing `_recursive_complete()` infrastructure in the Orchestrator.

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

## Design Principles

### 1. User Provides Their Own Keys (BYOK)

rlm-runtime is a local tool. The user configures their LLM backend (Anthropic, OpenAI, LiteLLM, etc.) with their own API keys. Sub-LLM calls use the same backend and key as the primary call. There is no server-side inference - everything runs client-side.

### 2. Budget Inheritance with Limits

Each sub-call inherits a fraction of the parent's remaining budget:

```python
# Parent has 10,000 token budget remaining
# Sub-call gets at most 50% of remaining budget
sub_budget = min(requested_budget, parent_remaining * 0.5)
```

### 3. Depth-Limited Recursion

The existing `max_depth` parameter in the Orchestrator already enforces this. Sub-LLM calls decrement the depth counter:

```python
# If max_depth=3:
# Primary call:    depth=0 (can spawn sub-calls)
# Sub-call:        depth=1 (can spawn sub-sub-calls)
# Sub-sub-call:    depth=2 (can spawn one more level)
# Sub-sub-sub-call: depth=3 (max reached, no more sub-calls)
```

### 4. Cost Tracking

Every sub-call is tracked in the trajectory with full token usage. The cost tracking system (already in Phase 4) aggregates costs across all sub-calls.

## New Tools

### `rlm_sub_complete`

Spawn a sub-LLM call with its own context window.

```python
Tool: rlm_sub_complete
Parameters:
  - query: string (required)
      The focused question for the sub-call
  - max_tokens: integer (default: 4000)
      Token budget for the sub-call's response
  - system: string (optional)
      Custom system prompt for the sub-call
  - tools: array of string (optional)
      Restrict which tools the sub-call can use
      Default: inherits parent's tool set
  - context_query: string (optional)
      If set, auto-calls Snipara context_query before the sub-LLM
      starts, injecting relevant docs into the sub-call's context
```

**Example usage by the LLM:**

```
I need to understand the auth flow. Let me delegate this.

<tool_call>
rlm_sub_complete({
    "query": "Explain the JWT token lifecycle in this codebase",
    "context_query": "JWT authentication token refresh",
    "max_tokens": 3000
})
</tool_call>
```

### `rlm_batch_complete`

Spawn multiple sub-LLM calls in parallel.

```python
Tool: rlm_batch_complete
Parameters:
  - queries: array of objects
      Each with: query, max_tokens, context_query (optional)
  - max_parallel: integer (default: 3)
      Maximum concurrent sub-calls
  - total_budget: integer (default: 8000)
      Total token budget shared across all sub-calls
```

## Implementation Plan

### Step 1: Expose `_recursive_complete()` as a Tool

The Orchestrator already has `_recursive_complete()` with depth limits and trajectory tracking. Wrap it as a callable tool:

```python
# In orchestrator.py
async def _handle_sub_complete(self, params: dict) -> str:
    """Handle rlm_sub_complete tool call."""
    if self._current_depth >= self.max_depth:
        return "Maximum recursion depth reached. Summarize with available context."

    sub_result = await self._recursive_complete(
        query=params["query"],
        system=params.get("system"),
        max_tokens=min(params.get("max_tokens", 4000), self._remaining_budget * 0.5),
        depth=self._current_depth + 1,
        tools=params.get("tools"),
    )

    return sub_result.response
```

### Step 2: Auto-Context Injection

If `context_query` is provided and Snipara is configured, automatically query Snipara and inject results into the sub-call's system prompt:

```python
if params.get("context_query") and self._snipara_client:
    context = await self._snipara_client.context_query(
        query=params["context_query"],
        max_tokens=params.get("context_budget", 3000),
    )
    system = f"{system}\n\nRelevant documentation:\n{context}"
```

### Step 3: Parallel Batch Execution

For `rlm_batch_complete`, use `asyncio.gather` with semaphore:

```python
async def _handle_batch_complete(self, params: dict) -> str:
    sem = asyncio.Semaphore(params.get("max_parallel", 3))
    budget_per_query = params.get("total_budget", 8000) // len(params["queries"])

    async def run_one(q):
        async with sem:
            return await self._handle_sub_complete({
                **q,
                "max_tokens": min(q.get("max_tokens", budget_per_query), budget_per_query),
            })

    results = await asyncio.gather(*[run_one(q) for q in params["queries"]])
    return "\n\n---\n\n".join(
        f"## Result for: {q['query']}\n{r}"
        for q, r in zip(params["queries"], results)
    )
```

### Step 4: Cost Guardrails

```python
@dataclass
class SubCallLimits:
    max_depth: int = 3               # Maximum recursion depth
    max_sub_calls_per_turn: int = 5   # Max sub-calls in one turn
    max_total_tokens: int = 50000     # Total tokens across all sub-calls
    max_cost_per_session: float = 1.0 # Dollar cap per session
    budget_inheritance: float = 0.5   # Fraction of remaining budget per sub-call
```

## Trajectory Logging

Sub-calls are logged as nested entries in the JSONL trajectory:

```json
{
  "type": "sub_completion",
  "depth": 1,
  "parent_turn": 3,
  "query": "How does JWT auth work?",
  "context_query": "JWT authentication",
  "tokens_used": 2847,
  "cost": 0.0142,
  "duration_ms": 3200,
  "tools_called": ["context_query", "execute_python"],
  "result_tokens": 1523
}
```

## Safety Considerations

| Risk | Mitigation |
|------|------------|
| Runaway recursion | Hard `max_depth` limit (default: 3) |
| Cost explosion | Per-session dollar cap + budget inheritance (50% per level) |
| Infinite loops | Turn counter with forced termination |
| Context pollution | Each sub-call gets a fresh conversation history |
| Prompt injection via docs | Sub-calls inherit parent's safety system prompt |

## Relationship to Snipara

rlm-runtime handles the LLM orchestration. Snipara provides the context:

```
rlm-runtime (client-side, user's keys)
├── Manages sub-LLM calls
├── Enforces budgets and depth limits
├── Logs trajectories
└── Calls Snipara for context
    └── Snipara MCP Server (SaaS)
        ├── context_query → ranked sections
        ├── repl_context → REPL-ready context
        ├── load_document → raw file content
        └── orchestrate → multi-round exploration
```

Snipara never runs LLM inference. It only provides optimized documentation context that sub-LLM calls consume.

## Prerequisites

- rlm-runtime Phase 1 (Orchestrator with `_recursive_complete()`) -- DONE
- rlm-runtime Phase 4 (Cost Tracking) -- DONE
- Snipara MCP tools auto-registration (`_register_snipara_tools()`) -- DONE
- Snipara `rlm_repl_context` tool (Phase 13) -- DONE

## Configuration

```toml
# rlm.toml
[rlm]
max_depth = 3
token_budget = 50000

[rlm.sub_calls]
enabled = true
max_per_turn = 5
budget_inheritance = 0.5
max_cost_per_session = 1.0

[rlm.snipara]
api_key = "rlm_..."
project_slug = "my-project"
auto_context = true  # Auto-query Snipara for sub-calls with context_query
```
