# RLM Runtime

**Recursive Language Model runtime with sandboxed REPL execution.**

RLM Runtime enables LLMs to recursively decompose tasks, execute real code in isolated environments, and retrieve context on demand. Instead of simulating computation in tokens, the model executes actual code—cheaper, more reliable, and auditable.

## Features

- **Recursive Completion** - LLMs can spawn sub-calls, execute code, and aggregate results
- **Sandboxed REPL** - Local (RestrictedPython) or Docker isolation
- **Multi-Provider** - OpenAI, Anthropic, and 100+ providers via LiteLLM
- **Streaming** - Real-time token streaming for simple completions
- **Trajectory Logging** - Full execution traces in JSONL format
- **Trajectory Visualizer** - Interactive Streamlit dashboard for debugging
- **MCP Server** - Claude Desktop/Code integration with multi-project support
- **Plugin System** - Extend with custom tools
- **Snipara Integration** - Optional context optimization (recommended)

## Installation

```bash
# Basic install
pip install rlm-runtime

# With Docker support (recommended)
pip install rlm-runtime[docker]

# With MCP server (for Claude Desktop/Code)
pip install rlm-runtime[mcp]

# With Snipara context optimization
pip install rlm-runtime[snipara]

# Full install
pip install rlm-runtime[all]
```

## Claude Desktop / Claude Code Integration

RLM Runtime includes an MCP server that exposes sandboxed Python execution to Claude.

### Setup

1. Install with MCP support:
   ```bash
   pip install rlm-runtime[mcp]
   ```

2. Add to your Claude configuration:

   **Claude Desktop** (`~/.claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "rlm": {
         "command": "rlm",
         "args": ["mcp-serve"]
       }
     }
   }
   ```

   **Claude Code** (`~/.claude/claude_code_config.json`):
   ```json
   {
     "mcpServers": {
       "rlm": {
         "command": "rlm",
         "args": ["mcp-serve"]
       }
     }
   }
   ```

3. Restart Claude Desktop or reload Claude Code.

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `execute_python` | Run Python code in a sandboxed environment |
| `run_completion` | Execute a recursive LLM completion |
| `set_project` | Switch to a different project (auto-loads config) |
| `get_project` | View current project configuration |
| `get_repl_context` | Get current REPL context variables |
| `set_repl_context` | Set a variable in REPL context |
| `clear_repl_context` | Clear all REPL context |

### Multi-Project Support

The MCP server supports working across multiple projects with different configurations:

```
~/projects/
├── frontend/
│   └── rlm.toml          # Frontend config (claude-sonnet, docker)
├── backend/
│   └── rlm.toml          # Backend config (gpt-4o, local)
└── data-pipeline/
    └── rlm.toml          # Data config (gpt-4o-mini)
```

Switch projects in Claude:
```
User: Switch to the backend project
Claude: [set_project directory="~/projects/backend"]
```

See [MCP Integration Guide](docs/mcp-integration.md) for details.

### Example Usage in Claude

Once configured, Claude can use these tools:

```
User: Calculate the fibonacci sequence up to n=20

Claude: I'll use the execute_python tool to calculate this.

[execute_python]
def fib(n):
    a, b = 0, 1
    result = []
    while a <= n:
        result.append(a)
        a, b = b, a + b
    return result

result = fib(20)
print(result)

Output: [0, 1, 1, 2, 3, 5, 8, 13]
```

## Quick Start

### CLI

```bash
# Initialize config
rlm init

# Run a completion
rlm run "Count the lines in data.csv and show the top 5 rows"

# Run with Docker isolation
rlm run --env docker "Parse the JSON files and extract all emails"

# Verbose mode (shows trajectory)
rlm run -v "Explain the authentication flow in this codebase"
```

### Python API

```python
import asyncio
from rlm import RLM

async def main():
    # Basic usage
    rlm = RLM(model="gpt-4o-mini", environment="local")

    result = await rlm.completion("Analyze data.csv and find outliers")
    print(result.response)
    print(f"Calls: {result.total_calls}, Tokens: {result.total_tokens}")

asyncio.run(main())
```

### With Snipara Context Optimization

```python
from rlm import RLM

rlm = RLM(
    model="gpt-4o-mini",
    environment="docker",
    snipara_api_key="rlm_...",
    snipara_project_slug="my-project",
)

# Snipara tools auto-registered: context_query, sections, search, etc.
result = await rlm.completion("Explain how authentication works in this project")
```

## Configuration

Create `rlm.toml` in your project:

```toml
[rlm]
backend = "litellm"
model = "gpt-4o-mini"
environment = "docker"  # "local" or "docker"
max_depth = 4
max_subcalls = 12
token_budget = 8000
verbose = false

# Docker settings
docker_image = "python:3.11-slim"
docker_cpus = 1.0
docker_memory = "512m"

# Snipara (optional but recommended)
snipara_api_key = "rlm_..."
snipara_project_slug = "your-project"
```

Or use environment variables:

```bash
export RLM_MODEL=gpt-4o-mini
export RLM_ENVIRONMENT=docker
export SNIPARA_API_KEY=rlm_...
export SNIPARA_PROJECT_SLUG=my-project
```

## Environments

### Local REPL

- Fastest iteration
- Uses RestrictedPython for sandboxing
- Limited isolation (no network/filesystem by default)
- Best for trusted inputs in development

### Docker REPL

- Strong isolation in containers
- Configurable resource limits (CPU, memory)
- Network disabled by default
- **Recommended for production and untrusted inputs**

```bash
# Start with Docker
rlm run --env docker "Process untrusted user input..."
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  RLM Orchestrator                                               │
│  • Manages recursion depth and token budgets                    │
│  • Coordinates LLM calls and tool execution                     │
├─────────────────────────────────────────────────────────────────┤
│  LLM Backends              │  REPL Environments                 │
│  • LiteLLM (default)       │  • Local (RestrictedPython)        │
│  • OpenAI                  │  • Docker (isolated)               │
│  • Anthropic               │                                    │
├─────────────────────────────────────────────────────────────────┤
│  Tool Registry                                                  │
│  • Builtin: file_read, execute_code                            │
│  • Snipara: context_query, sections, search (optional)         │
│  • Custom: your own tools                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Custom Tools

```python
from rlm import RLM
from rlm.tools import Tool

async def fetch_weather(city: str) -> dict:
    # Your implementation
    return {"city": city, "temp": 72}

weather_tool = Tool(
    name="get_weather",
    description="Get current weather for a city",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"}
        },
        "required": ["city"]
    },
    handler=fetch_weather,
)

