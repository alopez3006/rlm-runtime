"""Tests for RLM configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from rlm.core.config import RLMConfig, load_config, save_config


class TestRLMConfig:
    """Tests for RLMConfig class."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = RLMConfig()

        assert config.backend == "litellm"
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.0
        assert config.environment == "local"
        assert config.max_depth == 4
        assert config.max_subcalls == 12
        assert config.token_budget == 8000
        assert config.tool_budget == 20
        assert config.timeout_seconds == 120
        assert config.verbose is False

    def test_custom_values(self):
        """Should accept custom values."""
        config = RLMConfig(
            backend="openai",
            model="gpt-4",
            temperature=0.7,
            environment="docker",
            max_depth=8,
            token_budget=16000,
        )

        assert config.backend == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.environment == "docker"
        assert config.max_depth == 8
        assert config.token_budget == 16000

    def test_docker_settings(self):
        """Should have Docker-specific settings."""
        config = RLMConfig(
            docker_image="python:3.12-slim",
            docker_cpus=2.0,
            docker_memory="1g",
            docker_network_disabled=False,
            docker_timeout=60,
        )

        assert config.docker_image == "python:3.12-slim"
        assert config.docker_cpus == 2.0
        assert config.docker_memory == "1g"
        assert config.docker_network_disabled is False
        assert config.docker_timeout == 60

    def test_log_dir_default(self):
        """Should default log_dir to ./logs."""
        config = RLMConfig()
        assert config.log_dir == Path("./logs")

    def test_log_dir_custom(self):
        """Should accept custom log_dir."""
        config = RLMConfig(log_dir=Path("/custom/logs"))
        assert config.log_dir == Path("/custom/logs")


class TestSniparaIntegration:
    """Tests for Snipara integration settings."""

    def test_snipara_disabled_by_default(self):
        """Should be disabled when no credentials."""
        config = RLMConfig()
        assert config.snipara_enabled is False

    def test_snipara_enabled_with_credentials(self, monkeypatch):
        """Should be enabled when both key and slug are set via env."""
        monkeypatch.setenv("SNIPARA_API_KEY", "rlm_test")
        monkeypatch.setenv("SNIPARA_PROJECT_SLUG", "my-project")

        config = RLMConfig()
        assert config.snipara_enabled is True

    def test_snipara_disabled_without_slug(self, monkeypatch):
        """Should be disabled when slug is missing."""
        monkeypatch.setenv("SNIPARA_API_KEY", "rlm_test")
        monkeypatch.delenv("SNIPARA_PROJECT_SLUG", raising=False)

        config = RLMConfig()
        assert config.snipara_enabled is False

    def test_snipara_disabled_without_key(self, monkeypatch):
        """Should be disabled when key is missing."""
        monkeypatch.delenv("SNIPARA_API_KEY", raising=False)
        monkeypatch.setenv("SNIPARA_PROJECT_SLUG", "my-project")

        config = RLMConfig()
        assert config.snipara_enabled is False

    def test_get_snipara_url_when_enabled(self, monkeypatch):
        """Should return URL when enabled."""
        monkeypatch.setenv("SNIPARA_API_KEY", "rlm_test")
        monkeypatch.setenv("SNIPARA_PROJECT_SLUG", "my-project")

        config = RLMConfig()
        url = config.get_snipara_url()
        assert url == "https://snipara.com/api/mcp/my-project"

    def test_get_snipara_url_when_disabled(self):
        """Should return None when disabled."""
        config = RLMConfig()
        assert config.get_snipara_url() is None

    def test_custom_base_url(self, monkeypatch):
        """Should use custom base URL."""
        monkeypatch.setenv("SNIPARA_API_KEY", "key")
        monkeypatch.setenv("SNIPARA_PROJECT_SLUG", "proj")

        config = RLMConfig(snipara_base_url="https://custom.example.com/api")
        url = config.get_snipara_url()
        assert url == "https://custom.example.com/api/proj"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_defaults_without_file(self, tmp_path, monkeypatch):
        """Should return defaults when no config file exists."""
        monkeypatch.chdir(tmp_path)
        config = load_config()

        assert config.backend == "litellm"
        assert config.model == "gpt-4o-mini"

    def test_load_from_toml_file(self, tmp_path, monkeypatch):
        """Should load settings from rlm.toml."""
        monkeypatch.chdir(tmp_path)

        toml_content = """
[rlm]
backend = "openai"
model = "gpt-4-turbo"
max_depth = 8
verbose = true
"""
        (tmp_path / "rlm.toml").write_text(toml_content)

        config = load_config()

        assert config.backend == "openai"
        assert config.model == "gpt-4-turbo"
        assert config.max_depth == 8
        assert config.verbose is True

    def test_load_from_custom_path(self, tmp_path):
        """Should load from custom config path."""
        config_file = tmp_path / "custom.toml"
        config_file.write_text("""
[rlm]
model = "claude-3-sonnet"
environment = "docker"
""")

        config = load_config(config_path=config_file)

        assert config.model == "claude-3-sonnet"
        assert config.environment == "docker"

    def test_ignores_extra_keys(self, tmp_path, monkeypatch):
        """Should ignore unknown keys in config."""
        monkeypatch.chdir(tmp_path)

        toml_content = """
[rlm]
model = "gpt-4"
unknown_key = "value"
another_unknown = 123
"""
        (tmp_path / "rlm.toml").write_text(toml_content)

        # Should not raise
        config = load_config()
        assert config.model == "gpt-4"

    def test_env_vars_override_file(self, tmp_path, monkeypatch):
        """Environment variables should override file settings."""
        monkeypatch.chdir(tmp_path)

        toml_content = """
[rlm]
model = "gpt-4"
max_depth = 4
"""
        (tmp_path / "rlm.toml").write_text(toml_content)

        # Set env vars BEFORE loading config
        monkeypatch.setenv("RLM_MODEL", "claude-3-opus")
        monkeypatch.setenv("RLM_MAX_DEPTH", "10")

        # Reload the module to pick up new env vars
        config = RLMConfig()

        assert config.model == "claude-3-opus"
        assert config.max_depth == 10


