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
│  LLM Backend (LiteLLM)     │  REPL Environments                 │
│  • OpenAI models           │  • Local (RestrictedPython)        │
│  • Anthropic models        │  • Docker (isolated)               │
│  • 100+ other providers    │  • WebAssembly (Pyodide)           │
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
│   └── litellm.py           # LiteLLM (unified backend for all providers)
├── repl/                    # Code execution environments
│   ├── local.py             # RestrictedPython sandbox
│   ├── docker.py            # Docker container isolation (with resource reporting)
│   └── wasm.py              # WebAssembly via Pyodide
├── mcp/                     # MCP server for Claude Code
│   ├── server.py            # MCP server (REPL + agent tools)
│   └── auth.py              # Snipara OAuth token support
├── tools/                   # Tool system
│   ├── registry.py          # Tool registration and lookup
│   ├── snipara.py           # Native Snipara tools (OAuth HTTP client)
│   └── sub_llm.py           # Sub-LLM orchestration tools
├── agent/                   # Autonomous agent
│   ├── __init__.py          # Exports AgentRunner, AgentConfig, AgentResult
│   ├── config.py            # AgentConfig with hard safety limits
│   ├── result.py            # AgentResult dataclass
│   ├── runner.py            # Main agent loop
│   ├── terminal.py          # FINAL/FINAL_VAR protocol
│   ├── prompts.py           # System and iteration prompts
│   └── guardrails.py        # Budget/iteration/cost checks
├── visualizer/              # Trajectory visualizer
│   └── app.py               # Streamlit dashboard
└── cli/                     # CLI commands
    └── main.py              # Typer CLI (run, agent, init, logs, etc.)
```

## MCP Server (Zero API Keys)

The MCP server is designed to work within Claude Code without external API costs:

```python
# src/rlm/mcp/server.py - Key tools
Tools:
- execute_python: Sandboxed code execution (RestrictedPython)
  - session_id: Isolated context per session
  - profile: quick/default/analysis/extended resource limits
- get_repl_context: Get persistent variables from session
- set_repl_context: Set persistent variables in session
- clear_repl_context: Reset session state
- list_sessions: List all active sessions with metadata
- destroy_session: Destroy a session and free resources
```

**Why zero API keys?**
- Claude Code IS the LLM (billing included)
- No need for external LLM calls
- Snipara uses OAuth Device Flow (no key copying)

## REPL Environments

The REPL system provides three execution environments with different isolation levels and tradeoffs.

### Local Mode (RestrictedPython)

**File:** `src/rlm/repl/local.py`

Uses RestrictedPython for in-process sandboxing:

| Aspect | Details |
|--------|---------|
| **Isolation** | Software-based via RestrictedPython guards |
| **Mechanism** | Compiles code with `compile_restricted()`, executes in controlled namespace |
| **Import restrictions** | Whitelist of safe modules only |
| **Attribute access** | Guarded via `safer_getattr`, `guarded_getitem`, `guarded_getiter` |
| **Performance** | Fast (~0ms startup) - runs in same process |
| **Setup** | No setup required |
| **Resource tracking** | CPU time + peak memory (Unix only via `resource` module) |
| **Context storage** | Python objects stored directly in `_context` dict |

**Security note:** This provides defense-in-depth but is NOT a complete sandbox. For untrusted code, use DockerREPL instead.

```python
from rlm.repl.local import LocalREPL

