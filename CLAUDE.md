# CLAUDE.md - RLM Runtime

This document helps Claude Code understand the rlm-runtime project.

## Project Overview

RLM Runtime is a **Recursive Language Model runtime** with sandboxed REPL execution. It enables LLMs to recursively decompose tasks, execute real code in isolated environments, and retrieve context on demand.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  RLM Orchestrator                                               │
│  • Manages recursion depth, token budgets, and cost limits      │
│  • Coordinates LLM calls and tool execution                     │
│  • Tracks API costs in real-time via pricing module             │
├─────────────────────────────────────────────────────────────────┤
│  LLM Backends              │  REPL Environments                 │
│  • LiteLLM (100+ providers)│  • Local (RestrictedPython)        │
│  • OpenAI                  │  • Docker (isolated)               │
│  • Anthropic               │  • WebAssembly (Pyodide)           │
├─────────────────────────────────────────────────────────────────┤
│  Tool Registry             │  MCP Server                        │
│  • execute_code            │  • execute_python (sandbox)        │
│  • file_read               │  • get/set/clear_repl_context      │
│  • Custom tools            │  • Zero API keys required          │
└─────────────────────────────────────────────────────────────────┘
```

## Key Directories

```
src/rlm/
├── core/                    # Core orchestrator and types
│   ├── orchestrator.py      # Main RLM class, completion logic
│   ├── types.py             # Message, Tool, Result types
│   ├── config.py            # Configuration loading
│   ├── exceptions.py        # Custom exception hierarchy
│   └── pricing.py           # Model pricing for cost estimation
├── backends/                # LLM provider integrations
│   ├── base.py              # Abstract backend class
│   ├── litellm.py           # LiteLLM (100+ providers)
│   ├── openai.py            # OpenAI direct
│   └── anthropic.py         # Anthropic direct
├── repl/                    # Code execution environments
│   ├── local.py             # RestrictedPython sandbox
│   ├── docker.py            # Docker container isolation
│   └── wasm.py              # WebAssembly via Pyodide
├── mcp/                     # MCP server for Claude Code
│   ├── server.py            # MCP server implementation
│   └── auth.py              # Snipara OAuth token support
├── tools/                   # Tool system
│   └── registry.py          # Tool registration and lookup
├── visualizer/              # Trajectory visualizer
│   └── app.py               # Streamlit dashboard
└── cli/                     # CLI commands
    └── main.py              # Typer CLI app
```

## MCP Server (Zero API Keys)

The MCP server is designed to work within Claude Code without external API costs:

```python
# src/rlm/mcp/server.py - Key tools
Tools:
- execute_python: Sandboxed code execution (RestrictedPython)
- get_repl_context: Get persistent variables
- set_repl_context: Set persistent variables
- clear_repl_context: Reset state
```

**Why zero API keys?**
- Claude Code IS the LLM (billing included)
- No need for external LLM calls
- Snipara uses OAuth Device Flow (no key copying)

## REPL Environments

### Local (RestrictedPython)
- Fast, no setup required
- Limited isolation
- Best for development/trusted code

### Docker
- Full container isolation
- Configurable resources (CPU, memory)
- Network disabled by default
- Best for production/untrusted code

### WebAssembly (Pyodide)
- Browser-compatible sandbox
- No Docker required
- Portable across platforms

## Exception Hierarchy

```python
from rlm.core.exceptions import (
    RLMError,              # Base exception
    MaxDepthExceeded,      # Recursion limit hit
    TokenBudgetExhausted,  # Token limit hit
    CostBudgetExhausted,   # Cost budget exceeded
    ToolBudgetExhausted,   # Tool call limit hit
    REPLExecutionError,    # Code execution failed
    REPLSecurityError,     # Security violation
    REPLResourceExceeded,  # Memory/CPU limit exceeded
    ToolNotFoundError,     # Unknown tool
    BackendConnectionError, # LLM API error
)
```

## Cost Tracking & Budget Enforcement

The orchestrator tracks API costs and enforces budgets in real-time.

### Pricing Module

```python
from rlm.core.pricing import estimate_cost, format_cost, get_pricing

# Estimate cost for a completion
cost = estimate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=500)
print(format_cost(cost))  # "$0.0005"