rlm = RLM(tools=[weather_tool])
```

## Trajectory Logging

All completions emit JSONL trajectory logs:

```bash
# View recent logs
rlm logs

# View specific trajectory
rlm logs abc123-def456

# Logs location
ls ./logs/
```

Each event includes:
- `trajectory_id` - Unique ID for the request
- `call_id` - ID for this specific call
- `parent_call_id` - Parent call (for recursion)
- `depth` - Recursion depth
- `prompt`, `response` - Input/output
- `tool_calls`, `tool_results` - Tool usage
- `token_usage`, `duration_ms` - Metrics

## Trajectory Visualizer

Debug and analyze execution trajectories with the interactive web UI:

```bash
# Install visualizer dependencies
pip install rlm-runtime[visualizer]

# Launch the dashboard
rlm visualize

# Custom log directory and port
rlm visualize --dir ./logs --port 8502
```

The visualizer provides:
- **Execution Tree** - Visual graph of recursive calls
- **Token Charts** - Input/output token usage per call
- **Duration Analysis** - Timing breakdown across calls
- **Tool Distribution** - Pie chart of tool call frequency
- **Event Inspector** - Detailed view of each call with prompts/responses

## API Reference

### RLM Class

```python
from rlm import RLM

rlm = RLM(
    # Required
    model="gpt-4o-mini",           # LLM model identifier

    # Backend
    backend="litellm",             # "litellm", "openai", or "anthropic"
    api_key=None,                  # Provider API key (or use env vars)

    # Execution Environment
    environment="local",           # "local" or "docker"

    # Recursion Limits
    max_depth=4,                   # Max recursive depth
    max_subcalls=12,               # Max total tool calls
    token_budget=8000,             # Token limit per completion

    # Docker Settings (when environment="docker")
    docker_image="python:3.11-slim",
    docker_cpus=1.0,
    docker_memory="512m",
    docker_network_disabled=True,

    # Tools
    tools=None,                    # List of custom Tool objects

    # Snipara Integration
    snipara_api_key=None,          # Snipara API key
    snipara_project_slug=None,     # Snipara project slug
    snipara_api_url=None,          # Custom API URL

    # Logging
    verbose=False,                 # Print execution details
    log_dir="./logs",              # Trajectory log directory
)
```

### CompletionResult

```python
result = await rlm.completion("Your prompt")