repl = LocalREPL(timeout=30)
result = await repl.execute("print(sum(range(100)))")
print(result.output)  # "4950\n"
print(f"CPU: {result.cpu_time_ms}ms, Memory: {result.memory_peak_bytes} bytes")
```

### Docker Mode (Container Isolation)

**File:** `src/rlm/repl/docker.py`

Uses Docker containers for OS-level isolation:

| Aspect | Details |
|--------|---------|
| **Isolation** | Full container isolation (separate filesystem, network, processes) |
| **Mechanism** | Spins up new container per execution, runs script, destroys container |
| **Network** | Disabled by default (`network_disabled=True`) |
| **Resource limits** | Hard limits via `cpu_quota` and `mem_limit` (container killed if exceeded) |
| **Filesystem** | Read-only mounts, automatic cleanup |
| **Performance** | Slower (~100-500ms startup) - container overhead |
| **Setup** | Requires Docker daemon + `pip install rlm-runtime[docker]` |
| **Context storage** | Must be JSON-serializable (passed via temp file to container) |

```python
from rlm.repl.docker import DockerREPL

repl = DockerREPL(
    image="python:3.11-slim",
    cpus=1.0,
    memory="512m",
    network_disabled=True,
)
result = await repl.execute("print(sum(range(100)))")
```

### WebAssembly Mode (Pyodide)

**File:** `src/rlm/repl/wasm.py`

Uses Pyodide for browser-compatible sandboxing:

| Aspect | Details |
|--------|---------|
| **Isolation** | WebAssembly sandbox |
| **Mechanism** | Runs Python via Pyodide in WASM runtime |
| **Setup** | No Docker required |
| **Portability** | Works across platforms including browsers |

### Mode Comparison

| Feature | Local | Docker | WebAssembly |
|---------|-------|--------|-------------|
| **Security level** | Medium | High | Medium-High |
| **Startup time** | ~0ms | ~100-500ms | ~1-2s (first load) |
| **Network access** | Blocked (import) | Blocked (OS) | Blocked (WASM) |
| **File system** | Blocked (import) | Isolated | Sandboxed |
| **Process isolation** | None | Full | WASM sandbox |
| **Memory limits** | Soft (tracking) | Hard (killed) | WASM limits |
| **Dependencies** | RestrictedPython | Docker daemon | Pyodide |
| **Best for** | Dev, trusted code | Production, untrusted | Browser, portable |

### Security Level Details

| Mode | Rating | Risk | Mitigation |
|------|--------|------|------------|
| **Local** | ⚠️ Medium | RestrictedPython can be bypassed via introspection attacks | Use only for trusted/AI-generated code |
| **Docker** | ✅ High | Container escape requires kernel exploit | Add seccomp/AppArmor for maximum security |
| **WASM** | ✅ Medium-High | WASM sandbox is robust but less battle-tested | Good for browser environments |

**Security recommendations:**
- **Local mode:** Suitable for development and AI-generated code. NOT recommended for arbitrary user input.
- **Docker mode:** Use for production and untrusted code. Add `--security-opt` flags for defense in depth.
- **WASM mode:** Good portability with decent isolation. Best for browser-based applications.

### Allowed Imports

**File:** `src/rlm/repl/safety.py`

The sandbox only allows these safe standard library modules:

```python
ALLOWED_IMPORTS = {
    # Core utilities
    "json", "re", "math", "datetime", "time", "uuid",
    "hashlib", "base64", "string", "textwrap",

    # Collections and iteration
    "collections", "itertools", "functools", "operator",

    # Data structures
    "dataclasses", "typing", "enum", "copy",

    # Parsing and math
    "csv", "statistics", "decimal", "fractions",

    # Path operations (read-only)
    "pathlib", "posixpath", "ntpath",

    # URL parsing (no requests)
    "urllib.parse",

    # Text processing
    "difflib", "unicodedata",
}
```

### Blocked Imports

These modules are explicitly blocked for security:

| Category | Blocked Modules |
|----------|-----------------|
| **System access** | `os`, `sys`, `subprocess`, `shutil`, `platform`, `signal`, `resource` |
| **Network** | `socket`, `ssl`, `requests`, `urllib.request`, `http`, `ftplib`, `smtplib` |
| **Serialization** | `pickle`, `shelve`, `marshal` (can execute arbitrary code) |
| **Database** | `sqlite3` |
| **Low-level** | `ctypes`, `cffi`, `mmap` |
| **Concurrency** | `multiprocessing`, `threading`, `concurrent`, `asyncio` |
| **Code execution** | `importlib`, `builtins`, `eval`, `exec`, `compile`, `code` |
| **File operations** | `tempfile`, `fileinput`, `glob`, `fnmatch` |
| **Debugging** | `pdb`, `bdb`, `trace`, `traceback`, `inspect`, `dis`, `ast` |
| **Other** | `atexit`, `gc` |

### REPL Limitations

#### No UI/UX or Visualization Support

The REPL is designed for **pure computation only** and cannot render visual output:

**1. No visualization libraries allowed:**
- `matplotlib` - charts/graphs
- `PIL/Pillow` - image manipulation
- `plotly` - interactive visualizations
- `seaborn` - statistical graphics
- `tkinter` - GUI widgets
- `pygame` - graphics/games
- `svgwrite` - SVG generation

**2. No display mechanism:**
Both Local and Docker REPLs are headless - there is no browser, window system, or way to render pixels. Output is text-only via `REPLResult.output`.

**3. No file output for images:**
Cannot save images to disk since `tempfile`, `glob`, and file I/O are blocked.

**4. Design intent:**
The REPL is intentionally limited to:
- Math and algorithms
- Data processing and transformation
- Text manipulation
- Logic validation
- JSON/CSV parsing

#### Workarounds for Visualization

If visualization is needed:

| Approach | Description | Tradeoff |
|----------|-------------|----------|
| **Extend allowed imports** | Add matplotlib, PIL to `ALLOWED_IMPORTS` | Security risk |
| **Return base64 images** | Generate image, encode as base64 text, decode client-side | Complexity |
| **Generate code as text** | Output HTML/CSS/SVG as strings, render elsewhere | Manual step |
| **Docker with X11** | Mount display socket or use virtual framebuffer | Complex setup |

#### Output Limits

From `src/rlm/repl/safety.py`:

```python
MAX_OUTPUT_SIZE = 100_000   # 100KB max output
MAX_OUTPUT_LINES = 1000     # Max lines
MAX_EXECUTION_TIME = 30     # Default timeout (seconds)
MAX_MEMORY_MB = 512         # Docker memory limit
```

### When to Use Each Mode

| Scenario | Recommended Mode |
|----------|------------------|
| Local development | Local |
| Quick prototyping | Local |
| Trusted internal code | Local |
| User-submitted code | Docker |
| Production workloads | Docker |
| Browser environments | WebAssembly |
| CI/CD pipelines | Docker |
| No Docker available | Local or WebAssembly |

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
    SniparaAPIError,       # Snipara HTTP API error (native tools)
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
timeout_seconds = 120     # Overall completion timeout
cost_budget_usd = 0.10    # Maximum API cost

# Security: restrict file access to specific paths
allowed_paths = ["/path/to/project", "/tmp"]

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
rlm run --sub-calls   # Enable sub-LLM calls (default)
rlm run --no-sub-calls  # Disable sub-LLM calls
rlm agent "task"      # Run autonomous agent
rlm agent "task" -v   # Verbose with iteration details
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

## Snipara Integration (Native Tools + MCP Fallback)

RLM can access Snipara context retrieval, memory, and shared collections
through **two mechanisms** — a native HTTP client (preferred) and the
`snipara-mcp` package (backward-compatible fallback).

### Architecture

```
Orchestrator._register_snipara_tools()
    │
    ├── Attempt 1: Native HTTP client (src/rlm/tools/snipara.py)
    │   ├── SniparaClient.from_config(config)
    │   │   ├── Auth: OAuth tokens (~/.snipara/tokens.json)
    │   │   ├── Auth: SNIPARA_API_KEY env var
    │   │   └── Auth: snipara_api_key in rlm.toml
    │   └── get_native_snipara_tools(client, memory_enabled)
    │       ├── Tier 1: rlm_context_query, rlm_search, rlm_sections, rlm_read
    │       ├── Tier 2: rlm_remember, rlm_recall, rlm_memories, rlm_forget  (if memory_enabled)
    │       └── Tier 3: rlm_shared_context
    │
    └── Attempt 2: snipara-mcp package (backward compat)
        └── from snipara_mcp.rlm_tools import get_snipara_tools
