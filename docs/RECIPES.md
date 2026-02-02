# Recipes and Common Tasks

This document provides recipes and examples for common tasks with RLM Runtime.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Data Analysis](#data-analysis)
- [Code Generation](#code-generation)
- [File Operations](#file-operations)
- [Snipara Integration](#snipara-integration)
- [Docker Environments](#docker-environments)
- [Error Handling](#error-handling)
- [Custom Tools](#custom-tools)
- [Agent Tasks](#agent-tasks)
- [Debugging](#debugging)

---

## Basic Usage

### Simple Completion

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(model="gpt-4o-mini")

    result = await rlm.completion("What is 2 + 2?")
    print(result.response)  # "2 + 2 equals 4."

asyncio.run(main())
```

### With System Prompt

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(model="gpt-4o-mini")

    result = await rlm.completion(
        prompt="Solve this math problem",
        system="You are a math tutor. Explain steps clearly.",
    )
    print(result.response)

asyncio.run(main())
```

### Streaming Response

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(model="gpt-4o-mini")

    print("Streaming: ", end="")
    async for chunk in rlm.stream("Write a short poem about code"):
        print(chunk, end="", flush=True)
    print()  # Newline at the end

asyncio.run(main())
```

---

## Data Analysis

### Analyze a CSV File

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        environment="docker",
        max_depth=6,
    )

    result = await rlm.completion("""
        Analyze sales_data.csv:
        1. Load the data
        2. Calculate total revenue
        3. Find top 5 products by sales
        4. Identify any anomalies
        5. Create a summary report
    """)
    print(result.response)

asyncio.run(main())
```

### Process Multiple Files

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        environment="docker",
        max_depth=4,
    )

    result = await rlm.completion("""
        Process all JSON files in ./data/:
        1. List all files
        2. Load and validate each JSON file
        3. Merge them into a single dataset
        4. Report on data quality
    """)
    print(result.response)

asyncio.run(main())
```

### Generate Charts

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o",
        environment="docker",
    )

    result = await rlm.completion("""
        From the database query results in results.csv:
        1. Create a bar chart of monthly sales
        2. Save as sales_chart.png
        3. Include a trend line
    """)
    print(result.response)
    print(f"Charts created in: ./output/")

asyncio.run(main())
```

---

## Code Generation

### Generate a REST API

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o",
        snipara_api_key="rlm_...",
        snipara_project_slug="my-project",
    )

    result = await rlm.completion("""
        Create a REST API for a todo list:
        1. Use FastAPI
        2. Include CRUD endpoints
        3. Add authentication
        4. Write unit tests
        5. Follow our existing code patterns (check docs/)
    """)
    print(result.response)

asyncio.run(main())
```

### Generate with Specific Requirements

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o",
        max_depth=3,
    )

    result = await rlm.completion("""
        Write a Python function that:
        - Takes a list of numbers
        - Filters out even numbers
        - Squares the remaining odd numbers
        - Returns the result sorted in descending order

        Include:
        - Type hints
        - Docstring
        - Unit tests
    """)
    # The LLM will write the code and execute it to verify
    print(result.response)

asyncio.run(main())
```

---

## File Operations

### Read and Modify Files

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        environment="local",
    )

    result = await rlm.completion("""
        In config/settings.py:
        1. Read the current configuration
        2. Change the database port from 5432 to 5433
        3. Add a new setting DEBUG_MODE = True
        4. Save the changes
    """)
    print(result.response)

asyncio.run(main())
```

### Search and Replace

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        environment="local",
    )

    result = await rlm.completion("""
        Find all occurrences of 'print(' in src/:
        1. List files containing print statements
        2. Replace debug print statements with logging calls
        3. Use the logger pattern from src/utils/logger.py
    """)
    print(result.response)

asyncio.run(main())
```

### Create New Module

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o",
        snipara_api_key="rlm_...",
        snipara_project_slug="my-project",
    )

    result = await rlm.completion("""
        Create src/services/email_service.py:
        1. Follow the pattern in src/services/base.py
        2. Implement send_email() method
        3. Add error handling
        4. Include unit tests in tests/test_email.py
        5. Update src/services/__init__.py
    """)
    print(result.response)

asyncio.run(main())
```

---

## Snipara Integration

### Query Documentation

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        snipara_api_key="rlm_...",
        snipara_project_slug="my-project",
    )

    result = await rlm.completion("""
        How do we handle authentication in this codebase?
        Use the documentation to find:
        - Auth flow diagram
        - Code examples
        - Security considerations
    """)
    # The LLM will automatically use rlm_context_query
    print(result.response)

asyncio.run(main())
```

### With Memory

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        snipara_api_key="rlm_...",
        snipara_project_slug="my-project",
        memory_enabled=True,  # Enable memory tools
    )

    # Session 1: Store a decision
    await rlm.completion(
        "We decided to use PostgreSQL as our primary database."
    )

    # Session 2: Recall the decision
    result = await rlm.completion(
        "What database are we using for this project?"
    )
    # The LLM will recall the stored memory
    print(result.response)

asyncio.run(main())
```

### Team Context

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        snipara_api_key="rlm_...",
        snipara_project_slug="my-project",
    )

    result = await rlm.completion("""
        What are the team's coding standards for error handling?
        Check the shared context for:
        - Best practices
        - Mandatory guidelines
        - Reference patterns
    """)
    # Uses rlm_shared_context to get team guidelines
    print(result.response)

asyncio.run(main())
```

---

## Docker Environments

### Run with Docker Isolation

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        environment="docker",
        docker_image="python:3.11-slim",
        docker_memory="1g",
        docker_cpus=2.0,
    )

    result = await rlm.completion("""
        Process untrusted user input:
        1. Parse the JSON payload
        2. Validate all fields
        3. Sanitize strings
        4. Return normalized data
    """)
    print(result.response)

asyncio.run(main())
```

### Custom Docker Image

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        environment="docker",
        docker_image="my-org/custom-runtime:latest",
        docker_memory="2g",
    )

    result = await rlm.completion("""
        Run analysis using our custom ML libraries:
        1. Load the model from /models/
        2. Process input.csv
        3. Save predictions to /output/
    """)
    print(result.response)

asyncio.run(main())
```

---

## Error Handling

### Handle Budget Errors

```python
from rlm import RLM
from rlm.core.exceptions import (
    MaxDepthExceeded,
    TokenBudgetExhausted,
    ToolBudgetExhausted,
)
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        max_depth=2,
        token_budget=1000,
    )

    try:
        result = await rlm.completion("Complex recursive task...")
        print(result.response)
    except MaxDepthExceeded as e:
        print(f"Hit recursion limit at depth {e.depth}")
    except TokenBudgetExhausted as e:
        print(f"Used {e.tokens_used} tokens, budget was {e.budget}")
    except ToolBudgetExhausted as e:
        print(f"Made {e.calls_made} calls, budget was {e.budget}")

asyncio.run(main())
```

### Handle REPL Errors

```python
from rlm import RLM
from rlm.core.exceptions import REPLExecutionError, REPLTimeoutError
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        environment="local",
    )

    try:
        result = await rlm.completion("Run this problematic code...")
        print(result.response)
    except REPLExecutionError as e:
        print(f"Execution failed: {e.error}")
        print(f"Output before error: {e.output}")
    except REPLTimeoutError as e:
        print(f"Code timed out after {e.timeout}s")
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(main())
```

---

## Custom Tools

### Create a Simple Tool

```python
from rlm import RLM
from rlm.tools.base import Tool
import asyncio

async def get_weather(city: str) -> dict:
    """Get weather for a city."""
    # Your implementation
    return {"city": city, "temp": 72, "condition": "sunny"}

async def main():
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

    rlm = RLM(
        model="gpt-4o-mini",
        tools=[weather_tool],
    )

    result = await rlm.completion("What's the weather in Tokyo?")
    print(result.response)

asyncio.run(main())
```

### Create a Data Processing Tool

```python
from rlm import RLM
from rlm.tools.base import Tool
import pandas as pd
import asyncio

async def analyze_csv(file_path: str) -> dict:
    """Analyze a CSV file and return summary statistics."""
    df = pd.read_csv(file_path)
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "numeric_cols": df.select_dtypes(include=['number']).columns.tolist(),
        "null_counts": df.isnull().sum().to_dict(),
    }

async def main():
    analyze_tool = Tool(
        name="analyze_csv",
        description="Analyze a CSV file and return statistics",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to CSV file"}
            },
            "required": [" },
        handler=analyze_csv,
    )

   file_path"]
        rlm = RLM(
        model="gpt-4o-mini",
        tools=[analyze_tool],
    )

    result = await rlm.completion("Analyze data/users.csv")
    print(result.response)

asyncio.run(main())
```

---

## Agent Tasks

### Autonomous Task Completion

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o",
        environment="docker",
        max_depth=10,
    )

    result = await rlm.agent_run(
        goal="""
            Research competitors and create a summary:
            1. Search for top 5 competitors
            2. Compare their features
            3. Identify gaps in the market
            4. Create a SWOT analysis
            5. Save report to competitor_analysis.md
        """,
        max_iterations=20,
        cost_limit=5.0,  # Maximum $5
    )

    print(f"Completed in {len(result.events)} iterations")
    print(f"Total cost: ${result.total_cost_usd:.2f}")
    print(result.response)

asyncio.run(main())
```

### Iterative Refinement

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o",
        max_depth=5,
    )

    result = await rlm.agent_run(
        goal="""
            Write and improve a sorting algorithm:
            1. Implement quicksort
            2. Test with random arrays
            3. Measure performance
            4. Optimize if needed
            5. Add documentation
        """,
        max_iterations=10,
    )

    print(result.response)

asyncio.run(main())
```

---

## Debugging

### Verbose Mode

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        verbose=True,  # Enable verbose logging
        log_level="DEBUG",
    )

    result = await rlm.completion("Your task here")
    # See detailed logs of execution

asyncio.run(main())
```

### Inspect Trajectory

```python
from rlm import RLM
import asyncio

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        max_depth=3,
    )

    result = await rlm.completion("Complex task...")

    # Inspect trajectory
    print(f"Trajectory ID: {result.trajectory_id}")
    print(f"Total calls: {result.total_calls}")
    print(f"Total tokens: {result.total_tokens}")
    print(f"Duration: {result.duration_ms}ms")

    # View each event
    for i, event in enumerate(result.events):
        print(f"\n--- Event {i} (depth={event.depth}) ---")
        print(f"Prompt: {event.prompt[:100]}...")
        print(f"Tool calls: {len(event.tool_calls)}")
        if event.error:
            print(f"Error: {event.error}")

asyncio.run(main())
```

### View Logs

```bash
# View recent trajectories
rlm logs

# View specific trajectory
rlm logs <trajectory-id>

# View with verbose output
rlm logs -v

# Specify log directory
rlm logs --dir ./custom-logs
```

### Trajectory Visualizer

```bash
# Launch the web-based visualizer
rlm visualize

# Custom port and directory
rlm visualize --dir ./logs --port 8502

# Then open http://localhost:8502 in your browser
```
