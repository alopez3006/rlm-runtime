"""RLM CLI entrypoint."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rlm import __version__

app = typer.Typer(
    name="rlm",
    help="Recursive Language Model runtime - execute LLM completions with tool use and sandboxed code execution.",
    add_completion=True,
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(
    prompt: str = typer.Argument(..., help="The prompt to execute"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="Model to use"),
    backend: str = typer.Option("litellm", "--backend", "-b", help="Backend provider"),
    environment: str = typer.Option("local", "--env", "-e", help="REPL environment (local/docker)"),
    max_depth: int = typer.Option(4, "--max-depth", "-d", help="Max recursion depth"),
    token_budget: int = typer.Option(8000, "--token-budget", "-t", help="Token budget"),
    system: str | None = typer.Option(None, "--system", "-s", help="System message"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON"),
    sub_calls: bool = typer.Option(True, "--sub-calls/--no-sub-calls", help="Enable sub-LLM calls"),
    max_sub_calls: int = typer.Option(5, "--max-sub-calls", help="Max sub-calls per turn"),
) -> None:
    """Run a recursive completion with the RLM runtime."""
    from rlm.core.config import load_config
    from rlm.core.orchestrator import RLM
    from rlm.core.types import CompletionOptions

    config = load_config(config_file)
    config.sub_calls_enabled = sub_calls
    config.sub_calls_max_per_turn = max_sub_calls

    try:
        rlm = RLM(
            backend=backend,
            model=model,
            environment=environment,
            config=config,
            verbose=verbose,
        )
    except ImportError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    options = CompletionOptions(
        max_depth=max_depth,
        token_budget=token_budget,
        include_trajectory=verbose,
    )

    if not json_output:
        with console.status("[bold green]Running completion..."):
            result = asyncio.run(rlm.completion(prompt, system=system, options=options))
    else:
        result = asyncio.run(rlm.completion(prompt, system=system, options=options))

    if json_output:
        import json

        console.print(json.dumps(result.to_dict(), indent=2))
    else:
        console.print(Panel(result.response, title="Response", border_style="green"))

        if verbose:
            console.print()
            table = Table(title="Execution Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Trajectory ID", str(result.trajectory_id))
            table.add_row("Total Calls", str(result.total_calls))
            table.add_row("Total Tokens", str(result.total_tokens))
            table.add_row("Tool Calls", str(result.total_tool_calls))
            table.add_row("Duration", f"{result.duration_ms}ms")
            table.add_row("Success", "✓" if result.success else "✗")
            console.print(table)


@app.command()
def agent(
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="Model to use"),
    backend: str = typer.Option("litellm", "--backend", "-b", help="Backend provider"),
    environment: str = typer.Option("local", "--env", "-e", help="REPL environment (local/docker)"),
    max_iterations: int = typer.Option(10, "--max-iterations", "-i", help="Max agent iterations"),
    token_budget: int = typer.Option(50000, "--budget", help="Token budget"),
    cost_limit: float = typer.Option(2.0, "--cost-limit", help="Cost limit in USD"),
    timeout: int = typer.Option(120, "--timeout", help="Timeout in seconds"),
    auto_context: bool = typer.Option(
        True, "--auto-context/--no-auto-context", help="Auto-load Snipara context"
    ),
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run an autonomous agent that iteratively solves a task.

    The agent loops: observe -> think -> act -> terminate.
    It uses REPL for code execution, Snipara for context, and
    sub-LLM calls for delegation. Terminates via FINAL/FINAL_VAR tools.
    """
    from rlm.agent.config import AgentConfig
    from rlm.agent.runner import AgentRunner
    from rlm.core.config import load_config
    from rlm.core.orchestrator import RLM

    config = load_config(config_file)

    try:
        rlm = RLM(
            backend=backend,
            model=model,
            environment=environment,
            config=config,
            verbose=verbose,
        )
    except ImportError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    agent_config = AgentConfig(
        max_iterations=max_iterations,
        token_budget=token_budget,
        cost_limit=cost_limit,
        timeout_seconds=timeout,
        auto_context=auto_context,
        trajectory_log=verbose,
    )

    runner = AgentRunner(rlm, agent_config)

    if not json_output:
        with console.status("[bold green]Agent running..."):
            result = asyncio.run(runner.run(task))
    else:
        result = asyncio.run(runner.run(task))

    if json_output:
        import json

        console.print(json.dumps(result.to_dict(), indent=2))
    else:
        # Answer panel
        border = "green" if result.success else "yellow" if result.forced_termination else "red"
        title = (
            "Answer"
            if result.success
            else "Answer (forced)"
            if result.forced_termination
            else "Error"
        )
        console.print(Panel(result.answer, title=title, border_style=border))

        # Summary table
        console.print()
        table = Table(title="Agent Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Run ID", result.run_id)
        table.add_row("Success", "[green]Yes[/green]" if result.success else "[red]No[/red]")
        table.add_row("Source", result.answer_source)
        table.add_row("Iterations", str(result.iterations))
        table.add_row("Total Tokens", f"{result.total_tokens:,}")
        table.add_row("Total Cost", f"${result.total_cost:.4f}" if result.total_cost else "N/A")
        table.add_row("Duration", f"{result.duration_ms:,}ms")
        if result.forced_termination:
            table.add_row("Forced", "[yellow]Yes[/yellow]")
        console.print(table)

        # Verbose: iteration details
        if verbose and result.iteration_summaries:
            console.print()
            iter_table = Table(title="Iteration Details")
            iter_table.add_column("#", style="dim")
            iter_table.add_column("Tokens", style="yellow")
            iter_table.add_column("Cost", style="green")
            iter_table.add_column("Tools", style="cyan")
            iter_table.add_column("Preview", style="dim", max_width=60)

            for s in result.iteration_summaries:
                iter_table.add_row(
                    str(s["iteration"] + 1),
                    str(s.get("tokens", 0)),
                    f"${s.get('cost', 0) or 0:.4f}",
                    str(s.get("tool_calls", 0)),
                    (s.get("response_preview", "")[:60] or "—"),
                )
            console.print(iter_table)