```

### Auth Resolution Order

Credentials are resolved top-down; the first match wins:

| Priority | Source | Header | Notes |
|----------|--------|--------|-------|
| 1 | OAuth tokens (`~/.snipara/tokens.json`) | `Authorization: Bearer <token>` | Via `snipara-mcp-login` browser flow |
| 2 | `SNIPARA_API_KEY` env var | `x-api-key: <key>` | For open-source / non-Snipara users |
| 3 | `snipara_api_key` in `rlm.toml` | `x-api-key: <key>` | Static config fallback |
| 4 | `snipara-mcp` package import | (package handles auth) | Backward compat only |

If none of the above are available, Snipara tools are silently skipped.

### Setup

```bash
# Option A: OAuth (recommended — no API key copying)
pip install rlm-runtime[mcp]
snipara-mcp-login      # Opens browser, stores tokens
snipara-mcp-status     # Verify auth status

# Option B: API key (open-source users)
export SNIPARA_API_KEY="rlm_your_key_here"
export SNIPARA_PROJECT_SLUG="your-project-slug"

# Option C: snipara-mcp package (backward compat)
pip install rlm-runtime[mcp] snipara-mcp
```

Tokens stored at `~/.snipara/tokens.json`.

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `SNIPARA_API_KEY` | Raw API key for authentication | None |
| `SNIPARA_PROJECT_SLUG` | Project slug for API URL | None |
| `RLM_SNIPARA_BASE_URL` | Override API base URL | `https://api.snipara.com/mcp` |
| `RLM_MEMORY_ENABLED` | Enable Tier 2 memory tools | `false` |

