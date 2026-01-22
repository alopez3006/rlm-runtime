# RLM Runtime Architecture

## Overview

RLM Runtime is a local-first execution environment for Recursive Language Models. It enables LLMs to:

1. **Decompose** complex tasks into sub-queries
2. **Execute** real code in sandboxed environments
3. **Retrieve** context on demand (via plugins like Snipara)
4. **Aggregate** results into coherent responses

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  User Application                                                           │
│  ├── CLI (rlm run, rlm logs, etc.)                                         │
│  ├── Python API (from rlm import RLM)                                      │
│  └── MCP Server (Claude Desktop/Code integration)                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  RLM Orchestrator                                                           │
│  ├── Manages recursion depth and token budgets                              │
│  ├── Coordinates LLM calls and tool execution                               │
│  └── Logs trajectories for debugging                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  LLM Backends                   │  REPL Environments                        │
│  ┌─────────────────────────┐    │  ┌─────────────────────────┐              │
│  │  LiteLLM (default)      │    │  │  Local REPL             │              │
│  │  - OpenAI               │    │  │  - RestrictedPython     │              │
│  │  - Anthropic            │    │  │  - Fast iteration       │              │
│  │  - 100+ providers       │    │  │  - Limited isolation    │              │
│  └─────────────────────────┘    │  └─────────────────────────┘              │
│                                 │  ┌─────────────────────────┐              │
│                                 │  │  Docker REPL            │              │
│                                 │  │  - Full isolation       │              │
│                                 │  │  - Resource limits      │              │
│                                 │  │  - Network disabled     │              │
│                                 │  └─────────────────────────┘              │
│                                 │  ┌─────────────────────────┐              │
│                                 │  │  WebAssembly REPL       │              │
│                                 │  │  - Pyodide sandbox      │              │
│                                 │  │  - No Docker needed     │              │
│                                 │  │  - Portable             │              │
│                                 │  └─────────────────────────┘              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Tool Registry                                                              │
│  ├── Builtin: execute_code, file_read, list_files                          │
│  ├── Snipara: context_query, sections, search (optional plugin)            │
│  └── Custom: user-defined tools                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  MCP Server (optional)                                                      │
│  ├── execute_python: Sandboxed code execution for Claude                   │
│  ├── run_completion: Recursive LLM completion                              │
│  ├── set_project / get_project: Multi-project support                      │
│  └── REPL context management                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### Orchestrator

The `RLM` class is the main entry point. It coordinates:

- **Message management** - Builds and maintains conversation history
- **Tool dispatch** - Routes tool calls to appropriate handlers
- **Recursion control** - Enforces depth and budget limits
- **Logging** - Records trajectories for debugging

```python
from rlm import RLM

rlm = RLM(
    backend="litellm",
    model="gpt-4o-mini",
    environment="docker",
)

result = await rlm.completion("Analyze the logs")
```

### Backends

Backends abstract LLM providers. The default `LiteLLMBackend` supports 100+ providers.

```python
from rlm.backends.litellm import LiteLLMBackend

# Use any LiteLLM-supported model
backend = LiteLLMBackend(model="claude-3-sonnet-20240229")
```

### REPL Environments

Three execution environments are provided:

| Environment | Isolation | Speed | Use Case |
|-------------|-----------|-------|----------|
| **Local** | Limited (RestrictedPython) | Fast | Development, trusted code |
| **Docker** | Full (container) | Slower | Production, untrusted code |
| **WebAssembly** | Full (Pyodide sandbox) | Medium | Browser/serverless, portable |

#### WebAssembly REPL

The WebAssembly environment uses Pyodide to run Python in a sandboxed WebAssembly runtime:

```python
rlm = RLM(environment="wasm")
```

Features:
- **Full isolation** - Runs in WebAssembly sandbox
- **No Docker required** - Works anywhere WebAssembly runs
- **Package installation** - Supports micropip for pure-Python packages
- **Portable** - Same execution across platforms

### Tool System

Tools are functions the LLM can call. They follow the OpenAI function calling format.

```python
from rlm.backends.base import Tool

async def my_tool(param: str) -> dict:
    return {"result": param.upper()}

tool = Tool(
    name="my_tool",
    description="Convert to uppercase",
    parameters={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        },
        "required": ["param"]
    },
    handler=my_tool,
)

rlm = RLM(tools=[tool])
```

## Execution Flow

```
1. User sends prompt
   │
2. Orchestrator builds messages
   │
3. Backend generates completion
   │
   ├── No tool calls → Return response
   │
   └── Has tool calls
       │
       4. Execute each tool
       │
       5. Add results to messages
       │
       6. Recurse (go to step 3)
       │
       └── Until: no tools OR max_depth OR max_subcalls
```

## Safety Model

### Local REPL (RestrictedPython)

- **Import whitelist** - Only safe modules (json, re, math, etc.)
- **Attribute guards** - Controlled attribute access
- **Output limits** - Truncation at 100KB
- **No network** - Network modules blocked

### Docker REPL

- **Process isolation** - Separate container
- **Network disabled** - `--network none` by default
- **Resource limits** - CPU and memory caps
- **Read-only mounts** - Workspace mounted as read-only
- **Non-root user** - Runs as unprivileged user

## Trajectory Logging

Every completion generates a trajectory log (JSONL):

