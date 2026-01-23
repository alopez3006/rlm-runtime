# CLAUDE.md - RLM Runtime

This document helps Claude Code understand the rlm-runtime project.

## Project Overview

RLM Runtime is a **Recursive Language Model runtime** with sandboxed REPL execution. It enables LLMs to recursively decompose tasks, execute real code in isolated environments, and retrieve context on demand.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  RLM Orchestrator                                               │
│  • Manages recursion depth and token budgets                    │
│  • Coordinates LLM calls and tool execution                     │
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
│   └── exceptions.py        # Custom exception hierarchy
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
    ToolBudgetExhausted,   # Tool call limit hit
    REPLExecutionError,    # Code execution failed
    REPLSecurityError,     # Security violation
    ToolNotFoundError,     # Unknown tool
    BackendConnectionError, # LLM API error
)
```

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

## Recent Changes

- **MCP Server Refactor**: Simplified to code sandbox only (no LLM calls)
- **OAuth Support**: Added auth.py for Snipara token integration
- **WebAssembly REPL**: New wasm.py for Pyodide execution
- **Exception Hierarchy**: Comprehensive error handling in exceptions.py
- **Trajectory Visualizer**: Streamlit dashboard for debugging
