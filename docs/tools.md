# Tool Development Guide

Learn how to create custom tools for RLM Runtime.

## Overview

Tools allow LLMs to interact with external systems, execute code, and access data. RLM comes with builtin tools and supports custom tool development.

## Builtin Tools

RLM includes these builtin tools:

| Tool | Description |
|------|-------------|
| `execute_code` | Execute Python code in the sandboxed REPL |
| `file_read` | Read file contents |
| `list_files` | List files in a directory |

When Snipara is configured, additional tools are available:

| Tool | Description |
|------|-------------|
| `context_query` | Query project context semantically |
| `sections` | Get code sections by path |
| `search` | Hybrid keyword + semantic search |

## Creating Custom Tools

### Basic Tool Structure

```python
from rlm import RLM
from rlm.backends.base import Tool

# 1. Define the handler function
async def get_weather(city: str, units: str = "celsius") -> dict:
    """Get weather for a city."""
    # Your implementation here
    return {
        "city": city,
        "temperature": 22,
        "units": units,
        "condition": "sunny"
    }

# 2. Create the tool definition
weather_tool = Tool(
    name="get_weather",
    description="Get current weather for a city",
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name (e.g., 'London', 'New York')"
            },
            "units": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature units",
                "default": "celsius"
            }
        },
        "required": ["city"]
    },
    handler=get_weather,
)

# 3. Register with RLM
rlm = RLM(
    model="gpt-4o-mini",
    tools=[weather_tool],
)

# 4. Use in completion
result = await rlm.completion("What's the weather in Paris?")
```

### Tool Parameters Schema

Tools use JSON Schema for parameter definitions:

```python
parameters = {
    "type": "object",
    "properties": {
        # String parameter
        "name": {
            "type": "string",
            "description": "User's name"
        },
        # Number parameter
        "age": {
            "type": "integer",
            "minimum": 0,
            "maximum": 150
        },
        # Enum parameter
        "status": {
            "type": "string",
            "enum": ["active", "inactive", "pending"]
        },
        # Array parameter
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of tags"
        },
        # Object parameter
        "metadata": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"}
            }
        },
        # Optional with default
        "limit": {
            "type": "integer",
            "default": 10,
            "description": "Maximum results"
        }
    },
    "required": ["name", "status"]  # Required fields
}
```

### Async vs Sync Handlers

Tool handlers should be async, but sync functions work too:

```python
# Async handler (recommended)
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Sync handler (wrapped automatically)
def calculate(a: int, b: int) -> int:
    return a + b
```

### Error Handling

Return errors gracefully for better LLM feedback:

```python
from rlm.core.exceptions import ToolExecutionError

async def database_query(query: str) -> dict:
    try:
        result = await db.execute(query)
        return {"rows": result, "count": len(result)}
    except DatabaseError as e:
        # Return error as string - LLM will see this
        return {"error": str(e), "query": query}
    except Exception as e:
        # Or raise ToolExecutionError for structured handling
        raise ToolExecutionError(
            tool_name="database_query",
            error=str(e),
            arguments={"query": query}
        )
```

## Advanced Patterns

### Tools with State

```python
class DatabaseTool:
    def __init__(self, connection_string: str):
        self.conn = create_connection(connection_string)
        self._cache = {}

    async def query(self, sql: str) -> dict:
        if sql in self._cache:
            return self._cache[sql]
        result = await self.conn.execute(sql)
        self._cache[sql] = result
        return result

# Create tool from class method
db = DatabaseTool("postgresql://...")
db_tool = Tool(
    name="database_query",
    description="Execute SQL query",
    parameters={
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "SQL query"}
        },
        "required": ["sql"]
    },
    handler=db.query,
)
```

### Tool Chains

Create tools that work together:

```python
# Tool 1: Search for files
async def search_files(pattern: str) -> list[str]:
    return glob.glob(pattern)

# Tool 2: Read file content
async def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()

# Tool 3: Analyze content
async def analyze_code(content: str) -> dict:
    # Your analysis logic
    return {"lines": len(content.split('\n')), "complexity": "medium"}

# Register all tools
rlm = RLM(tools=[
    Tool(name="search_files", ...),
    Tool(name="read_file", ...),
    Tool(name="analyze_code", ...),
])

# LLM can chain: search -> read -> analyze
result = await rlm.completion(
    "Find all Python files and analyze their complexity"
)
```

### Dynamic Tool Registration

```python
# Register tools after initialization
rlm = RLM(model="gpt-4o-mini")

# Add tool later
rlm.tool_registry.register(my_tool)

# Remove tool
rlm.tool_registry.unregister("my_tool")

# List all tools
tools = rlm.tool_registry.get_all()
for tool in tools:
    print(f"{tool.name}: {tool.description}")
```