### Native Snipara Tools Reference

**Tier 1 — Context Retrieval** (always registered):

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `rlm_context_query` | Semantic/keyword/hybrid doc search | `query`, `max_tokens=4000`, `search_mode=hybrid` |
| `rlm_search` | Regex pattern search across docs | `pattern`, `max_results=20` |
| `rlm_sections` | List indexed doc sections | `filter`, `limit=50`, `offset=0` |
| `rlm_read` | Read specific lines from docs | `start_line`, `end_line` |

**Tier 2 — Memory** (gated by `memory_enabled`):

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `rlm_remember` | Store a memory for later recall | `content`, `type=fact`, `scope=project`, `ttl_days` |
| `rlm_recall` | Semantic recall by query | `query`, `limit=5`, `min_relevance=0.5` |
| `rlm_memories` | List memories with filters | `type`, `scope`, `category`, `search` |
| `rlm_forget` | Delete memories | `memory_id`, `type`, `category`, `older_than_days` |

**Tier 3 — Advanced** (always registered):

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `rlm_shared_context` | Merged team docs with budget allocation | `categories[]`, `max_tokens=4000`, `include_content=true` |

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

### This Project's Snipara Configuration

For rlm-runtime development, Snipara is configured via:
- **Auth**: OAuth tokens at `~/.snipara/tokens.json` (via `snipara-mcp-login`)
- **Project slug**: Resolved automatically from OAuth token metadata
- **Tools**: Native HTTP client (`src/rlm/tools/snipara.py`) — no `snipara-mcp` package needed

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
| Modify agent behavior | `src/rlm/agent/runner.py` |
| Change agent prompts | `src/rlm/agent/prompts.py` |
| Modify sub-LLM tools | `src/rlm/tools/sub_llm.py` |
| Modify Snipara tools | `src/rlm/tools/snipara.py` |
| Snipara OAuth auth | `src/rlm/mcp/auth.py` |
| Change agent limits | `src/rlm/agent/config.py`, `src/rlm/agent/guardrails.py` |
| Add terminal protocol | `src/rlm/agent/terminal.py` |

