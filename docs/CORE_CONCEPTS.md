# Core Concepts and Glossary

This document defines the core concepts and terminology used in RLM Runtime. Understanding these concepts is essential for effectively using and extending the framework.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Glossary](#glossary)
- [Architecture Terms](#architecture-terms)
- [Execution Terms](#execution-terms)
- [Tool System Terms](#tool-system-terms)

---

## Core Concepts

### RLM (Recursive Language Model)

RLM stands for Recursive Language Model. Unlike traditional LLM usage where a single prompt-response cycle is used, RLM enables LLMs to:

- **Decompose** complex tasks into smaller sub-tasks
- **Execute** real code in sandboxed environments
- **Iterate** on results with multiple recursive calls
- **Aggregate** findings into coherent responses

The "recursive" aspect means the LLM can make tool calls, receive results, and make additional calls based on those results—all within a single completion request, up to a configured depth limit.

### Orchestration

Orchestration refers to the coordination of LLM calls, tool executions, and result aggregation. The RLM Orchestrator manages:

- **Recursion depth** - Maximum number of nested calls
- **Token budgets** - Token limits per completion
- **Tool dispatch** - Routing calls to appropriate handlers
- **Trajectory logging** - Recording execution traces

### Trajectory

A trajectory is the complete record of an RLM execution, including:

- All prompts and responses
- Tool calls and results
- Timing and token usage
- Recursion structure

Trajectories are logged in JSONL format for debugging and analysis.

### Context Optimization

Context optimization (via Snipara) is the process of intelligently selecting and compressing documentation relevant to a query. Instead of sending entire files to the LLM:

1. **Query analysis** - Understand what information is needed
2. **Semantic search** - Find relevant sections using embeddings
3. **Ranking** - Prioritize most relevant content
4. **Compression** - Summarize or truncate to fit token budgets

---

## Glossary

### Agent

An autonomous entity that can plan, execute, and learn. In RLM, agents use the `Agent` class to run iterative task completion with guardrails and learning capabilities.

### Backend

The LLM provider abstraction. RLM supports multiple backends:

- **LiteLLM** - Default backend supporting 100+ providers
- **OpenAI** - Direct OpenAI API access
- **Anthropic** - Direct Anthropic API access

### Completion

A completion is a single LLM response generation. RLM completions can include tool calls, which trigger recursive execution.

### Context

Context refers to the information available to the LLM when generating a response, including:

- **System prompt** - Fixed instructions
- **Conversation history** - Previous messages
- **Tool results** - Output from tool executions
- **Retrieved documentation** - Context from Snipara

### Execution Profile

A predefined set of resource limits for REPL execution:

| Profile | Timeout | Memory | Use Case |
|---------|---------|--------|----------|
| `quick` | 5s | 128m | Simple math, string ops |
| `default` | 30s | 512m | Standard data processing |
| `analysis` | 120s | 2g | Heavy computation |
| `extended` | 300s | 4g | Batch processing |

### Memory (Snipara)

Snipara's memory system allows LLMs to store and recall information across sessions:

- **rlm_remember** - Store a memory
- **rlm_recall** - Retrieve memories semantically
- **rlm_memories** - List stored memories
- **rlm_forget** - Delete memories

Memory types: `fact`, `decision`, `learning`, `preference`, `todo`, `context`
Memory scopes: `agent`, `project`, `team`, `user`

### MCP (Model Context Protocol)

MCP is a protocol for providing tools to LLMs. RLM includes an MCP server that exposes sandboxed Python execution to Claude Desktop/Code.

### REPL

Read-Eval-Print Loop. RLM provides multiple REPL environments:

- **Local** - RestrictedPython sandbox
- **Docker** - Full container isolation
- **WebAssembly** - Pyodide-based sandbox

### Sandbox

A sandbox is an isolated execution environment that restricts what code can do. RLM sandboxes prevent:

- Network access (except Docker)
- File system access (configurable)
- Importing dangerous modules
- Infinite loops (via timeouts)

### Sub-LLM Call

A sub-LLM call is when the LLM spawns another LLM to handle a subtask. This enables:

- Parallel task processing
- Specialized expertise per subtask
- Cost tracking per sub-task

### Tool

A tool is a function the LLM can call to perform actions. Tools follow the OpenAI function calling format and are registered in the Tool Registry.

### Tool Budget

The maximum number of tool calls allowed in a single completion. Prevents runaway recursion.

### Token Budget

The maximum number of tokens allowed in a completion. Includes prompt and response tokens.

---

## Architecture Terms

### Orchestrator

The central component that coordinates LLM execution. Located in `src/rlm/core/orchestrator.py`, it manages:

- Message construction
- Tool dispatch
- Budget enforcement
- Trajectory logging

### Tool Registry

A registry that maintains available tools and their handlers. Located in `src/rlm/tools/registry.py`.

### Backend Adapter

An adapter that standardizes access to different LLM providers. Located in `src/rlm/backends/`.

### REPL Environment

An execution environment for code. Implementations:
- `src/rlm/repl/local.py` - RestrictedPython
- `src/rlm/repl/docker.py` - Docker containers
- `src/rlm/repl/wasm.py` - WebAssembly (Pyodide)

---

## Execution Terms

### Depth

The recursion depth indicates how many levels deep the execution has gone. A depth of 0 means the initial call, depth 1 means a tool call within that, etc.

### Parallel Execution

When `parallel_tools=True`, multiple tool calls can execute simultaneously. Limited by `max_parallel`.

### Streaming

Streaming allows receiving tokens as they're generated, rather than waiting for the complete response. Only available for simple completions without tool calls.

### Timeout

The maximum time (in seconds) allowed for execution. Applies to:
- Individual tool calls
- Overall completion request

---

## Tool System Terms

### Builtin Tools

Tools that are always available:

| Tool | Description |
|------|-------------|
| `execute_code` | Execute Python in REPL |
| `list_files` | List directory contents |
| `read_file` | Read file contents |
| `write_file` | Write file contents |
| `search_files` | Search files with regex |

### Context Retrieval Tools (Snipara Tier 1)

Tools for retrieving documentation:

| Tool | Description |
|------|-------------|
| `rlm_context_query` | Semantic/keyword/hybrid search |
| `rlm_search` | Regex pattern search |
| `rlm_sections` | List indexed sections |
| `rlm_read` | Read specific lines |

### Memory Tools (Snipara Tier 2)

Tools for persistent memory (requires `memory_enabled=True`):

| Tool | Description |
|------|-------------|
| `rlm_remember` | Store a memory |
| `rlm_recall` | Recall memories semantically |
| `rlm_memories` | List stored memories |
| `rlm_forget` | Delete memories |

### Advanced Tools (Snipara Tier 3)

Tools for team context:

| Tool | Description |
|------|-------------|
| `rlm_shared_context` | Get merged team documentation |

---

## Error Types

### Budget Errors

Errors related to resource limits:

- `MaxDepthExceeded` - Recursion limit hit
- `TokenBudgetExhausted` - Token limit hit
- `CostBudgetExhausted` - Cost budget hit
- `ToolBudgetExhausted` - Tool call limit hit

### REPL Errors

Errors from code execution:

- `REPLExecutionError` - Code failed
- `REPLTimeoutError` - Execution timed out
- `REPLImportError` - Blocked import
- `REPLSecurityError` - Security violation

### Tool Errors

Errors from tool execution:

- `ToolNotFoundError` - Unknown tool
- `ToolExecutionError` - Tool failed
- `ToolValidationError` - Invalid arguments
- `SniparaAPIError` - Snipara API failure

### Backend Errors

Errors from LLM providers:

- `BackendConnectionError` - Connection failed
- `BackendRateLimitError` - Rate limited
- `BackendAuthError` - Authentication failed

---

## Configuration Terms

### Config File (rlm.toml)

A TOML configuration file that stores RLM settings. Located in the project root or specified via CLI.

### Environment Variables

Configuration can also be set via environment variables with the `RLM_` prefix (e.g., `RLM_MODEL`, `RLM_MAX_DEPTH`).

### Execution Profile

Named configurations for resource limits. See [Execution Profile](#execution-profile) above.
