# Contributing to RLM Runtime

Thank you for your interest in contributing to RLM Runtime! This document provides guidelines and information for contributors.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## Getting Started

### Development Setup

```bash
# Clone the repository
git clone https://github.com/alopez3006/rlm-runtime
cd rlm-runtime

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Verify setup
rlm doctor
pytest
```

### Project Structure

```
rlm-runtime/
├── src/rlm/
│   ├── backends/       # LLM backend adapters
│   ├── cli/            # Command-line interface
│   ├── core/           # Core orchestrator and types
│   ├── logging/        # Trajectory logging
│   ├── mcp/            # MCP server for Claude
│   ├── repl/           # REPL environments (local, docker, wasm)
│   ├── tools/          # Builtin tools and registry
│   └── visualizer/     # Trajectory visualizer
├── tests/              # Test suite
├── docs/               # Documentation
└── examples/           # Example scripts
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes

Follow these guidelines:

- Write clear, readable code
- Add type hints to all functions
- Include docstrings for public APIs
- Update tests for new functionality
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=rlm --cov-report=html

# Run specific tests
pytest tests/unit/test_repl_local.py

# Run tests matching a pattern
pytest -k "test_execute"
```

### 4. Lint and Format

```bash
# Check linting
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Check formatting
ruff format --check src/

# Auto-format
ruff format src/

# Type checking
mypy src/
```

### 5. Commit Changes

Write clear commit messages:

```bash
# Good commit messages
git commit -m "Add WebAssembly REPL using Pyodide"
git commit -m "Fix token counting in recursive completion"
git commit -m "Update configuration documentation"

# Bad commit messages
git commit -m "Fix stuff"
git commit -m "WIP"
```

### 6. Submit Pull Request

1. Push your branch to GitHub
2. Open a Pull Request against `master`
3. Fill out the PR template
4. Wait for CI checks to pass
5. Request review

## Coding Standards

### Python Style

We follow PEP 8 with these additions:

- Line length: 100 characters
- Use type hints everywhere
- Use `from __future__ import annotations` for forward references

```python
from __future__ import annotations

def process_data(
    items: list[str],
    options: dict[str, Any] | None = None,
) -> ProcessResult:
    """Process a list of items.

    Args:
        items: List of items to process
        options: Optional processing options

    Returns:
        ProcessResult with the processed data

    Raises:
        ValueError: If items is empty
    """
    if not items:
        raise ValueError("Items cannot be empty")
    ...
```

### Documentation Style

Use Google-style docstrings:

```python
def example_function(param1: str, param2: int = 10) -> dict[str, Any]:
    """Short description of the function.

    Longer description if needed. Can span multiple lines
    and include examples.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is invalid

    Example:
        ```python
        result = example_function("test", 20)
        print(result)
        ```
    """
```

### Testing Standards

- Write tests for all new functionality
- Use descriptive test names
- Use fixtures for common setup
- Test both success and error cases

```python
import pytest
from rlm.repl.local import LocalREPL

@pytest.fixture
def repl():
    return LocalREPL(timeout=30)

@pytest.mark.asyncio
async def test_execute_simple_code(repl):
    """Test executing simple Python code."""
    result = await repl.execute("print(2 + 2)")
    assert result.output.strip() == "4"
    assert result.error is None

@pytest.mark.asyncio
async def test_execute_with_syntax_error(repl):
    """Test that syntax errors are handled properly."""
    result = await repl.execute("print(")
    assert result.error is not None
    assert "SyntaxError" in result.error
```

## Priority Areas

We welcome contributions in these areas:

### High Priority

1. **Test Coverage** - Help us reach 90%+ coverage
2. **Documentation** - Improve guides and examples
3. **Bug Fixes** - Fix reported issues

### Medium Priority

4. **WebAssembly REPL** - Improve Pyodide integration
5. **New Tools** - Create useful community tools
6. **Performance** - Optimize token usage and latency

### Low Priority

7. **New Backends** - Add support for more LLM providers
8. **Observability** - Add metrics and tracing

## Reporting Issues

### Bug Reports

Include:
- Python version
- RLM version (`rlm version`)
- Steps to reproduce
- Expected vs actual behavior
- Error messages/logs

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternatives considered

## Pull Request Guidelines

### PR Title Format

```
type: short description

Examples:
feat: add streaming support for completions
fix: handle empty response from LLM
docs: update configuration guide
test: add tests for Docker REPL
refactor: simplify tool registry
```

### PR Description Template

```markdown
## Summary
Brief description of changes

## Changes
- List of specific changes
- Another change

## Testing
How was this tested?

## Checklist
- [ ] Tests pass locally
- [ ] Linting passes
- [ ] Documentation updated
- [ ] Type hints added
```

## Release Process

Releases are managed by maintainers:

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create GitHub release
4. CI automatically publishes to PyPI

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email security@snipara.com

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
