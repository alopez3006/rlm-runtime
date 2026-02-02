# Testing Documentation

This document explains how to run tests, the test structure, and how to add new tests to RLM Runtime.

## Table of Contents

- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Fixtures and Mocks](#fixtures-and-mocks)
- [Test Coverage](#test-coverage)
- [Continuous Integration](#continuous-integration)

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=rlm --cov-report=term-missing

# Run with HTML coverage report
pytest --cov=rlm --cov-report=html

# Run specific test file
pytest tests/unit/test_repl_local.py

# Run tests matching a pattern
pytest -k "test_execute"

# Run tests matching multiple patterns
pytest -k "execute or search"

# Exclude tests matching a pattern
pytest -k "not docker"

# Run with verbose output
pytest -v

# Run with debugging output
pytest -vv
```

### Docker Tests

```bash
# Run Docker REPL tests (requires Docker)
pytest tests/unit/test_repl_docker.py -v

# Run with specific Docker image
pytest tests/unit/test_repl_docker.py --docker-image python:3.12-slim
```

### Async Tests

```bash
# Run async tests
pytest tests/ -v

# Async mode is configured in pyproject.toml
# asyncio_mode = "auto"
```

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_agent_*.py      # Agent tests
│   ├── test_backend_*.py    # Backend tests
│   ├── test_cli.py          # CLI tests
│   ├── test_config.py       # Config tests
│   ├── test_exceptions.py   # Exception tests
│   ├── test_mcp_*.py        # MCP tests
│   ├── test_orchestrator.py # Orchestrator tests
│   ├── test_pricing.py      # Pricing tests
│   ├── test_repl_*.py       # REPL tests
│   ├── test_safety.py       # Safety tests
│   ├── test_tools_*.py      # Tool tests
│   ├── test_trajectory.py   # Trajectory tests
│   └── test_types.py        # Type tests
└── integration/
    ├── __init__.py
    └── test_orchestrator.py # Integration tests
```

### Test Categories

| Category | Location | Purpose |
|----------|----------|---------|
| Unit tests | `tests/unit/` | Test individual components |
| Integration tests | `tests/integration/` | Test component interactions |
| E2E tests | `tests/e2e/` | Full workflow tests |

---

## Writing Tests

### Basic Test Structure

```python
import pytest
from rlm import RLM

@pytest.mark.asyncio
async def test_basic_completion():
    """Test basic completion functionality."""
    rlm = RLM(model="gpt-4o-mini")
    result = await rlm.completion("Say hello")
    assert result.response
    assert result.total_calls == 1
```

### Test Class Structure

```python
import pytest
from rlm.repl.local import LocalREPL

class TestLocalREPL:
    """Test suite for LocalREPL."""

    @pytest.fixture
    def repl(self):
        """Create a REPL instance for testing."""
        return LocalREPL(timeout=30)

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, repl):
        """Test executing simple Python code."""
        result = await repl.execute("print(2 + 2)")
        assert result.output.strip() == "4"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_with_error(self, repl):
        """Test that errors are handled properly."""
        result = await repl.execute("print(")
        assert result.error is not None
        assert "SyntaxError" in result.error
```

### Parameterized Tests

```python
import pytest

@pytest.mark.parametrize("code,expected", [
    ("2 + 2", "4"),
    ("10 * 5", "50"),
    ("'hello'.upper()", "'HELLO'"),
])
@pytest.mark.asyncio
async def test_math_operations(repl, code, expected):
    """Test various math operations."""
    result = await repl.execute(f"result = {code}\nprint(result)")
    assert expected in result.output
```

### Testing Exceptions

```python
import pytest
from rlm.core.exceptions import MaxDepthExceeded, TokenBudgetExhausted

@pytest.mark.asyncio
async def test_max_depth_exceeded():
    """Test that max depth limit is enforced."""
    rlm = RLM(model="gpt-4o-mini", max_depth=1)

    with pytest.raises(MaxDepthExceeded) as exc_info:
        await rlm.completion("Recursive task that exceeds depth")

    assert exc_info.value.depth == 1
    assert exc_info.value.max_depth == 1
```

---

## Fixtures and Mocks

### Shared Fixtures (conftest.py)

```python
import pytest
import asyncio
from rlm import RLM

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def rlm():
    """Create a basic RLM instance."""
    return RLM(model="gpt-4o-mini")

@pytest.fixture
def rlm_docker():
    """Create a Docker-based RLM instance."""
    return RLM(model="gpt-4o-mini", environment="docker")

@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file for testing."""
    csv_content = "name,age,city\nAlice,30,NYC\nBob,25,LA"
    path = tmp_path / "test.csv"
    path.write_text(csv_content)
    return path
```

### Mocking LLM Responses

```python
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_with_mocked_llm():
    """Test with mocked LLM response."""
    mock_response = {
        "choices": [{
            "message": {
                "content": "Mocked response",
                "role": "assistant"
            }
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5
        }
    }

    with patch('rlm.backends.litellm.LiteLLMBackend._complete') as mock:
        mock.return_value = mock_response

        rlm = RLM(model="gpt-4o-mini")
        result = await rlm.completion("Test prompt")

        assert result.response == "Mocked response"
        mock.assert_called_once()
```

### Mocking File System

```python
import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os

@pytest.mark.asyncio
async def test_with_mocked_files():
    """Test with mocked file system."""
    mock_files = {
        "/test/file.py": "print('hello')",
        "/test/data.csv": "a,b,c\n1,2,3",
    }

    with patch('builtins.open', side_effect=lambda path, mode:
               MagicMock(__enter__=lambda s: MagicMock(
                   read=lambda: mock_files.get(str(path), ""),
                   write=lambda x: None,
                   __exit__=lambda *args: None
               ), __exit__=lambda *args: None)):
        # Test code that reads files
        pass
```

---

## Test Coverage

### Coverage Goals

Current coverage targets by module:

| Module | Target | Current |
|--------|--------|---------|
| Core (orchestrator, types) | 90% | ~85% |
| REPL (local, docker, wasm) | 85% | ~80% |
| Tools (builtin, snipara) | 80% | ~75% |
| Backends | 75% | ~70% |
| CLI | 70% | ~65% |

### Running with Coverage

```bash
# Generate coverage report
pytest --cov=rlm --cov-report=term-missing

# Generate HTML report
pytest --cov=rlm --cov-report=html

# Generate XML report for CI
pytest --cov=rlm --cov-report=xml

# Report on specific modules
pytest --cov=rlm.core --cov-report=term-missing
```

### Coverage Exclusions

Some code is intentionally excluded from coverage:

```python
if TYPE_CHECKING:
    # Type hints only - not executed at runtime

# pragma: no cover
# Debug code that shouldn't be shipped

# pragma: allowlist nextline
def legacy_function():
    """Legacy function kept for backwards compatibility."""
```

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run linting
        run: |
          ruff check src/
          ruff format --check src/
          mypy src/

      - name: Run tests
        run: |
          pytest --cov=rlm --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
        args: [--ignore-missing-imports]
```

---

## Test Best Practices

### 1. Test Naming

Use descriptive test names that explain what is being tested:

```python
# Good
async def test_completion_returns_response_within_token_budget():
    ...

# Bad
async def test_completion():
    ...
```

### 2. Test Isolation

Each test should be independent:

```python
@pytest.fixture
def isolated_repl():
    """Each test gets a fresh REPL."""
    return LocalREPL(timeout=30)
```

### 3. Test Documentation

Document what each test verifies:

```python
@pytest.mark.asyncio
async def test_nested_tool_calls_with_depth_limit():
    """Verify that tool call depth is properly limited.

    Tests that:
    1. Recursive calls stop at max_depth
    2. MaxDepthExceeded exception is raised
    3. Partial results are still returned
    """
```

### 4. Edge Case Testing

Test edge cases and error conditions:

```python
@pytest.mark.asyncio
async def test_empty_prompt_handling():
    """Test that empty prompts are handled gracefully."""
    rlm = RLM(model="gpt-4o-mini")
    result = await rlm.completion("")
    assert result.response  # Should still get a response

@pytest.mark.asyncio
async def test_very_long_prompt():
    """Test handling of prompts near token limits."""
    long_prompt = "word " * 10000  # ~70K tokens
    rlm = RLM(model="gpt-4o-mini", token_budget=1000)
    # Should handle gracefully
```

---

## Debugging Tests

### Print Debugging

```python
@pytest.mark.asyncio
async def test_debug_example():
    """Debug test with print output."""
    rlm = RLM(model="gpt-4o-mini", verbose=True)
    result = await rlm.completion("Debug prompt")
    print(f"Result: {result}")
    print(f"Trajectory: {result.events}")
```

### PDB Debugging

```python
@pytest.mark.asyncio
async def test_with_pdb():
    """Debug with pdb."""
    import pdb

    rlm = RLM(model="gpt-4o-mini")

    pdb.set_trace()
    result = await rlm.completion("Test")
```

### pytest-sugar

```bash
# Install pytest-sugar for better output
pip install pytest-sugar

# Run with pytest-sugar
pytest --pytest-sugar
```