```json
{"_type": "trajectory_metadata", "trajectory_id": "abc-123", "event_count": 3}
{"trajectory_id": "abc-123", "call_id": "...", "depth": 0, "prompt": "...", "response": "..."}
{"trajectory_id": "abc-123", "call_id": "...", "depth": 1, "prompt": "...", "tool_calls": [...]}
```

View with CLI:
```bash
rlm logs              # Recent trajectories
rlm logs abc-123      # Specific trajectory
```

## Streaming

RLM supports streaming completions for real-time output:

```python
async for chunk in rlm.stream("Write a story about a robot"):
    print(chunk, end="", flush=True)
```

Note: Streaming is for simple completions without tool use. For tool-using completions, use the standard `completion()` method.

## Trajectory Visualizer

The trajectory visualizer provides a web-based dashboard for debugging:

```bash
# Launch visualizer
rlm visualize

# Custom port and log directory
rlm visualize --dir ./my-logs --port 8080
```

Features:
- **Execution tree** - Visual representation of recursive calls
- **Token usage** - Charts showing token consumption
- **Tool analysis** - Breakdown of tool calls and timing
- **Event inspector** - Detailed view of each execution step

## Plugin System

### Snipara Integration

When `snipara-mcp` is installed and configured, Snipara tools are auto-registered:

```python
rlm = RLM(
    snipara_api_key="rlm_...",
    snipara_project_slug="my-project",
)
# Tools available: context_query, sections, search, shared_context
```

### Custom Tools

Register custom tools via the constructor or registry:

```python
# Via constructor
rlm = RLM(tools=[my_tool])

# Via registry
rlm.tool_registry.register(my_tool)
```

## MCP Server

The MCP (Model Context Protocol) server enables Claude Desktop and Claude Code to use RLM capabilities.

### Components

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Desktop / Claude Code                               │
└─────────────────────────────────┬───────────────────────────┘
                                  │ stdio (JSON-RPC)
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│  MCP Server (rlm mcp-serve)                                 │
│  ├── ProjectContext: Multi-project config management        │
│  ├── LocalREPL: Persistent sandboxed execution             │
│  └── Tool handlers: execute_python, run_completion, etc.   │
└─────────────────────────────────────────────────────────────┘
```

## Error Handling

RLM uses a comprehensive exception hierarchy for clear error handling:

```
RLMError (base)
├── Budget Errors
│   ├── MaxDepthExceeded
│   ├── TokenBudgetExhausted
│   ├── ToolBudgetExhausted
│   └── TimeoutExceeded
├── REPL Errors
│   ├── REPLExecutionError
│   ├── REPLTimeoutError
│   ├── REPLImportError
│   └── REPLSecurityError
├── Tool Errors
│   ├── ToolNotFoundError
│   ├── ToolExecutionError
│   └── ToolValidationError
├── Backend Errors
│   ├── BackendConnectionError
│   ├── BackendRateLimitError
│   └── BackendAuthError
└── Config Errors
    ├── ConfigNotFoundError
    └── ConfigValidationError
```

All exceptions include context for debugging:

```python
from rlm.core.exceptions import MaxDepthExceeded

try:
    result = await rlm.completion(prompt)
except MaxDepthExceeded as e:
    print(f"Recursion limit: depth={e.depth}, max={e.max_depth}")
```

### Project Context

The `ProjectContext` class manages project-specific configuration:

1. **Auto-detection**: Loads `rlm.toml` from cwd on startup
2. **Manual switching**: `set_project` tool changes active project
3. **Snipara integration**: Routes context queries to correct project

### Available Tools

| Tool | Description |
|------|-------------|
| `execute_python` | Sandboxed Python execution (RestrictedPython) |
| `run_completion` | Recursive LLM completion with tools |
| `set_project` | Switch to different project/config |
| `get_project` | View current project status |
| `get_repl_context` | Get persistent REPL variables |
| `set_repl_context` | Set REPL variables |
| `clear_repl_context` | Reset REPL state |

### Security Model

The MCP server uses the same RestrictedPython sandbox as the Local REPL:

- Import whitelist (json, re, math, datetime, etc.)
- No file I/O, network, or system access
- Output truncation at 100KB
- Execution timeout (default: 30s, max: 60s)

See [MCP Integration Guide](mcp-integration.md) for full documentation.

## Configuration

### Environment Variables

```bash
# Backend
RLM_BACKEND=litellm
RLM_MODEL=gpt-4o-mini
RLM_TEMPERATURE=0.0

# Environment
RLM_ENVIRONMENT=docker
RLM_DOCKER_IMAGE=python:3.11-slim

# Limits
RLM_MAX_DEPTH=4
RLM_TOKEN_BUDGET=8000

# Snipara (optional)
SNIPARA_API_KEY=rlm_...
SNIPARA_PROJECT_SLUG=my-project
```

### Config File (rlm.toml)

```toml
[rlm]
backend = "litellm"
model = "gpt-4o-mini"
environment = "docker"
max_depth = 4
token_budget = 8000
```

## Performance Considerations

1. **Use Docker for production** - Better isolation, predictable resource usage
2. **Set appropriate budgets** - Prevent runaway recursion
3. **Cache when possible** - Snipara caches context queries
4. **Log trajectories** - Debug performance issues with trajectory analysis