# Supported models: OpenAI, Anthropic, Google, Mistral
pricing = get_pricing("claude-3-5-sonnet")  # Also handles "anthropic/claude-3-5-sonnet"
```

### Budget Enforcement

Budgets are checked **before** each LLM call in the recursive completion loop:

```python
from rlm.core.types import CompletionOptions

# Set token AND cost budgets
options = CompletionOptions(
    token_budget=8000,       # Max total tokens
    cost_budget_usd=0.10,    # Max $0.10 spend
    tool_budget=20,          # Max tool calls
)

result = await rlm.completion("Complex task...", options=options)

# Result includes cost tracking
print(f"Total cost: ${result.total_cost_usd:.4f}")
print(f"Input tokens: {result.total_input_tokens}")
print(f"Output tokens: {result.total_output_tokens}")
```

### Cost in Trajectory Events

Each `TrajectoryEvent` includes `estimated_cost_usd`:

```python
options = CompletionOptions(include_trajectory=True)
result = await rlm.completion("...", options=options)

for event in result.events:
    print(f"Call cost: ${event.estimated_cost_usd:.4f}")
```

## Resource Tracking (REPL)

The LocalREPL tracks CPU time and peak memory usage (Unix only):

```python
from rlm.repl.local import LocalREPL

repl = LocalREPL()
result = await repl.execute("x = [i**2 for i in range(10000)]")

print(f"CPU time: {result.cpu_time_ms}ms")
print(f"Peak memory: {result.memory_peak_bytes} bytes")
```

Note: Resource tracking requires the `resource` module (Unix). On Windows, these fields are `None`.

## Configuration

### rlm.toml
```toml
[rlm]
model = "gpt-4o-mini"
environment = "docker"  # local, docker, wasm
max_depth = 4
token_budget = 8000

[docker]
image = "python:3.11-slim"
cpus = 1.0
memory = "512m"
```

### Environment Variables
```bash
RLM_MODEL=gpt-4o-mini
RLM_ENVIRONMENT=docker
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## CLI Commands

```bash
rlm init              # Create rlm.toml
rlm run "prompt"      # Run completion
rlm run --env docker  # With Docker isolation
rlm logs              # View trajectories
rlm visualize         # Launch Streamlit dashboard
rlm mcp-serve         # Start MCP server
rlm doctor            # Check setup
```

## Trajectory Visualizer (Streamlit)

The visualizer is a Streamlit web dashboard for exploring RLM execution trajectories.

### Installation

```bash
# Install with visualizer support
pip install rlm-runtime[visualizer]

# Or install dependencies manually
pip install streamlit plotly
```

### Usage

```bash
# Start visualizer (default port 8501)
rlm visualize

# Custom port
rlm visualize --port 8080

# Custom log directory
rlm visualize --log-dir ./my-logs
```

Opens at **http://localhost:8501**.

### Features

| Feature | Description |
|---------|-------------|
| **Trajectory List** | Browse all execution logs |
| **Token Usage** | Per-call and cumulative token counts |
| **Cost Tracking** | Estimated API costs per call |
| **Tool Calls** | View tool invocations and results |
| **REPL Results** | Code execution outputs and errors |
| **Timing** | Duration of each step |
| **Visualizations** | Plotly charts for token/cost analysis |

### Manual Run

```bash
# Run Streamlit directly
streamlit run -m rlm.visualizer.app

# With options
streamlit run -m rlm.visualizer.app --server.port 8080
```

### Key Files

| File | Purpose |
|------|---------|
| `src/rlm/visualizer/app.py` | Main Streamlit application |
| `src/rlm/cli/main.py:263` | CLI `visualize` command |
| `src/rlm/logging/trajectory.py` | Trajectory logging/loading |

## Testing

```bash
# Run all tests
pytest tests/

# Specific test file
pytest tests/unit/test_repl_local.py

# With coverage
pytest --cov=src/rlm tests/
```

## Development Workflow

1. **Edit code** in `src/rlm/`
2. **Run tests** with `pytest`
3. **Check types** with `mypy src/`
4. **Lint** with `ruff check src/`
5. **Commit** with descriptive messages