## Future Features (Not Yet Implemented)

### Visualization Tool for Non-Developers

**Status:** Proposed, not implemented

**Rationale:** The REPL is intentionally limited to pure computation. For non-technical users who need Claude to generate and display visualizations, a separate tool could be useful.

#### Proposed Design

```
MCP Tools (current + proposed)
├── execute_python           # Pure computation (restricted sandbox)
├── get/set/clear_repl_context
└── generate_visualization   # PROPOSED - creates files, returns path
```

#### Proposed Tool: `generate_visualization`

```python
# Example usage by Claude:
generate_visualization(
    code="""
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
plt.plot([1, 2, 3, 4], [1, 4, 9, 16])
plt.title('Sample Chart')
plt.savefig(OUTPUT_PATH)  # Magic variable injected by tool
""",
    format="png",        # png, svg, pdf, html
    filename="chart",    # optional custom name
    auto_open=True,      # open in default viewer
)

# Returns:
# {"path": "~/.rlm/visualizations/chart_20240124_143052.png", "opened": true}
```

#### Comparison with REPL

| Aspect | `execute_python` | `generate_visualization` |
|--------|------------------|--------------------------|
| **Purpose** | Computation | Visual output |
| **Imports** | Restricted whitelist | matplotlib, PIL, plotly, seaborn |
| **File I/O** | Blocked | Writes to controlled output dir only |
| **Network** | Blocked | Blocked |
| **Output** | Text (stdout) | File path |
| **Auto-open** | N/A | Optional (opens in default viewer) |

#### When This Tool Adds Value

| Scenario | Benefit |
|----------|---------|
| **Claude-driven iteration** | Claude generates chart → user says "make it blue" → Claude regenerates |
| **Data flows from REPL** | Compute in `execute_python`, visualize result without copy/paste |
| **Non-technical users** | Don't need local Python/Jupyter setup |
| **Reproducible workflow** | Same tool, same output location, logged |

#### When Local Execution is Better

| Scenario | Why |
|----------|-----|
| **Complex visualizations** | Need full library access, debugging |
| **Interactive exploration** | Jupyter notebooks are superior |
| **One-off charts** | Faster to just run a script |
| **Custom dependencies** | Any package, any version |

#### Implementation Notes (If Built)

**Files to create:**
- `src/rlm/repl/visualization.py` - Visualization executor
- Update `src/rlm/mcp/server.py` - Add new tool

**Security model:**
- Writes only to controlled directory (`~/.rlm/visualizations/` or configurable)
- No arbitrary file paths allowed
- Network still blocked
- Timeout enforced
- Allowed libraries: matplotlib, plotly, seaborn, PIL (curated list)

**Dependencies:**
```toml
[project.optional-dependencies]
visualization = ["matplotlib", "plotly", "seaborn", "pillow"]
```

**Decision:** Not implementing now. For developers, local Python/Jupyter is better. Only build if targeting non-developer users who need Claude to create visualizations.

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
| 2.0.0 | Jan 2025 | Major release: persistent sessions, execution profiles, path security, caching |
| 0.2.0 | Jan 2025 | Cost tracking, budget enforcement, resource monitoring |
| 0.1.x | Dec 2024 | Initial release with MCP server |

## Advanced LLM Features (Phase 7)

### Parallel Tool Execution

Execute multiple tool calls concurrently when the LLM returns several in one response:

```python
options = CompletionOptions(
    parallel_tools=True,   # Enable parallel execution
    max_parallel=5,        # Concurrent tool limit (semaphore)
)
```

Implementation: When `parallel_tools=True` and `len(tool_calls) > 1`, the orchestrator uses `asyncio.gather()` with `asyncio.Semaphore(max_parallel)` and `return_exceptions=True`. Sequential behavior is preserved when the flag is off.

### Structured Outputs

JSON schema-constrained LLM responses:

