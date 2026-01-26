"""Docker-based REPL sandbox with strong isolation."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

try:
    import docker
    from docker.errors import ContainerError, ImageNotFound

    DOCKER_AVAILABLE = True
except ImportError:
    docker = None  # type: ignore[assignment]
    DOCKER_AVAILABLE = False

    # Provide stub classes for type checking and testing
    class ContainerError(Exception):  # type: ignore[no-redef]
        """Stub for docker.errors.ContainerError when docker not installed."""

        def __init__(
            self,
            container: object = None,
            exit_status: int = 1,
            command: str = "",
            image: str = "",
            stderr: bytes = b"",
        ):
            self.container = container
            self.exit_status = exit_status
            self.command = command
            self.image = image
            self.stderr = stderr
            super().__init__(f"Container error: {stderr.decode()}")

    class ImageNotFound(Exception):  # type: ignore[no-redef]
        """Stub for docker.errors.ImageNotFound when docker not installed."""

        pass


from rlm.core.types import REPLResult
from rlm.repl.base import BaseREPL
from rlm.repl.safety import MAX_EXECUTION_TIME, MAX_MEMORY_MB, truncate_output


class DockerREPL(BaseREPL):
    """Docker container REPL with strong isolation.

    Executes code in isolated Docker containers with:
    - Network disabled by default
    - Resource limits (CPU, memory)
    - Read-only filesystem mounts
    - Automatic cleanup

    This is the recommended REPL for untrusted inputs.

    Example:
        ```python
        repl = DockerREPL(
            image="python:3.11-slim",
            cpus=1.0,
            memory="512m",
        )
        result = await repl.execute("print(sum(range(100)))")
        print(result.output)  # "4950\\n"
        ```
    """

    def __init__(
        self,
        image: str = "python:3.11-slim",
        cpus: float = 1.0,
        memory: str = f"{MAX_MEMORY_MB}m",
        timeout: int = MAX_EXECUTION_TIME,
        network_disabled: bool = True,
        workdir_mount: Path | None = None,
    ):
        """Initialize the Docker REPL.

        Args:
            image: Docker image to use
            cpus: CPU limit (e.g., 1.0 = 1 CPU)
            memory: Memory limit (e.g., "512m", "1g")
            timeout: Execution timeout in seconds
            network_disabled: Disable network access (recommended)
            workdir_mount: Optional directory to mount read-only at /workspace
        """
        if not DOCKER_AVAILABLE:
            raise ImportError(
                "Docker support requires 'docker' package. "
                "Install with: pip install rlm-runtime[docker]"
            )

        self.image = image
        self.cpus = cpus
        self.memory = memory
        self.timeout = timeout
        self.network_disabled = network_disabled
        self.workdir_mount = workdir_mount
        self._client: docker.DockerClient | None = None  # type: ignore[name-defined]
        self._context: dict[str, Any] = {}

    def _get_client(self) -> docker.DockerClient:  # type: ignore[name-defined]
        """Get or create Docker client."""
        if self._client is None:
            self._client = docker.from_env()  # type: ignore[attr-defined]
        return self._client

    async def _ensure_image(self) -> None:
        """Ensure the Docker image exists, pulling if needed."""
        client = self._get_client()
        try:
            client.images.get(self.image)
        except ImageNotFound:
            # Pull image asynchronously
            await asyncio.to_thread(client.images.pull, self.image)

    def _create_script(self, code: str) -> str:
        """Create the Python script to run in the container."""
        context_json = json.dumps(self._context)

        return f"""
import json
import sys

# Inject context
context = json.loads({context_json!r})
result = None

# Capture stdout
import io
_stdout = io.StringIO()
_original_stdout = sys.stdout
sys.stdout = _stdout

try:
    # User code
{self._indent_code(code)}

except Exception as e:
    print(f"{{type(e).__name__}}: {{e}}", file=sys.stderr)
    sys.exit(1)
finally:
    sys.stdout = _original_stdout

# Output
output = _stdout.getvalue()
if output:
    print(output, end="")
if result is not None:
    print(f"result = {{result!r}}")
"""

    def _indent_code(self, code: str, spaces: int = 4) -> str:
        """Indent code for inclusion in the script."""
        indent = " " * spaces
        return "\n".join(indent + line for line in code.splitlines())

    async def execute(self, code: str, timeout: int | None = None) -> REPLResult:
        """Execute code in a Docker container.

        Args:
            code: Python code to execute
            timeout: Optional timeout override

        Returns:
            REPLResult with output, error, and timing
        """
        timeout = timeout or self.timeout
        client = self._get_client()

        # Ensure image exists
        await self._ensure_image()

        # Create temporary script file
        script_content = self._create_script(code)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            script_path = Path(f.name)

        try:
            # Build volumes
            volumes: dict[str, dict[str, str]] = {
                str(script_path): {"bind": "/code/script.py", "mode": "ro"},
            }
            if self.workdir_mount and self.workdir_mount.exists():
                volumes[str(self.workdir_mount)] = {"bind": "/workspace", "mode": "ro"}

            # Run container
            start_time = asyncio.get_event_loop().time()

            try:
                output = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.containers.run,
                        self.image,
                        command=["python", "/code/script.py"],
                        volumes=volumes,
                        working_dir="/workspace" if self.workdir_mount else "/code",
                        network_disabled=self.network_disabled,
                        mem_limit=self.memory,
                        cpu_quota=int(self.cpus * 100000),
                        cpu_period=100000,
                        remove=True,
                        stdout=True,
                        stderr=True,
                    ),
                    timeout=timeout,
                )

                execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                output_str = output.decode("utf-8") if isinstance(output, bytes) else str(output)
                output_str, truncated = truncate_output(output_str)

                return REPLResult(
                    output=output_str,
                    error=None,
                    execution_time_ms=execution_time_ms,
                    truncated=truncated,
                )

            except ContainerError as e:
                execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                stderr = e.stderr.decode("utf-8") if e.stderr else str(e)
                return REPLResult(
                    output="",
                    error=stderr.strip(),
                    execution_time_ms=execution_time_ms,
                )

            except asyncio.TimeoutError:
                return REPLResult(
                    output="",
                    error=f"Execution timed out after {timeout}s",
                    execution_time_ms=timeout * 1000,
                )

        finally:
            # Cleanup temp file
            script_path.unlink(missing_ok=True)

    def get_context(self) -> dict[str, Any]:
        """Get the current context."""
        return self._context.copy()

    def set_context(self, key: str, value: Any) -> None:
        """Set a value in the context.

        Note: Values must be JSON-serializable for Docker REPL.
        """
        # Validate JSON-serializable
        try:
            json.dumps({key: value})
        except (TypeError, ValueError) as e:
            raise ValueError(f"Context value must be JSON-serializable: {e}") from e

        self._context[key] = value

    def clear_context(self) -> None:
        """Clear the context."""
        self._context.clear()

    def cleanup(self) -> None:
        """Cleanup Docker client resources."""
        if self._client:
            self._client.close()
            self._client = None
