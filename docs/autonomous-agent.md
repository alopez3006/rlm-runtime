# Autonomous RLM Agent (Phase: Planned)

## Overview

The Autonomous RLM Agent implements the full Recursive Language Model loop from Alex Zhang's paper. The model explores documentation, writes and executes code, spawns sub-LLM calls, and terminates when it has enough information to answer -- all in a single `rlm.completion()` call.

This is the capstone feature that combines all prior capabilities:
- **REPL execution** (Phase 1) -- Run code in sandboxed environments
- **Snipara context** (existing) -- Retrieve optimized documentation
- **REPL Context Bridge** (Snipara Phase 13) -- Pre-packaged context for REPL
- **Sub-LLM Orchestration** (prior phase) -- Recursive sub-calls with budget control
- **Cost tracking** (Phase 4) -- Full cost visibility across the agent loop

## The RLM Loop

```
┌────────────────────────────────────────────────────────────────┐
│  RLM Agent Loop                                                 │
│                                                                  │
│  1. OBSERVE                                                      │
│     - Load project context (Snipara rlm_repl_context)           │
│     - Scan documentation structure                               │
│     - Review existing code                                       │
│                                                                  │
│  2. THINK                                                        │
│     - Analyze what information is needed                         │
│     - Plan which files/sections to explore                       │
│     - Decide: explore more? sub-LLM call? or terminate?         │
│                                                                  │
│  3. ACT                                                          │
│     - Execute code to analyze data                               │
│     - Query Snipara for specific context                         │
│     - Spawn sub-LLM for focused sub-problems                    │
│                                                                  │
│  4. TERMINATE                                                    │
│     - Call FINAL("answer text") to return natural language       │
│     - Call FINAL_VAR("var_name") to return computed result       │
│     - Agent loop ends, result returned to user                   │
│                                                                  │
│  Loop: 1 → 2 → 3 → 2 → 3 → ... → 4                            │
│  Max iterations: configurable (default: 10)                      │
└────────────────────────────────────────────────────────────────┘
```

## FINAL / FINAL_VAR Protocol

The agent signals completion using special tool calls:

### `FINAL(answer)`

Returns a natural language answer. The agent has gathered enough context and is ready to synthesize.

```python
# The LLM calls this when ready to answer:
FINAL("The authentication system uses JWT tokens with RS256 signing. "
      "Tokens are issued by /api/auth/login and refreshed via /api/auth/refresh. "
      "The middleware in auth.py validates tokens on every request.")
```

### `FINAL_VAR(var_name)`

Returns a computed value from the REPL context. Useful when the agent wrote code to analyze data and wants to return the result.

```python
# The LLM executes code, then returns the computed result:
execute_python("result = analyze_logs(context['files']['logs.md'])")
FINAL_VAR("result")  # Returns the value of 'result' from REPL context
```

## Implementation Design

### Agent Runner

```python
@dataclass
class AgentConfig:
    """Configuration for the autonomous agent loop."""
    max_iterations: int = 10          # Maximum observe-think-act cycles
    max_depth: int = 3                # Sub-LLM recursion depth
    token_budget: int = 50000         # Total token budget
    cost_limit: float = 2.0           # Dollar cap for entire agent run
    timeout_seconds: int = 120        # Wall-clock timeout
    auto_context: bool = True         # Auto-load Snipara context at start
    context_budget: int = 8000        # Tokens for initial context load
    trajectory_log: bool = True       # Log full trajectory for debugging


class AgentRunner:
    """Runs the autonomous RLM agent loop."""

    def __init__(self, rlm: RLM, config: AgentConfig = None):
        self.rlm = rlm
        self.config = config or AgentConfig()
        self._iteration = 0
        self._total_tokens = 0
        self._total_cost = 0.0

    async def run(self, task: str) -> AgentResult:
        """Execute the agent loop until FINAL or limit reached."""

        # Phase 1: Initial context load (if Snipara configured)
        if self.config.auto_context:
            context = await self._load_initial_context(task)

        # Phase 2: Agent loop
        while self._iteration < self.config.max_iterations:
            self._iteration += 1

            result = await self.rlm.completion(
                task,
                tools=self._get_tools(),
                max_tokens=self._remaining_budget(),
            )

            # Check for FINAL/FINAL_VAR in tool calls
            terminal = self._check_terminal(result)
            if terminal:
                return AgentResult(
                    answer=terminal.value,
                    iterations=self._iteration,
                    total_tokens=self._total_tokens,
                    total_cost=self._total_cost,
                    trajectory=self._trajectory,
                )

            self._total_tokens += result.usage.total_tokens
            self._total_cost += result.cost

        # Max iterations reached -- force termination
        return AgentResult(
            answer=result.response,  # Use last response
            iterations=self._iteration,
            forced_termination=True,
            total_tokens=self._total_tokens,
            total_cost=self._total_cost,
            trajectory=self._trajectory,
        )
```

### Tool Set

The agent has access to all standard tools plus terminal tools:

| Tool | Category | Purpose |
|------|----------|---------|
| `execute_python` | REPL | Run code in sandbox |
| `get_repl_context` | REPL | Read persistent state |
| `set_repl_context` | REPL | Write persistent state |
| `context_query` | Snipara | Search documentation |
| `repl_context` | Snipara | Load REPL-ready context with helpers |
| `load_document` | Snipara | Read raw file content |
| `orchestrate` | Snipara | Multi-round exploration |
| `rlm_sub_complete` | Sub-LLM | Delegate sub-problems |
| `rlm_batch_complete` | Sub-LLM | Parallel sub-queries |
| **`FINAL`** | Terminal | Return natural language answer |
| **`FINAL_VAR`** | Terminal | Return computed variable |

### System Prompt

The agent receives a structured system prompt that explains the loop:

```python
AGENT_SYSTEM_PROMPT = """You are an autonomous research agent. Your goal is to answer
the user's question by exploring documentation and code.

## Available Actions

1. **Explore**: Use context_query, load_document, orchestrate to find information
2. **Analyze**: Use execute_python to run analysis code on loaded context
3. **Delegate**: Use rlm_sub_complete for focused sub-problems
4. **Terminate**: Call FINAL("your answer") when you have enough information

## Rules

- Always explore before answering. Don't guess.
- Use FINAL_VAR when you computed a result in code.
- Keep sub-calls focused and budget-aware.
- If stuck after 3 iterations, call FINAL with your best answer and note gaps.

## Context

Your REPL has a persistent `context` variable with project documentation.
Use peek(), grep(), sections(), files() helpers to navigate it.
"""
```

## Trajectory Logging

Every agent run produces a detailed trajectory log:

```json
{
  "agent_run_id": "agent_abc123",
  "task": "Explain how auth and billing interact",
  "config": {
    "max_iterations": 10,
    "max_depth": 3,
    "token_budget": 50000
  },
  "iterations": [
    {
      "iteration": 1,
      "phase": "observe",
      "tool_calls": [
        {"tool": "repl_context", "params": {"query": "auth billing"}, "tokens": 2847}
      ],
      "tokens_used": 3200,
      "cost": 0.016
    },
    {
      "iteration": 2,
      "phase": "act",
      "tool_calls": [
        {"tool": "execute_python", "code": "auth_files = grep('auth')\nbilling_files = grep('billing')"},
        {"tool": "load_document", "params": {"path": "docs/auth.md"}}
      ],
      "tokens_used": 4100,
      "cost": 0.021
    },
    {
      "iteration": 3,
      "phase": "delegate",
      "tool_calls": [
        {"tool": "rlm_sub_complete", "query": "JWT token lifecycle", "sub_tokens": 2500}
      ],
      "tokens_used": 5200,
      "cost": 0.026
    },
    {
      "iteration": 4,
      "phase": "terminate",
      "tool_calls": [
        {"tool": "FINAL", "answer": "Auth and billing interact through..."}
      ],
      "tokens_used": 1800,
      "cost": 0.009
    }
  ],
  "result": {
    "answer": "Auth and billing interact through...",
    "iterations": 4,
    "total_tokens": 14300,
    "total_cost": 0.072,
    "forced_termination": false
  }
}
```

## Usage

### Python API

```python
from rlm import RLM
from rlm.agent import AgentRunner, AgentConfig

rlm = RLM(
    model="claude-sonnet-4-20250514",
    snipara_api_key="rlm_...",
    snipara_project_slug="my-project",
    environment="docker",  # Sandboxed execution
)

config = AgentConfig(
    max_iterations=10,
    token_budget=50000,
    cost_limit=2.0,
    auto_context=True,
)

agent = AgentRunner(rlm, config)
result = await agent.run(
    "How does the payment webhook handler validate Stripe signatures, "
    "and what happens on signature failure?"
)

print(result.answer)
print(f"Iterations: {result.iterations}")
print(f"Cost: ${result.total_cost:.4f}")
print(f"Tokens: {result.total_tokens}")
```

### CLI

```bash
# Run agent from command line
rlm agent "How does auth work?" \
    --max-iterations 10 \
    --budget 50000 \
    --cost-limit 2.0 \
    --env docker

# View trajectory
rlm logs --last --format rich

# Visualize agent run
rlm visualize --agent
```

### MCP Server

New MCP tools for Claude Desktop/Code:

```
Tool: rlm_agent_run
Parameters:
  - task: string (required) - The question or task
  - max_iterations: integer (default: 10)
  - token_budget: integer (default: 50000)
  - cost_limit: float (default: 2.0)

Tool: rlm_agent_status
Parameters:
  - run_id: string (required)
Returns: current iteration, tokens used, cost, status

Tool: rlm_agent_cancel
Parameters:
  - run_id: string (required)
```

## Safety and Guardrails

### Hard Limits (Non-Configurable)