```python
options = CompletionOptions(
    response_format={
        "type": "json_schema",
        "json_schema": {"name": "result", "schema": {"type": "object", ...}}
    }
)
result = await rlm.completion("Extract entities", options=options)
# result.parsed_output contains the parsed JSON dict
```

The `response_format` is passed through to LiteLLM's `acompletion()`. The response content is parsed as JSON into `BackendResponse.parsed_output`.

### Multi-Modal Input

Messages support images/audio via list-based content:

```python
from rlm.core.types import Message

# Text-only (string)
msg = Message(role="user", content="Hello")

# Multi-modal (list of content blocks)
msg = Message(role="user", content=[
    {"type": "text", "text": "What's in this image?"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
])

# text_content property extracts text regardless of format
msg.text_content  # "What's in this image?"
```

### Agent Memory (via Snipara)

Persistent context across sessions using Snipara's existing memory tools. Gated by `memory_enabled` config:

```python
# In config
config.memory_enabled = True  # Register rlm_remember and rlm_recall tools
```

When enabled, the LLM can use:
- `rlm_remember` -- Store memories with type (fact/decision/learning/preference/todo/context), scope, category, TTL
- `rlm_recall` -- Semantic recall by query with relevance scoring

## Sub-LLM Orchestration (Phase 8)

The model can delegate focused sub-problems to fresh LLM calls with their own context and budget.

**Tools**: `rlm_sub_complete` (single sub-call) and `rlm_batch_complete` (parallel sub-calls)

**Budget inheritance**: Sub-calls get `min(requested, remaining * 0.5)` of the parent's remaining budget.

**Configuration**:
```toml
[rlm]
sub_calls_enabled = true
sub_calls_max_per_turn = 5
sub_calls_budget_inheritance = 0.5
sub_calls_max_cost_per_session = 1.0
```

**CLI flags**: `--sub-calls/--no-sub-calls`, `--max-sub-calls`

See [docs/sub-llm-orchestration.md](docs/sub-llm-orchestration.md) for full specification.

## Autonomous Agent (Phase 9)

Full agent loop: observe → think → act → terminate. The model uses REPL for code execution, Snipara for context/memory, and sub-LLM calls for delegation.

### Quick Start

```python
from rlm.agent import AgentRunner, AgentConfig
from rlm.core.orchestrator import RLM

rlm = RLM(model="gpt-4o-mini")
runner = AgentRunner(rlm, AgentConfig(max_iterations=10, cost_limit=2.0))
result = await runner.run("What is 2+2?")
print(result.answer)  # "4"
```

### CLI

```bash
rlm agent "What is 2+2?"
rlm agent "Explain auth system" --model claude-sonnet-4-20250514 --max-iterations 20 --verbose
rlm agent "Count files" --json
```

### MCP Tools

- `rlm_agent_run(task, max_iterations, token_budget, cost_limit)` -- Start async agent
- `rlm_agent_status(run_id)` -- Check status or get result
- `rlm_agent_cancel(run_id)` -- Cancel running agent

### Termination Protocol

- `FINAL(answer="...")` -- Return natural language answer
- `FINAL_VAR(variable_name="result")` -- Return computed REPL variable

### Hard Safety Limits

| Limit | Value |
|-------|-------|
| Max iterations | 50 |
| Max cost | $10.00 |
| Max timeout | 600s |
| Max depth | 5 |

### Key Files

| File | Purpose |
|------|---------|
| `src/rlm/agent/runner.py` | Main agent loop |
| `src/rlm/agent/config.py` | Config with hard limit clamping |
| `src/rlm/agent/terminal.py` | FINAL/FINAL_VAR tools |
| `src/rlm/agent/prompts.py` | System and iteration prompts |
| `src/rlm/agent/guardrails.py` | Budget/iteration/cost checks |
| `src/rlm/agent/result.py` | AgentResult dataclass |
| `src/rlm/tools/sub_llm.py` | Sub-LLM orchestration tools |