## Using rlm-runtime-mcp with Snipara

Both MCP servers work together in Claude Code for powerful workflows:

```
Claude Code
    │
    ├── rlm-runtime-mcp (code sandbox)
    │   └── execute_python, get/set_repl_context
    │
    └── snipara-mcp (context retrieval, OAuth)
        └── context_query, search, shared_context
```

### Setup

```bash
# Install both
pip install rlm-runtime[mcp] snipara-mcp

# Authenticate with Snipara (OAuth - no API key copying)
snipara-mcp-login      # Opens browser
snipara-mcp-status     # Check auth status
```

Tokens stored at `~/.snipara/tokens.json`.

### Complex Use Cases

#### 1. Code Generation with Project Conventions

When generating code that must follow project patterns:

```
User: "Add a new API endpoint for user preferences"

Claude workflow:
1. [snipara: context_query] → Get existing endpoint patterns
2. [snipara: shared_context] → Get team coding standards
3. [rlm: execute_python] → Validate generated code structure
4. Generate code following discovered patterns
```

#### 2. Data Analysis with Documentation Context

When analyzing data that requires domain knowledge:

```
User: "Analyze the sales data and identify anomalies"

Claude workflow:
1. [snipara: context_query] → Get data schema documentation
2. [snipara: search] → Find business rules for anomaly detection
3. [rlm: execute_python] → Run statistical analysis
4. [rlm: set_repl_context] → Store intermediate results
5. [rlm: execute_python] → Generate visualizations
6. Synthesize findings with domain context
```

#### 3. Architecture Review with Code Verification

When reviewing code changes against architecture:

```
User: "Review this PR for architectural compliance"

Claude workflow:
1. [snipara: context_query] → Get architecture guidelines
2. [snipara: shared_context categories=["MANDATORY"]] → Get required patterns
3. [rlm: execute_python] → Parse and analyze code structure
4. Compare against architectural rules
5. Generate compliance report
```

#### 4. Algorithm Implementation with Testing

When implementing algorithms that need verification:

```
User: "Implement the pricing algorithm from our spec"

Claude workflow:
1. [snipara: context_query] → Get pricing specification
2. [snipara: search] → Find test cases from documentation
3. [rlm: execute_python] → Implement algorithm
4. [rlm: set_repl_context] → Store implementation
5. [rlm: execute_python] → Run test cases
6. Iterate until tests pass
```

#### 5. Debugging with Context-Aware Analysis

When debugging requires understanding system behavior:

```
User: "Debug why user authentication is failing"

Claude workflow:
1. [snipara: context_query] → Get auth system documentation
2. [snipara: search pattern="error|exception"] → Find error handling patterns
3. [rlm: execute_python] → Reproduce and analyze error
4. [rlm: execute_python] → Test fix hypotheses
5. Provide solution with documentation references
```

### When to Use Each MCP

| Task Type | Use rlm-runtime-mcp | Use snipara-mcp |
|-----------|---------------------|-----------------|
| Math/calculations | ✅ | |
| Data processing | ✅ | |
| Algorithm verification | ✅ | |
| Code structure analysis | ✅ | |
| Understanding codebase | | ✅ |
| Finding patterns | | ✅ |
| Team best practices | | ✅ |
| Domain knowledge | | ✅ |
| **Complex tasks** | ✅ + ✅ | ✅ + ✅ |

### Snipara Tools Reference

| Tool | Purpose |
|------|---------|
| `context_query` | Semantic search for relevant documentation |
| `search` | Regex pattern search across docs |
| `sections` | List available documentation sections |
| `shared_context` | Get team guidelines and best practices |

### Project Configuration

For this project (rlm-runtime), Snipara is configured with:
- **Project ID**: `cmkqwxi7c0007kq0nsf944wpr`
- **Auth**: OAuth tokens at `~/.snipara/tokens.json`

## Key Files for Common Tasks

| Task | Files |
|------|-------|
| Add MCP tool | `src/rlm/mcp/server.py` |
| Add CLI command | `src/rlm/cli/main.py` |
| Modify sandbox | `src/rlm/repl/local.py` |
| Add exception | `src/rlm/core/exceptions.py` |
| Change config | `src/rlm/core/config.py` |
| Update orchestrator | `src/rlm/core/orchestrator.py` |
| Update model pricing | `src/rlm/core/pricing.py` |
| Modify result types | `src/rlm/core/types.py` |