@app.command()
def init(
    project_dir: Path = typer.Argument(Path("."), help="Project directory"),
    no_snipara: bool = typer.Option(False, "--no-snipara", help="Skip Snipara setup"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
) -> None:
    """Initialize RLM configuration in a project."""
    config_path = project_dir / "rlm.toml"

    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists:[/yellow] {config_path}")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    config_content = """# RLM Runtime Configuration

[rlm]
backend = "litellm"
model = "gpt-4o-mini"
environment = "local"  # or "docker" for isolation
max_depth = 4
max_subcalls = 12
token_budget = 8000
verbose = false

# Docker settings (when environment = "docker")
docker_image = "python:3.11-slim"
docker_cpus = 1.0
docker_memory = "512m"
"""

    if not no_snipara:
        config_content += """
# Snipara context optimization (recommended)
# Get your API key at https://snipara.com/dashboard
# snipara_api_key = "rlm_..."
# snipara_project_slug = "your-project"
"""

    config_path.write_text(config_content)
    console.print(f"[green]✓[/green] Created {config_path}")

    # Create .env.example
    env_example = project_dir / ".env.example"
    if not env_example.exists():
        env_content = """# RLM Runtime Environment Variables

# LLM API Keys (set the ones you need)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Snipara (optional)
SNIPARA_API_KEY=
SNIPARA_PROJECT_SLUG=
"""
        env_example.write_text(env_content)
        console.print(f"[green]✓[/green] Created {env_example}")

    if not no_snipara:
        console.print()
        console.print(
            "[yellow]Tip:[/yellow] Get your Snipara API key at https://snipara.com/dashboard"
        )
        console.print("     Then set snipara_api_key and snipara_project_slug in rlm.toml")


@app.command()
def logs(
    trajectory_id: str | None = typer.Argument(None, help="Trajectory ID to view"),
    log_dir: Path = typer.Option(Path("./logs"), "--dir", "-d", help="Log directory"),
    tail: int = typer.Option(10, "--tail", "-n", help="Number of recent logs to show"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """View trajectory logs."""
    from rlm.logging.trajectory import TrajectoryLogger

    logger = TrajectoryLogger(log_dir=log_dir)

    if trajectory_id:
        events = logger.load_trajectory(trajectory_id)
        if not events:
            console.print(f"[red]Trajectory not found:[/red] {trajectory_id}")
            raise typer.Exit(1)

        if json_output:
            import json

            console.print(json.dumps([e.to_dict() for e in events], indent=2))
        else:
            for event in events:
                console.print()
                console.print(f"[bold cyan]Call {event.call_id}[/bold cyan] (depth={event.depth})")
                console.print(
                    f"  [dim]Prompt:[/dim] {event.prompt[:80]}{'...' if len(event.prompt) > 80 else ''}"
                )
                if event.response:
                    console.print(
                        f"  [dim]Response:[/dim] {event.response[:80]}{'...' if len(event.response) > 80 else ''}"
                    )
                if event.tool_calls:
                    console.print(f"  [dim]Tools:[/dim] {[tc.name for tc in event.tool_calls]}")
                if event.error:
                    console.print(f"  [red]Error:[/red] {event.error}")
                console.print(
                    f"  [dim]Tokens:[/dim] {event.input_tokens} in / {event.output_tokens} out"
                )
                console.print(f"  [dim]Duration:[/dim] {event.duration_ms}ms")
    else:
        trajectories = logger.list_recent(tail)

        if not trajectories:
            console.print("[dim]No trajectories found[/dim]")
            return

        if json_output:
            import json

            console.print(json.dumps(trajectories, indent=2))
        else:
            table = Table(title="Recent Trajectories")
            table.add_column("ID", style="cyan")
            table.add_column("Timestamp", style="dim")
            table.add_column("Calls", style="green")
            table.add_column("Tokens", style="yellow")
            table.add_column("Duration", style="magenta")

            for t in trajectories:
                table.add_row(
                    t["id"][:8] + "...",
                    t["timestamp"][:19],
                    str(t["calls"]),
                    str(t["tokens"]),
                    f"{t['duration_ms']}ms",
                )

            console.print(table)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"rlm-runtime {__version__}")


@app.command("mcp-serve")
def mcp_serve() -> None:
    """Start the MCP server for Claude Desktop/Code integration.

    This runs the RLM MCP server using stdio transport. Configure it in your
    Claude settings:

    For Claude Desktop (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "rlm": {
          "command": "rlm",
          "args": ["mcp-serve"]
        }
      }
    }

    For Claude Code (~/.claude/claude_code_config.json):
    {
      "mcpServers": {
        "rlm": {
          "command": "rlm",
          "args": ["mcp-serve"]
        }
      }
    }
    """
    try:
        from rlm.mcp import run_server

        run_server()
    except ImportError as e:
        console.print("[red]Error:[/red] MCP dependencies not installed")
        console.print("Install with: pip install rlm-runtime[mcp]")
        console.print(f"Details: {e}")
        raise typer.Exit(1) from None


@app.command()
def visualize(
    log_dir: Path = typer.Option(Path("./logs"), "--dir", "-d", help="Log directory"),
    port: int = typer.Option(8501, "--port", "-p", help="Port to run on"),
) -> None:
    """Launch the trajectory visualizer web UI.

    Opens an interactive Streamlit dashboard to explore RLM execution
    trajectories, view token usage, and debug completions.
    """
    try:
        import os
        import sys

        import streamlit.web.cli as stcli

        from rlm.visualizer import app as viz_app

        # Set log directory as environment variable for the app
        os.environ["RLM_LOG_DIR"] = str(log_dir.absolute())

        console.print(f"[green]Starting visualizer on port {port}...[/green]")
        console.print(f"[dim]Log directory: {log_dir}[/dim]")
        console.print()
        console.print(f"Open http://localhost:{port} in your browser")
        console.print("[dim]Press Ctrl+C to stop[/dim]")

        sys.argv = [
            "streamlit",
            "run",
            viz_app.__file__,
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ]
        sys.exit(stcli.main())

    except ImportError as e:
        console.print("[red]Error:[/red] Visualizer dependencies not installed")
        console.print("Install with: pip install rlm-runtime[visualizer]")
        console.print(f"Details: {e}")
        raise typer.Exit(1) from None


@app.command()
def doctor() -> None:
    """Check RLM runtime setup and dependencies."""
    console.print("[bold]RLM Runtime Doctor[/bold]")
    console.print()

    checks: list[tuple[str, bool, str]] = []

    # Check Python version
    import sys

    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append(("Python version", py_ok, py_version))

    # Check required packages
    required = ["litellm", "RestrictedPython", "pydantic", "structlog", "typer"]
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
            checks.append((f"Package: {pkg}", True, "installed"))
        except ImportError:
            checks.append((f"Package: {pkg}", False, "missing"))

    # Check optional packages
    optional = [
        ("docker", "docker"),
        ("snipara_mcp", "snipara-mcp"),
        ("mcp", "mcp"),
        ("streamlit", "streamlit"),
        ("plotly", "plotly"),
    ]
    for module, pkg in optional:
        try:
            __import__(module)
            checks.append((f"Optional: {pkg}", True, "installed"))
        except ImportError:
            checks.append((f"Optional: {pkg}", None, "not installed"))  # type: ignore

    # Check Docker
    try:
        import docker

        client = docker.from_env()  # type: ignore[attr-defined]
        client.ping()
        checks.append(("Docker daemon", True, "running"))
    except Exception as e:
        checks.append(("Docker daemon", False, str(e)[:30]))

    # Check config file
    config_path = Path("rlm.toml")
    if config_path.exists():
        checks.append(("Config file", True, str(config_path)))
    else:
        checks.append(("Config file", None, "not found (optional)"))  # type: ignore

    # Check API keys
    import os

    api_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "SNIPARA_API_KEY"]
    for key in api_keys:
        if os.environ.get(key):
            checks.append((f"Env: {key}", True, "set"))
        else:
            checks.append((f"Env: {key}", None, "not set"))  # type: ignore

    # Print results
    table = Table()
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for name, ok, details in checks:
        if ok is True:
            status = "[green]✓[/green]"
        elif ok is False:
            status = "[red]✗[/red]"
        else:
            status = "[yellow]○[/yellow]"
        table.add_row(name, status, details)

    console.print(table)

    # Summary
    failures = sum(1 for _, ok, _ in checks if ok is False)
    if failures:
        console.print(f"\n[red]{failures} issue(s) found[/red]")
        raise typer.Exit(1)
    else:
        console.print("\n[green]All checks passed![/green]")


if __name__ == "__main__":
    app()
