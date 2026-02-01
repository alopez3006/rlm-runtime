"""RLM configuration management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class ExecutionProfile:
    """Predefined execution profile with resource limits."""

    timeout: int  # Seconds
    memory: str  # Docker memory limit (e.g., "512m", "2g")
    description: str


# Built-in execution profiles
EXECUTION_PROFILES: dict[str, ExecutionProfile] = {
    "quick": ExecutionProfile(
        timeout=5,
        memory="128m",
        description="Fast operations: simple math, string manipulation",
    ),
    "default": ExecutionProfile(
        timeout=30,
        memory="512m",
        description="Standard operations: data processing, algorithms",
    ),
    "analysis": ExecutionProfile(
        timeout=120,
        memory="2g",
        description="Heavy computation: large datasets, complex algorithms",
    ),
    "extended": ExecutionProfile(
        timeout=300,
        memory="4g",
        description="Long-running tasks: batch processing, extensive analysis",
    ),
}


def get_profile(name: str) -> ExecutionProfile:
    """Get an execution profile by name.

    Args:
        name: Profile name (quick, default, analysis, extended)

    Returns:
        ExecutionProfile with timeout and memory settings

    Raises:
        ValueError: If profile name is unknown
    """
    if name not in EXECUTION_PROFILES:
        available = ", ".join(EXECUTION_PROFILES.keys())
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return EXECUTION_PROFILES[name]


class RLMConfig(BaseSettings):
    """RLM runtime configuration.

    Configuration can be set via:
    1. Environment variables (RLM_* prefix)
    2. rlm.toml config file
    3. Direct instantiation
    """

    model_config = SettingsConfigDict(
        env_prefix="RLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Backend settings
    backend: str = "litellm"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    api_key: str | None = None  # For direct OpenAI/Anthropic

    # Environment settings
    environment: str = "local"
    docker_image: str = "python:3.11-slim"
    docker_cpus: float = 1.0
    docker_memory: str = "512m"
    docker_network_disabled: bool = True
    docker_timeout: int = 30

    # Limits
    max_depth: int = 4
    max_subcalls: int = 12
    token_budget: int = 8000
    tool_budget: int = 20
    timeout_seconds: int = 120
    parallel_tools: bool = False
    max_parallel: int = 5

    # Sub-LLM Orchestration
    sub_calls_enabled: bool = True
    sub_calls_max_per_turn: int = 5
    sub_calls_budget_inheritance: float = 0.5  # Fraction of parent's remaining budget
    sub_calls_max_cost_per_session: float = 1.0  # Max dollar cost for sub-calls per session

    # Security: File access restrictions
    # Paths that file tools can access. Empty list means current directory only.
    allowed_paths: list[Path] = Field(default_factory=list)

    # Logging
    log_dir: Path = Field(default_factory=lambda: Path("./logs"))
    verbose: bool = False
    log_level: str = "INFO"

    # Snipara integration (optional)
    snipara_api_key: str | None = Field(default=None, alias="SNIPARA_API_KEY")
    snipara_project_slug: str | None = Field(default=None, alias="SNIPARA_PROJECT_SLUG")
    snipara_base_url: str = "https://api.snipara.com/mcp"
    memory_enabled: bool = False  # Enable Snipara memory tools (rlm_remember, rlm_recall)

    @property
    def snipara_enabled(self) -> bool:
        """Check if Snipara integration is configured."""
        return bool(self.snipara_api_key and self.snipara_project_slug)

    def get_snipara_url(self) -> str | None:
        """Get the full Snipara MCP URL."""
        if not self.snipara_enabled:
            return None
        return f"{self.snipara_base_url}/{self.snipara_project_slug}"


def load_config(config_path: Path | None = None) -> RLMConfig:
    """Load configuration from file and environment.

    Priority (highest to lowest):
    1. Environment variables
    2. Config file (if provided)
    3. Default values

    Args:
        config_path: Optional path to rlm.toml config file

    Returns:
        RLMConfig instance
    """
    config_data: dict[str, Any] = {}

    # Try to load from config file
    if config_path is None:
        # Look for rlm.toml in current directory
        config_path = Path("rlm.toml")

    if config_path.exists():
        try:
            import tomllib

            with open(config_path, "rb") as f:
                toml_data = tomllib.load(f)
            config_data = toml_data.get("rlm", {})
        except ImportError:
            # Python < 3.11, try tomli
            try:
                import tomli

                with open(config_path, "rb") as f:
                    toml_data = tomli.load(f)
                config_data = toml_data.get("rlm", {})
            except ImportError:
                pass  # No TOML library available, use defaults

    return RLMConfig(**config_data)


def save_config(config: RLMConfig, config_path: Path) -> None:
    """Save configuration to a TOML file.

    Args:
        config: RLMConfig instance to save
        config_path: Path to save the config file
    """
    lines = [
        "# RLM Runtime Configuration",
        "",
        "[rlm]",
        f'backend = "{config.backend}"',
        f'model = "{config.model}"',
        f"temperature = {config.temperature}",
        f'environment = "{config.environment}"',
        f"max_depth = {config.max_depth}",
        f"max_subcalls = {config.max_subcalls}",
        f"token_budget = {config.token_budget}",
        f"verbose = {str(config.verbose).lower()}",
        "",
        "# Docker settings",
        f'docker_image = "{config.docker_image}"',
        f"docker_cpus = {config.docker_cpus}",
        f'docker_memory = "{config.docker_memory}"',
        "",
        "# Security: File access restrictions",
        "# Paths that file tools can access. Empty list means current directory only.",
        f"allowed_paths = {[str(p) for p in config.allowed_paths]}",
        "",
        "# Snipara integration (optional)",
        "# Get your API key at https://snipara.com/dashboard",
    ]

    if config.snipara_api_key:
        lines.append(f'snipara_api_key = "{config.snipara_api_key}"')
    else:
        lines.append('# snipara_api_key = "rlm_..."')

    if config.snipara_project_slug:
        lines.append(f'snipara_project_slug = "{config.snipara_project_slug}"')
    else:
        lines.append('# snipara_project_slug = "your-project"')

    config_path.write_text("\n".join(lines) + "\n")