### Tool Validation

Add input validation:

```python
from pydantic import BaseModel, validator

class WeatherParams(BaseModel):
    city: str
    units: str = "celsius"

    @validator('city')
    def city_not_empty(cls, v):
        if not v.strip():
            raise ValueError('City cannot be empty')
        return v.strip()

    @validator('units')
    def valid_units(cls, v):
        if v not in ['celsius', 'fahrenheit']:
            raise ValueError('Units must be celsius or fahrenheit')
        return v

async def get_weather_validated(**kwargs) -> dict:
    params = WeatherParams(**kwargs)
    # Now params.city and params.units are validated
    return await fetch_weather(params.city, params.units)
```

## Tool Best Practices

### 1. Clear Descriptions

Write descriptions that help the LLM understand when to use the tool:

```python
# Good
description = "Search for files by name pattern. Use glob syntax like '*.py' or 'src/**/*.ts'"

# Bad
description = "Search files"
```

### 2. Meaningful Parameter Names

```python
# Good
parameters = {
    "properties": {
        "search_query": {"type": "string"},
        "max_results": {"type": "integer"},
        "include_archived": {"type": "boolean"}
    }
}

# Bad
parameters = {
    "properties": {
        "q": {"type": "string"},
        "n": {"type": "integer"},
        "a": {"type": "boolean"}
    }
}
```

### 3. Return Structured Data

```python
# Good - structured response
async def search(query: str) -> dict:
    results = await do_search(query)
    return {
        "query": query,
        "count": len(results),
        "results": results[:10],
        "has_more": len(results) > 10
    }

# Bad - unstructured string
async def search(query: str) -> str:
    results = await do_search(query)
    return str(results)
```

### 4. Handle Edge Cases

```python
async def divide(a: float, b: float) -> dict:
    if b == 0:
        return {"error": "Cannot divide by zero", "a": a, "b": b}
    return {"result": a / b, "a": a, "b": b}
```

### 5. Rate Limiting

```python
from asyncio import Semaphore

class RateLimitedTool:
    def __init__(self, max_concurrent: int = 5):
        self._semaphore = Semaphore(max_concurrent)

    async def call_api(self, **kwargs) -> dict:
        async with self._semaphore:
            return await self._do_call(**kwargs)
```

## Testing Tools

```python
import pytest
from rlm.backends.base import Tool

@pytest.fixture
def weather_tool():
    async def handler(city: str) -> dict:
        return {"city": city, "temp": 20}

    return Tool(
        name="get_weather",
        description="Get weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"]
        },
        handler=handler,
    )

@pytest.mark.asyncio
async def test_weather_tool(weather_tool):
    result = await weather_tool.execute(city="London")
    assert result["city"] == "London"
    assert "temp" in result

@pytest.mark.asyncio
async def test_weather_tool_integration():
    rlm = RLM(tools=[weather_tool])
    result = await rlm.completion("What's the weather in Paris?")
    assert "Paris" in result.response or "20" in result.response
```

## MCP Tool Integration

Tools registered with RLM are automatically available in the MCP server:

```python
# Your custom tools work in Claude Desktop/Code
rlm = RLM(tools=[my_custom_tool])

# Start MCP server (tools are exposed)
# rlm mcp-serve
```

## Example: Complete Tool

```python
"""Example: GitHub Issues Tool"""

import httpx
from rlm import RLM
from rlm.backends.base import Tool

class GitHubTool:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={"Authorization": f"token {token}"}
        )

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        limit: int = 10
    ) -> dict:
        """List issues for a repository."""
        try:
            response = await self.client.get(
                f"/repos/{owner}/{repo}/issues",
                params={"state": state, "per_page": limit}
            )
            response.raise_for_status()
            issues = response.json()
            return {
                "count": len(issues),
                "issues": [
                    {
                        "number": i["number"],
                        "title": i["title"],
                        "state": i["state"],
                        "author": i["user"]["login"]
                    }
                    for i in issues
                ]
            }
        except httpx.HTTPError as e:
            return {"error": str(e)}

    def as_tool(self) -> Tool:
        return Tool(
            name="github_list_issues",
            description="List GitHub issues for a repository",
            parameters={
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner (username or org)"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "default": "open"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["owner", "repo"]
            },
            handler=self.list_issues,
        )

# Usage
github = GitHubTool(token="ghp_...")
rlm = RLM(
    model="gpt-4o-mini",
    tools=[github.as_tool()]
)

result = await rlm.completion(
    "List the open issues in the facebook/react repository"
)
```