## Snipara Context Retrieval Improvement Goals

### Current Bottlenecks & Solutions

#### 1. Token Efficiency (4.1x → 10x+ target)

**Current limitation:** The extraction algorithm includes too many sections.

**Planned improvements:**
- **Smarter section scoring** - Weight title matches higher, penalize long sections
- **Semantic deduplication** - Remove overlapping content
- **Adaptive budgeting** - Use less context for simple queries

#### 2. Context Quality (38% precision → 70%+ target)

**Current limitation:** The section scoring is too broad, matching on common words.

**Planned improvements:**
- Stricter relevance thresholds
- TF-IDF or embedding-based scoring instead of keyword overlap
- Better test case definitions with more specific `relevant_sections`

#### 3. Answer Quality (7.1 → 8.5+ target)

**Current limitation:** Some context is relevant but not specific enough.

**Planned improvements:**
- More targeted section extraction
- Better ranking of highly relevant vs tangentially relevant content
- Improved query decomposition for complex questions

## CI/CD: Git to PyPI Deployment

The project uses **GitHub Actions** for automatic PyPI deployment when pushing to the main branch.

### Automatic Deployment Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  Developer Workflow                                             │
│                                                                 │
│  1. Make changes to code                                        │
│  2. Run tests locally: pytest tests/                            │
│  3. Commit changes: git commit -m "..."                         │
│  4. Push to main: git push origin master                        │
│                                                                 │
│  ↓ GitHub Actions triggers automatically                        │
│                                                                 │
│  5. CI runs tests                                               │
│  6. CI builds package: python -m build                          │
│  7. CI uploads to PyPI: twine upload dist/*                     │
│  8. Package available: pip install rlm-runtime                  │
└─────────────────────────────────────────────────────────────────┘
```

### Manual Release Steps (if needed)

```bash
# 1. Bump version in pyproject.toml
# version = "0.2.1"

# 2. Commit version bump
git add pyproject.toml
git commit -m "Bump version to 0.2.1"

# 3. Push to trigger CI/CD
git push origin master

# 4. (Optional) Create git tag
git tag v0.2.1
git push origin v0.2.1
```

### Local Build & Test (before push)

```bash
# Run tests
pytest tests/ -v

# Build locally to verify
python -m build

# Check built files
ls dist/
# rlm_runtime-0.2.0-py3-none-any.whl
# rlm_runtime-0.2.0.tar.gz

# (Optional) Test install locally
pip install dist/rlm_runtime-0.2.0-py3-none-any.whl
```

### PyPI Package Info

- **Package Name:** `rlm-runtime`
- **PyPI URL:** https://pypi.org/project/rlm-runtime/
- **Install:** `pip install rlm-runtime`
- **With MCP:** `pip install rlm-runtime[mcp]`
- **All extras:** `pip install rlm-runtime[all]`

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.2.0 | Jan 2025 | Cost tracking, budget enforcement, resource monitoring |
| 0.1.x | Dec 2024 | Initial release with MCP server |

## Recent Changes

- **Cost Tracking**: New pricing.py module with model pricing data for OpenAI, Anthropic, Google, and Mistral models. RLMResult now includes `total_cost_usd`, `total_input_tokens`, `total_output_tokens`.
- **Budget Enforcement**: Token budget is now enforced (was a bug - configured but never checked). New `cost_budget_usd` option for cost-based limits.
- **Resource Tracking**: LocalREPL tracks CPU time and peak memory via `cpu_time_ms` and `memory_peak_bytes` in REPLResult.
- **New Exceptions**: Added `CostBudgetExhausted` and `REPLResourceExceeded` exceptions.
- **MCP Server Refactor**: Simplified to code sandbox only (no LLM calls)
- **OAuth Support**: Added auth.py for Snipara token integration
- **WebAssembly REPL**: New wasm.py for Pyodide execution
- **Exception Hierarchy**: Comprehensive error handling in exceptions.py
- **Trajectory Visualizer**: Streamlit dashboard for debugging