| Limit | Value | Rationale |
|-------|-------|-----------|
| Absolute max iterations | 50 | Prevent infinite loops |
| Absolute max depth | 5 | Prevent recursion bombs |
| Absolute cost cap | $10 | Prevent billing surprises |
| Absolute timeout | 600s | Prevent hung agents |

### Configurable Limits

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `max_iterations` | 10 | 1-50 | Observe-think-act cycles |
| `max_depth` | 3 | 1-5 | Sub-LLM recursion depth |
| `token_budget` | 50,000 | 1K-500K | Total tokens across all calls |
| `cost_limit` | $2.00 | $0.01-$10 | Dollar cap for entire run |
| `timeout_seconds` | 120 | 10-600 | Wall-clock timeout |

### Graceful Degradation

When limits are hit, the agent doesn't just crash:

1. **Budget exhausted**: Force FINAL with best answer so far + "budget exhausted" note
2. **Depth limit**: Sub-call returns "summarize with available context" instead of recursing
3. **Iteration limit**: Force FINAL with accumulated context
4. **Timeout**: Cancel pending calls, force FINAL with partial results
5. **Cost limit**: Same as budget exhausted

## Testing Strategy

Agent behavior is non-deterministic, so testing requires:

### 1. Deterministic Replay Tests

Record agent trajectories and replay with mocked LLM responses:

```python
async def test_agent_finds_auth_docs():
    # Load recorded trajectory
    trajectory = load_trajectory("fixtures/auth_query_trajectory.json")

    # Create agent with mocked LLM that replays recorded responses
    agent = AgentRunner(MockRLM(trajectory), AgentConfig(max_iterations=5))
    result = await agent.run("How does auth work?")

    assert "JWT" in result.answer
    assert result.iterations <= 5
    assert not result.forced_termination
```

### 2. Property-Based Tests

Test invariants that must hold regardless of LLM behavior:

```python
async def test_agent_respects_budget():
    agent = AgentRunner(rlm, AgentConfig(token_budget=1000))
    result = await agent.run("anything")
    assert result.total_tokens <= 1500  # Small overflow tolerance

async def test_agent_always_terminates():
    agent = AgentRunner(rlm, AgentConfig(max_iterations=3, timeout_seconds=30))
    result = await agent.run("anything")
    assert result.iterations <= 3
```

### 3. Integration Tests

End-to-end tests with real LLM and Snipara:

```python
@pytest.mark.integration
@pytest.mark.slow
async def test_agent_e2e():
    rlm = RLM(model="gpt-4o-mini", snipara_project_slug="test-project")
    agent = AgentRunner(rlm, AgentConfig(max_iterations=5, cost_limit=0.50))
    result = await agent.run("What testing framework does this project use?")

    assert result.answer  # Non-empty
    assert result.total_cost < 0.50
```

## Prerequisites

| Dependency | Status | Description |
|------------|--------|-------------|
| Phase 1: Orchestrator | DONE | `_recursive_complete()`, depth limits |
| Phase 2: Distribution | DONE | PyPI, CI/CD |
| Phase 4: Cost Tracking | DONE | Token/cost budgets |
| Snipara Integration | DONE | Auto-registered tools |
| Snipara REPL Context Bridge | DONE | `rlm_repl_context` tool |
| Sub-LLM Orchestration | REQUIRED | `rlm_sub_complete`, `rlm_batch_complete` |

## Configuration

```toml
# rlm.toml
[rlm]
model = "claude-sonnet-4-20250514"
environment = "docker"

[rlm.agent]
enabled = true
max_iterations = 10
token_budget = 50000
cost_limit = 2.0
timeout_seconds = 120
auto_context = true
context_budget = 8000

[rlm.agent.terminal]
# Which terminal tools are available
final = true        # FINAL("answer")
final_var = true    # FINAL_VAR("var_name")

[rlm.snipara]
api_key = "rlm_..."
project_slug = "my-project"
```

## File Structure

```
src/rlm/
├── agent/
│   ├── __init__.py          # AgentRunner, AgentConfig, AgentResult
│   ├── runner.py            # Main agent loop implementation
│   ├── terminal.py          # FINAL/FINAL_VAR protocol parsing
│   ├── trajectory.py        # Trajectory logging and replay
│   └── guardrails.py        # Budget, depth, timeout enforcement
├── core/
│   └── orchestrator.py      # Extended with sub-LLM tools
├── tools/
│   ├── terminal.py          # FINAL, FINAL_VAR tool definitions
│   └── sub_llm.py           # rlm_sub_complete, rlm_batch_complete
└── mcp/
    └── server.py            # New MCP tools: agent_run, agent_status, agent_cancel
```

## Visualization

The existing Streamlit trajectory visualizer will be extended to show:

- Agent iteration timeline (observe → think → act → terminate)
- Token/cost accumulation chart per iteration
- Sub-LLM call tree (depth visualization)
- FINAL/FINAL_VAR decision point
- Tool call frequency heatmap

```bash
# Launch visualizer for agent runs
rlm visualize --agent --run-id agent_abc123
```