result.response          # Final LLM response text
result.trajectory_id     # Unique ID for this execution
result.total_calls       # Total LLM calls made
result.total_tokens      # Total tokens used
result.depth_reached     # Max recursion depth reached
result.tool_calls        # List of tool calls made
result.duration_ms       # Total execution time
```

### Tool Class

```python
from rlm.backends.base import Tool

tool = Tool(
    name="tool_name",              # Unique tool identifier
    description="What the tool does",
    parameters={                   # JSON Schema for parameters
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
        },
        "required": ["param1"]
    },
    handler=async_function,        # Async function to execute
)
```

### Error Handling

```python
from rlm import RLM
from rlm.core.exceptions import (
    RLMError,              # Base exception
    MaxDepthExceeded,      # Recursion limit hit
    TokenBudgetExhausted,  # Token limit hit
    REPLExecutionError,    # Code execution failed
    ToolNotFoundError,     # Unknown tool called
)

try:
    result = await rlm.completion("Complex task...")
except MaxDepthExceeded as e:
    print(f"Hit max depth at {e.depth}")
except TokenBudgetExhausted as e:
    print(f"Used {e.tokens_used} tokens, budget was {e.budget}")
except REPLExecutionError as e:
    print(f"Code failed: {e.stderr}")
```

## Advanced Examples

### Recursive Data Analysis

```python
from rlm import RLM

rlm = RLM(
    model="claude-sonnet-4-20250514",
    environment="docker",
    max_depth=6,
)

# The LLM will recursively:
# 1. List CSV files
# 2. Read and analyze each one
# 3. Aggregate findings
# 4. Generate report
result = await rlm.completion("""
    Analyze all CSV files in ./data/:
    1. Find common columns across files
    2. Calculate summary statistics for numeric columns
    3. Identify any data quality issues
    4. Generate a markdown report
""")
```

### Code Generation with Context

```python
from rlm import RLM

rlm = RLM(
    model="gpt-4o",
    snipara_api_key="rlm_...",
    snipara_project_slug="my-app",
)

# The LLM will:
# 1. Query Snipara for auth patterns
# 2. Execute code to explore existing structure
# 3. Generate new code following conventions
result = await rlm.completion("""
    Add a password reset endpoint:
    - Follow our existing auth patterns
    - Use the same error handling conventions
    - Add tests following our test patterns
""")

# Access the code that was written
print(result.response)
```

### Streaming Output

```python
from rlm import RLM

rlm = RLM(model="gpt-4o-mini")

async for chunk in rlm.stream("Explain quantum computing"):
    print(chunk, end="", flush=True)
```

### Batch Processing

```python
from rlm import RLM
import asyncio

rlm = RLM(model="gpt-4o-mini", environment="docker")

prompts = [
    "Analyze report_q1.csv",
    "Analyze report_q2.csv",
    "Analyze report_q3.csv",
]

# Run in parallel
results = await asyncio.gather(*[
    rlm.completion(p) for p in prompts
])
```

## Why Snipara?

Without Snipara, RLM can only read files directly. With Snipara:

| Feature | Without Snipara | With Snipara |
|---------|-----------------|--------------|
| File reading | Basic read | Semantic search |
| Token usage | All content (500K) | Relevant only (5K) |
| Search | Regex only | Hybrid (keyword + embeddings) |
| Best practices | None | Shared team context |
| Summaries | None | Cached summaries |

Get your API key at [snipara.com/dashboard](https://snipara.com/dashboard)

## Development

```bash
# Clone
git clone https://github.com/alopez3006/rlm-runtime
cd rlm-runtime

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
mypy src/

# Build
python -m build
```

## License

Apache 2.0 - See [LICENSE](LICENSE)

## Documentation

- [Quickstart Guide](docs/quickstart.md) - Get started in 5 minutes
- [Architecture Guide](docs/architecture.md) - System design and components
- [MCP Integration](docs/mcp-integration.md) - Claude Desktop/Code setup
- [Configuration](docs/configuration.md) - All configuration options
- [Tool Development](docs/tools.md) - Building custom tools

## Links

- [Snipara](https://snipara.com) - Context optimization service
- [GitHub Issues](https://github.com/alopez3006/rlm-runtime/issues)
