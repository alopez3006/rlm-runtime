# RLM Runtime Quickstart

Get started with RLM Runtime in 5 minutes.

## Installation

```bash
# Basic install
pip install rlm-runtime

# With Docker support (recommended for production)
pip install rlm-runtime[docker]

# With MCP server (for Claude Desktop/Code)
pip install rlm-runtime[mcp]

# With Snipara context optimization
pip install rlm-runtime[snipara]

# With WebAssembly support (no Docker required)
pip install rlm-runtime[wasm]

# With trajectory visualizer
pip install rlm-runtime[visualizer]

# Everything
pip install rlm-runtime[all]
```

## Setup

### 1. Initialize Configuration

```bash
rlm init
```

This creates `rlm.toml` with default settings.

### 2. Set API Keys

```bash
# Set your LLM provider key
export OPENAI_API_KEY=sk-...
# or
export ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Verify Setup

```bash
rlm doctor
```

## Basic Usage

### CLI

```bash
# Simple completion
rlm run "What is 2 + 2?"

# With a specific model
rlm run -m gpt-4o "Explain recursion"

# With Docker isolation
rlm run --env docker "Parse data.csv and count rows"

# Verbose mode (shows execution details)
rlm run -v "Find all Python files in this directory"
```

### Python API

```python
import asyncio
from rlm import RLM

async def main():
    rlm = RLM(model="gpt-4o-mini")

    result = await rlm.completion("What is the capital of France?")
    print(result.response)
    print(f"Tokens used: {result.total_tokens}")

asyncio.run(main())
```

## Code Execution

RLM can execute Python code in a sandboxed environment:

```python
from rlm import RLM

async def main():
    rlm = RLM(environment="local")  # or "docker" for isolation

    result = await rlm.completion(
        "Read data.csv and calculate the average of the 'price' column"
    )
    print(result.response)
```

The LLM will automatically use the `execute_code` tool when needed.

## Adding Snipara

For intelligent context retrieval:

```bash
# Install Snipara plugin
pip install snipara-mcp

# Set credentials
export SNIPARA_API_KEY=rlm_...
export SNIPARA_PROJECT_SLUG=my-project
```

```python
from rlm import RLM

rlm = RLM(
    snipara_api_key="rlm_...",
    snipara_project_slug="my-project",
)

# Now the LLM can query your documentation
result = await rlm.completion("How does authentication work in this project?")
```

## Custom Tools

Add your own tools:

```python
from rlm import RLM, Tool

async def get_weather(city: str) -> dict:
    # Your implementation
    return {"city": city, "temp": 72, "condition": "sunny"}

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
    handler=get_weather,
)

rlm = RLM(tools=[weather_tool])
result = await rlm.completion("What's the weather in Paris?")
```

## Docker Isolation

For untrusted inputs, use Docker:

```bash
# Make sure Docker is running
docker info

# Run with Docker isolation
rlm run --env docker "Process the uploaded file"
```

Or in Python:

```python
rlm = RLM(environment="docker")
```

## WebAssembly Isolation

For environments without Docker, use WebAssembly:

```bash
# Install WebAssembly support
pip install rlm-runtime[wasm]

# Run with WebAssembly isolation
rlm run --env wasm "Process the data"
```

Or in Python:

```python
rlm = RLM(environment="wasm")
```

The WebAssembly environment uses Pyodide to run Python in a sandboxed WebAssembly runtime, providing isolation without requiring Docker.

## Streaming Completions

For real-time output, use streaming:

```python
async def main():
    rlm = RLM(model="gpt-4o-mini")

    async for chunk in rlm.stream("Write a haiku about coding"):
        print(chunk, end="", flush=True)
```

Note: Streaming is for simple completions. Tool-using completions use the standard `completion()` method.

## Viewing Logs

```bash
# List recent trajectories
rlm logs

# View specific trajectory
rlm logs abc123-def456

# JSON output for scripting
rlm logs --json
```

## Trajectory Visualizer

Debug your completions with the web-based visualizer:

```bash
# Install visualizer dependencies
pip install rlm-runtime[visualizer]

# Launch the dashboard
rlm visualize

# Custom port and log directory
rlm visualize --dir ./my-logs --port 8080
```

The visualizer shows:
- Execution tree of recursive calls
- Token usage charts
- Tool call distribution
- Detailed event inspection

## Next Steps

- Read the [Architecture Guide](architecture.md)
- Learn about [Configuration Options](configuration.md)
- Explore [Tool Development](tools.md)
- Set up [Snipara Integration](snipara.md)
