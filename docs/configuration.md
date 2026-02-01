# Configuration Guide

RLM Runtime can be configured via TOML files, environment variables, or programmatically.

## Configuration Priority

1. **Environment variables** (highest priority)
2. **rlm.toml config file**
3. **Default values** (lowest priority)

## Quick Setup

```bash
# Initialize config in current directory
rlm init

# Check your setup
rlm doctor
```

## Configuration File

Create `rlm.toml` in your project root:

```toml
[rlm]
# LLM Backend
backend = "litellm"           # litellm, openai, or anthropic
model = "gpt-4o-mini"         # Model identifier
temperature = 0.0             # Sampling temperature (0.0 = deterministic)

# Execution Environment
environment = "local"         # local, docker, or wasm

# Recursion Limits
max_depth = 4                 # Maximum recursive depth
max_subcalls = 12             # Maximum total LLM calls
token_budget = 8000           # Token limit per completion
tool_budget = 20              # Maximum tool calls
timeout_seconds = 120         # Overall timeout

# Logging
log_dir = "./logs"            # Trajectory log directory
verbose = false               # Enable verbose output
log_level = "INFO"            # Logging level

# Docker Settings (when environment = "docker")
docker_image = "python:3.11-slim"
docker_cpus = 1.0
docker_memory = "512m"
docker_network_disabled = true
docker_timeout = 30

# Snipara Integration (optional)
snipara_api_key = "rlm_..."
snipara_project_slug = "my-project"
snipara_base_url = "https://api.snipara.com/mcp"
```

## Environment Variables

All configuration options can be set via environment variables with the `RLM_` prefix:

```bash
# Backend
export RLM_BACKEND=litellm
export RLM_MODEL=gpt-4o-mini
export RLM_TEMPERATURE=0.0

# Environment
export RLM_ENVIRONMENT=docker

# Limits
export RLM_MAX_DEPTH=4
export RLM_MAX_SUBCALLS=12
export RLM_TOKEN_BUDGET=8000
export RLM_TOOL_BUDGET=20
export RLM_TIMEOUT_SECONDS=120

# Logging
export RLM_LOG_DIR=./logs
export RLM_VERBOSE=false
export RLM_LOG_LEVEL=INFO

# Docker
export RLM_DOCKER_IMAGE=python:3.11-slim
export RLM_DOCKER_CPUS=1.0
export RLM_DOCKER_MEMORY=512m
export RLM_DOCKER_NETWORK_DISABLED=true
export RLM_DOCKER_TIMEOUT=30

# Snipara (no RLM_ prefix)
export SNIPARA_API_KEY=rlm_...
export SNIPARA_PROJECT_SLUG=my-project
```

## API Key Configuration

Set your LLM provider API keys:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Azure OpenAI
export AZURE_API_KEY=...
export AZURE_API_BASE=https://your-resource.openai.azure.com
export AZURE_API_VERSION=2024-02-15-preview

# Other providers (via LiteLLM)
# See: https://docs.litellm.ai/docs/providers
```

## Programmatic Configuration

```python
from rlm import RLM
from rlm.core.config import RLMConfig

# Direct parameters (override config file)
rlm = RLM(
    model="gpt-4o",
    environment="docker",
    verbose=True,
)

# Custom config object
config = RLMConfig(
    model="claude-sonnet-4-20250514",
    environment="docker",
    max_depth=6,
    token_budget=16000,
    docker_memory="1g",
)

rlm = RLM(config=config)
```

## Configuration Options Reference

### Backend Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `backend` | str | `"litellm"` | LLM backend: `litellm`, `openai`, `anthropic` |
| `model` | str | `"gpt-4o-mini"` | Model identifier |
| `temperature` | float | `0.0` | Sampling temperature (0.0-2.0) |
| `api_key` | str | None | Provider API key (usually via env var) |

### Environment Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `environment` | str | `"local"` | REPL environment: `local`, `docker`, `wasm` |

### Recursion Limits

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_depth` | int | `4` | Maximum recursive depth |
| `max_subcalls` | int | `12` | Maximum total LLM calls |
| `token_budget` | int | `8000` | Token limit per completion |
| `tool_budget` | int | `20` | Maximum tool calls |
| `timeout_seconds` | int | `120` | Overall execution timeout |

### Docker Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `docker_image` | str | `"python:3.11-slim"` | Docker image to use |
| `docker_cpus` | float | `1.0` | CPU limit |
| `docker_memory` | str | `"512m"` | Memory limit |
| `docker_network_disabled` | bool | `true` | Disable network access |
| `docker_timeout` | int | `30` | Per-execution timeout |

### Logging Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_dir` | Path | `"./logs"` | Trajectory log directory |
| `verbose` | bool | `false` | Enable verbose output |
| `log_level` | str | `"INFO"` | Logging level |

### Snipara Integration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `snipara_api_key` | str | None | Snipara API key |
| `snipara_project_slug` | str | None | Snipara project slug |
| `snipara_base_url` | str | `"https://api.snipara.com/mcp"` | Snipara API base URL |

## Per-Project Configuration

Create `rlm.toml` in each project directory:

```
~/projects/
├── frontend/
│   └── rlm.toml     # model = "gpt-4o-mini"
├── backend/
│   └── rlm.toml     # model = "gpt-4o", environment = "docker"
└── ml-pipeline/
    └── rlm.toml     # model = "claude-sonnet-4-20250514", max_depth = 8
```

Each project uses its own `rlm.toml` configuration. The CLI automatically detects the config from the current directory.

## Model Selection Guide

| Use Case | Recommended Model | Notes |
|----------|-------------------|-------|
| Quick tasks | `gpt-4o-mini` | Fast, cheap, good for simple tasks |
| Complex analysis | `gpt-4o` | Better reasoning, higher cost |
| Code generation | `claude-sonnet-4-20250514` | Excellent for code tasks |
| Large context | `claude-3-opus-20240229` | 200K context window |

## Security Recommendations

1. **Use Docker for production** - Better isolation for untrusted inputs
2. **Disable network in containers** - `docker_network_disabled = true`
3. **Set resource limits** - Prevent resource exhaustion
4. **Use environment variables for secrets** - Don't commit API keys
5. **Review trajectory logs** - Audit tool usage

## Troubleshooting

### "API key not found"

```bash
# Check if key is set
echo $OPENAI_API_KEY

# Or use rlm doctor
rlm doctor
```

### "Docker not available"

```bash
# Check Docker daemon
docker info

# Install Docker support
pip install rlm-runtime[docker]
```

### "Config file not found"

```bash
# Initialize config
rlm init

# Or specify path
rlm run --config /path/to/rlm.toml "Your prompt"
```
