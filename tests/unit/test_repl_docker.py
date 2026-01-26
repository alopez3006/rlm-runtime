"""Tests for Docker REPL sandbox."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestDockerREPLInit:
    """Tests for DockerREPL initialization."""

    def test_raises_import_error_without_docker(self):
        """Should raise ImportError when docker package not available."""
        with patch.dict("sys.modules", {"docker": None}):
            with patch("rlm.repl.docker.DOCKER_AVAILABLE", False):
                from rlm.repl.docker import DockerREPL

                with pytest.raises(ImportError) as exc_info:
                    DockerREPL()
                assert "docker" in str(exc_info.value).lower()

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_default_settings(self, mock_docker):
        """Should use default settings."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()

        assert repl.image == "python:3.11-slim"
        assert repl.cpus == 1.0
        assert repl.network_disabled is True

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_custom_settings(self, mock_docker):
        """Should accept custom settings."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL(
            image="python:3.12",
            cpus=2.0,
            memory="1g",
            timeout=60,
            network_disabled=False,
        )

        assert repl.image == "python:3.12"
        assert repl.cpus == 2.0
        assert repl.memory == "1g"
        assert repl.timeout == 60
        assert repl.network_disabled is False

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_workdir_mount(self, mock_docker, tmp_path):
        """Should accept workdir mount."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL(workdir_mount=tmp_path)

        assert repl.workdir_mount == tmp_path


class TestDockerREPLClient:
    """Tests for Docker client management."""

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_lazy_client_creation(self, mock_docker):
        """Should create client lazily."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        assert repl._client is None

        # Access client
        repl._get_client()
        mock_docker.from_env.assert_called_once()

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_client_reuse(self, mock_docker):
        """Should reuse existing client."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        repl = DockerREPL()
        client1 = repl._get_client()
        client2 = repl._get_client()

        assert client1 is client2
        mock_docker.from_env.assert_called_once()

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_cleanup(self, mock_docker):
        """Should close client on cleanup."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        repl = DockerREPL()
        repl._get_client()
        repl.cleanup()

        mock_client.close.assert_called_once()
        assert repl._client is None


class TestDockerREPLContext:
    """Tests for Docker REPL context management."""

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_empty_context_initially(self, mock_docker):
        """Should start with empty context."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        assert repl.get_context() == {}

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_set_context(self, mock_docker):
        """Should set context values."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        repl.set_context("key", "value")
        repl.set_context("number", 42)

        context = repl.get_context()
        assert context["key"] == "value"
        assert context["number"] == 42

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_clear_context(self, mock_docker):
        """Should clear context."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        repl.set_context("key", "value")
        repl.clear_context()

        assert repl.get_context() == {}

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_get_context_returns_copy(self, mock_docker):
        """Should return a copy of context."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        repl.set_context("key", "value")

        context = repl.get_context()
        context["new_key"] = "new_value"

        assert "new_key" not in repl.get_context()

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_set_context_requires_json_serializable(self, mock_docker):
        """Should reject non-JSON-serializable values."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()

        # Lambda is not JSON serializable
        with pytest.raises(ValueError) as exc_info:
            repl.set_context("func", lambda x: x)
        assert "JSON" in str(exc_info.value)


class TestDockerREPLScriptCreation:
    """Tests for script creation."""

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_creates_script_with_code(self, mock_docker):
        """Should create script containing user code."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        script = repl._create_script("print('hello')")

        assert "print('hello')" in script

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_creates_script_with_context(self, mock_docker):
        """Should inject context into script."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        repl.set_context("data", [1, 2, 3])
        script = repl._create_script("print(context)")

        # Context should be JSON-encoded in script
        assert "json.loads" in script

    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    def test_indent_code(self, mock_docker):
        """Should properly indent code."""
        from rlm.repl.docker import DockerREPL

        repl = DockerREPL()
        code = "line1\nline2"
        indented = repl._indent_code(code, spaces=4)

        assert indented == "    line1\n    line2"


class TestDockerREPLExecution:
    """Tests for code execution."""

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_execute_success(self, mock_docker):
        """Should return success result."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.return_value = b"hello\n"

        repl = DockerREPL()
        result = await repl.execute("print('hello')")

        assert result.output == "hello\n"
        assert result.error is None

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_execute_with_container_error(self, mock_docker):
        """Should handle container errors."""
        from rlm.repl.docker import ContainerError, DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        error = ContainerError(
            container=MagicMock(),
            exit_status=1,
            command="python",
            image="python:3.11",
            stderr=b"NameError: name 'x' is not defined",
        )
        mock_client.containers.run.side_effect = error

        repl = DockerREPL()
        result = await repl.execute("print(x)")

        assert result.error is not None
        assert "NameError" in result.error

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_execute_timeout(self, mock_docker):
        """Should handle execution timeout."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        # Make containers.run block forever
        async def slow_run(*args, **kwargs):
            await asyncio.sleep(10)
            return b"done"

        mock_client.containers.run.side_effect = asyncio.TimeoutError()

        repl = DockerREPL(timeout=1)
        result = await repl.execute("import time; time.sleep(10)")

        assert result.error is not None
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_execute_pulls_missing_image(self, mock_docker):
        """Should pull image if not found."""
        from rlm.repl.docker import DockerREPL, ImageNotFound

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.side_effect = ImageNotFound("not found")
        mock_client.containers.run.return_value = b"output"

        repl = DockerREPL()
        await repl.execute("print('test')")

        mock_client.images.pull.assert_called_once_with("python:3.11-slim")

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_execute_with_workdir_mount(self, mock_docker, tmp_path):
        """Should mount workdir when specified."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.return_value = b"output"

        repl = DockerREPL(workdir_mount=tmp_path)
        await repl.execute("print('test')")

        # Check that volumes include workdir
        call_kwargs = mock_client.containers.run.call_args.kwargs
        volumes = call_kwargs.get("volumes", {})
        assert str(tmp_path) in volumes


class TestDockerREPLResourceLimits:
    """Tests for resource limit configuration."""

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_memory_limit_applied(self, mock_docker):
        """Should apply memory limit."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.return_value = b"output"

        repl = DockerREPL(memory="256m")
        await repl.execute("print('test')")

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["mem_limit"] == "256m"

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_cpu_limit_applied(self, mock_docker):
        """Should apply CPU limit."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.return_value = b"output"

        repl = DockerREPL(cpus=0.5)
        await repl.execute("print('test')")

        call_kwargs = mock_client.containers.run.call_args.kwargs
        # CPU quota = cpus * 100000
        assert call_kwargs["cpu_quota"] == 50000
        assert call_kwargs["cpu_period"] == 100000

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_network_disabled(self, mock_docker):
        """Should disable network by default."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.return_value = b"output"

        repl = DockerREPL()
        await repl.execute("print('test')")

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["network_disabled"] is True

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_network_enabled(self, mock_docker):
        """Should allow network when configured."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.return_value = b"output"

        repl = DockerREPL(network_disabled=False)
        await repl.execute("print('test')")

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["network_disabled"] is False

    @pytest.mark.asyncio
    @patch("rlm.repl.docker.DOCKER_AVAILABLE", True)
    @patch("rlm.repl.docker.docker")
    async def test_container_auto_removed(self, mock_docker):
        """Should auto-remove container after execution."""
        from rlm.repl.docker import DockerREPL

        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.return_value = b"output"

        repl = DockerREPL()
        await repl.execute("print('test')")

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["remove"] is True