class TestSaveConfig:
    """Tests for save_config function."""

    def test_saves_basic_config(self, tmp_path):
        """Should save config to TOML file."""
        config = RLMConfig(
            backend="openai",
            model="gpt-4",
            max_depth=6,
            verbose=True,
        )
        config_path = tmp_path / "rlm.toml"

        save_config(config, config_path)

        assert config_path.exists()
        content = config_path.read_text()
        assert 'backend = "openai"' in content
        assert 'model = "gpt-4"' in content
        assert "max_depth = 6" in content
        assert "verbose = true" in content

    def test_saves_docker_settings(self, tmp_path):
        """Should save Docker settings."""
        config = RLMConfig(
            docker_image="python:3.12",
            docker_cpus=2.0,
            docker_memory="1g",
        )
        config_path = tmp_path / "rlm.toml"

        save_config(config, config_path)

        content = config_path.read_text()
        assert 'docker_image = "python:3.12"' in content
        assert "docker_cpus = 2.0" in content
        assert 'docker_memory = "1g"' in content

    def test_saves_snipara_credentials(self, tmp_path, monkeypatch):
        """Should save Snipara credentials when set."""
        monkeypatch.setenv("SNIPARA_API_KEY", "rlm_secret")
        monkeypatch.setenv("SNIPARA_PROJECT_SLUG", "my-project")

        config = RLMConfig()
        config_path = tmp_path / "rlm.toml"

        save_config(config, config_path)

        content = config_path.read_text()
        assert 'snipara_api_key = "rlm_secret"' in content
        assert 'snipara_project_slug = "my-project"' in content

    def test_comments_out_snipara_when_not_set(self, tmp_path):
        """Should comment out Snipara when not configured."""
        config = RLMConfig()
        config_path = tmp_path / "rlm.toml"

        save_config(config, config_path)

        content = config_path.read_text()
        assert '# snipara_api_key = "rlm_..."' in content
        assert '# snipara_project_slug = "your-project"' in content

    def test_roundtrip_config(self, tmp_path, monkeypatch):
        """Saved config should be loadable."""
        monkeypatch.chdir(tmp_path)

        original = RLMConfig(
            backend="anthropic",
            model="claude-3-sonnet",
            max_depth=6,
            token_budget=10000,
            environment="docker",
        )
        config_path = tmp_path / "rlm.toml"

        save_config(original, config_path)
        loaded = load_config(config_path)

        assert loaded.backend == original.backend
        assert loaded.model == original.model
        assert loaded.max_depth == original.max_depth
        assert loaded.token_budget == original.token_budget
        assert loaded.environment == original.environment


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_env_prefix(self, monkeypatch):
        """Should use RLM_ prefix for env vars."""
        monkeypatch.setenv("RLM_MODEL", "custom-model")
        monkeypatch.setenv("RLM_MAX_DEPTH", "10")
        monkeypatch.setenv("RLM_VERBOSE", "true")

        config = RLMConfig()

        assert config.model == "custom-model"
        assert config.max_depth == 10
        assert config.verbose is True

    def test_docker_env_vars(self, monkeypatch):
        """Should load Docker settings from env vars."""
        monkeypatch.setenv("RLM_DOCKER_IMAGE", "python:3.10")
        monkeypatch.setenv("RLM_DOCKER_CPUS", "0.5")
        monkeypatch.setenv("RLM_DOCKER_MEMORY", "256m")

        config = RLMConfig()

        assert config.docker_image == "python:3.10"
        assert config.docker_cpus == 0.5
        assert config.docker_memory == "256m"

    def test_snipara_env_alias(self, monkeypatch):
        """Should support SNIPARA_* env var aliases."""
        monkeypatch.setenv("SNIPARA_API_KEY", "rlm_from_env")
        monkeypatch.setenv("SNIPARA_PROJECT_SLUG", "env-project")

        config = RLMConfig()

        assert config.snipara_api_key == "rlm_from_env"
        assert config.snipara_project_slug == "env-project"
        assert config.snipara_enabled is True