See [docs/autonomous-agent.md](docs/autonomous-agent.md) for full specification.

## Recent Changes

### January 2025 (v2.0.0)

- **Path Traversal Security**: File tools now validate paths against `allowed_paths` config to prevent unauthorized file access
- **Streaming Cost Tracking**: `stream()` method now accepts `StreamOptions` with cost budget enforcement
- **Persistent REPL Sessions**: MCP server supports multiple named sessions with `session_id` parameter and TTL-based cleanup
- **Enhanced Error Context**: LocalREPL provides line numbers, variable state, and suggestions for blocked imports
- **Execution Profiles**: New `profile` parameter (quick/default/analysis/extended) for preset timeout/memory limits
- **Result Caching**: LocalREPL caches execution results by code+context hash with LRU eviction
- **WASM Package Installation**: `install_package()` now uses micropip for pure-Python packages
- **Timeout Enforcement**: `TimeoutExceeded` exception now raised when `timeout_seconds` is exceeded
- **New MCP Tools**: `list_sessions`, `destroy_session` for session management

### December 2024 (v0.2.0)

- **Cost Tracking**: New pricing.py module with model pricing data for OpenAI, Anthropic, Google, and Mistral models. RLMResult now includes `total_cost_usd`, `total_input_tokens`, `total_output_tokens`.
- **Budget Enforcement**: Token budget is now enforced (was a bug - configured but never checked). New `cost_budget_usd` option for cost-based limits.
- **Resource Tracking**: LocalREPL tracks CPU time and peak memory via `cpu_time_ms` and `memory_peak_bytes` in REPLResult.
- **New Exceptions**: Added `CostBudgetExhausted` and `REPLResourceExceeded` exceptions.
- **MCP Server Refactor**: Simplified to code sandbox only (no LLM calls)
- **OAuth Support**: Added auth.py for Snipara token integration
- **WebAssembly REPL**: New wasm.py for Pyodide execution
- **Exception Hierarchy**: Comprehensive error handling in exceptions.py
- **Trajectory Visualizer**: Streamlit dashboard for debugging

---

## BMad Method (Global Commands)

BMad Method is available globally across all Claude Code sessions. Use these slash commands for structured workflows.

### Quick Start
```
/bmad/core/agents/bmad-master    # Main BMad agent - start here
/bmad-help                        # Get guidance on what to do next
```

### Core Workflows
| Command | Purpose |
|---------|---------|
| `/bmad/bmm/workflows/prd` | Create Product Requirements Document |
| `/bmad/bmm/workflows/create-architecture` | Design system architecture |
| `/bmad/bmm/workflows/create-story` | Create user stories |
| `/bmad/bmm/workflows/create-epics-and-stories` | Full epic breakdown |
| `/bmad/bmm/workflows/dev-story` | Develop/implement a story |
| `/bmad/bmm/workflows/quick-dev` | Quick development flow |
| `/bmad/bmm/workflows/sprint-planning` | Sprint planning session |

### Planning & Design
| Command | Purpose |
|---------|---------|
| `/bmad/bmm/workflows/create-product-brief` | Initial product brief |
| `/bmad/bmm/workflows/check-implementation-readiness` | Verify before coding |
| `/bmad/core/workflows/brainstorming` | Brainstorming session |

### Documentation & Diagrams
| Command | Purpose |
|---------|---------|
| `/bmad/bmm/workflows/document-project` | Generate project docs |
| `/bmad/bmm/workflows/create-excalidraw-diagram` | Create diagrams |
| `/bmad/bmm/workflows/create-excalidraw-flowchart` | Create flowcharts |
| `/bmad/bmm/workflows/create-excalidraw-wireframe` | Create wireframes |
| `/bmad/bmm/workflows/create-excalidraw-dataflow` | Create data flow diagrams |

### Installation
BMad is installed globally at `~/bmad-global/` and symlinked to `~/.claude/commands/bmad/`.
