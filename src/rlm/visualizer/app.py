"""RLM Trajectory Visualizer - Streamlit Application."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def load_trajectory(log_path: Path) -> dict[str, Any]:
    """Load a trajectory from a JSONL file."""
    metadata = None
    events = []

    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("_type") == "trajectory_metadata":
                metadata = data
            else:
                events.append(data)

    return {"metadata": metadata, "events": events}


def list_trajectories(log_dir: Path) -> list[dict[str, Any]]:
    """List all trajectories in the log directory."""
    trajectories = []

    for log_path in sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(log_path, encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    data = json.loads(first_line)
                    if data.get("_type") == "trajectory_metadata":
                        trajectories.append({
                            "id": data["trajectory_id"],
                            "timestamp": data["timestamp"],
                            "calls": data["event_count"],
                            "tokens": data["total_tokens"],
                            "duration_ms": data["total_duration_ms"],
                            "path": str(log_path),
                        })
        except (json.JSONDecodeError, KeyError):
            continue

    return trajectories


def render_event_tree(events: list[dict[str, Any]]) -> go.Figure:
    """Render a tree visualization of the trajectory events."""
    if not events:
        return go.Figure()

    # Build node positions based on depth and order
    nodes = []
    edges = []
    node_map = {}

    for i, event in enumerate(events):
        call_id = event["call_id"]
        parent_id = event.get("parent_call_id")
        depth = event["depth"]

        node_map[call_id] = i
        nodes.append({
            "id": call_id,
            "depth": depth,
            "index": i,
            "label": f"Call {i+1}",
            "tokens": event.get("input_tokens", 0) + event.get("output_tokens", 0),
            "duration": event.get("duration_ms", 0),
            "tool_calls": len(event.get("tool_calls", [])),
            "has_error": event.get("error") is not None,
        })

        if parent_id and parent_id in node_map:
            edges.append((node_map[parent_id], i))

    # Calculate positions
    max_depth = max(n["depth"] for n in nodes) + 1
    depth_counts = dict.fromkeys(range(max_depth), 0)
    positions = []

    for node in nodes:
        x = depth_counts[node["depth"]]
        y = -node["depth"]
        positions.append((x, y))
        depth_counts[node["depth"]] += 1

    # Create figure
    fig = go.Figure()

    # Add edges
    for parent_idx, child_idx in edges:
        x0, y0 = positions[parent_idx]
        x1, y1 = positions[child_idx]
        fig.add_trace(go.Scatter(
            x=[x0, x1],
            y=[y0, y1],
            mode="lines",
            line=dict(color="#888", width=1),
            hoverinfo="none",
            showlegend=False,
        ))

    # Add nodes
    colors = ["#ff6b6b" if n["has_error"] else "#4ecdc4" for n in nodes]
    sizes = [max(20, min(50, n["tokens"] / 100)) for n in nodes]

    fig.add_trace(go.Scatter(
        x=[p[0] for p in positions],
        y=[p[1] for p in positions],
        mode="markers+text",
        marker=dict(size=sizes, color=colors, line=dict(width=2, color="white")),
        text=[n["label"] for n in nodes],
        textposition="top center",
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Tokens: %{customdata[0]}<br>"
            "Duration: %{customdata[1]}ms<br>"
            "Tool calls: %{customdata[2]}<br>"
            "<extra></extra>"
        ),
        customdata=[[n["tokens"], n["duration"], n["tool_calls"]] for n in nodes],
        showlegend=False,
    ))

    fig.update_layout(
        title="Execution Tree",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    return fig


def render_token_chart(events: list[dict[str, Any]]) -> go.Figure:
    """Render a chart showing token usage across calls."""
    if not events:
        return go.Figure()

    calls = list(range(1, len(events) + 1))
    input_tokens = [e.get("input_tokens", 0) for e in events]
    output_tokens = [e.get("output_tokens", 0) for e in events]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=calls,
        y=input_tokens,
        name="Input Tokens",
        marker_color="#3498db",
    ))

    fig.add_trace(go.Bar(
        x=calls,
        y=output_tokens,
        name="Output Tokens",
        marker_color="#2ecc71",
    ))

    fig.update_layout(
        title="Token Usage per Call",
        xaxis_title="Call Number",
        yaxis_title="Tokens",
        barmode="stack",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    return fig


def render_duration_chart(events: list[dict[str, Any]]) -> go.Figure:
    """Render a chart showing duration across calls."""
    if not events:
        return go.Figure()

    calls = list(range(1, len(events) + 1))
    durations = [e.get("duration_ms", 0) for e in events]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=calls,
        y=durations,
        name="Duration",
        marker_color="#9b59b6",
    ))

    fig.update_layout(
        title="Duration per Call (ms)",
        xaxis_title="Call Number",
        yaxis_title="Duration (ms)",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
    )

    return fig


def render_event_detail(event: dict[str, Any], index: int) -> None:
    """Render detailed view of a single event."""
    with st.expander(f"Call {index + 1} (Depth {event['depth']})", expanded=index == 0):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Input Tokens", event.get("input_tokens", 0))
        with col2:
            st.metric("Output Tokens", event.get("output_tokens", 0))
        with col3:
            st.metric("Duration", f"{event.get('duration_ms', 0)}ms")
        with col4:
            st.metric("Tool Calls", len(event.get("tool_calls", [])))

        # Prompt
        st.markdown("**Prompt:**")
        prompt = event.get("prompt", "")
        if len(prompt) > 500:
            st.code(prompt[:500] + "...", language="text")
            if st.button("Show full prompt", key=f"prompt_{index}"):
                st.code(prompt, language="text")
        else:
            st.code(prompt, language="text")

        # Response
        if event.get("response"):
            st.markdown("**Response:**")
            response = event["response"]
            if len(response) > 500:
                st.code(response[:500] + "...", language="text")
                if st.button("Show full response", key=f"response_{index}"):
                    st.code(response, language="text")
            else:
                st.code(response, language="text")

        # Tool calls
        if event.get("tool_calls"):
            st.markdown("**Tool Calls:**")
            for tc in event["tool_calls"]:
                st.markdown(f"- `{tc['name']}`: {json.dumps(tc['arguments'], indent=2)}")

        # Tool results
        if event.get("tool_results"):
            st.markdown("**Tool Results:**")
            for tr in event["tool_results"]:
                status = "error" if tr.get("is_error") else "success"
                st.markdown(f"- [{status}] {tr['content'][:200]}...")

        # Error
        if event.get("error"):
            st.error(f"Error: {event['error']}")


def main() -> None:
    """Main Streamlit application."""
    st.set_page_config(
        page_title="RLM Trajectory Visualizer",
        page_icon="🔄",
        layout="wide",
    )

    st.title("🔄 RLM Trajectory Visualizer")

    # Sidebar - Configuration
    with st.sidebar:
        st.header("Configuration")

        log_dir = st.text_input(
            "Log Directory",
            value="./logs",
            help="Path to the directory containing trajectory logs",
        )
        log_path = Path(log_dir)

        if not log_path.exists():
            st.warning(f"Directory not found: {log_dir}")
            st.info("Run some completions first to generate trajectory logs.")
            return

        st.markdown("---")

        # List trajectories
        st.header("Trajectories")
        trajectories = list_trajectories(log_path)

        if not trajectories:
            st.info("No trajectories found in the log directory.")
            return

        # Trajectory selector
        trajectory_options = {
            f"{t['timestamp'][:19]} ({t['calls']} calls, {t['tokens']} tokens)": t
            for t in trajectories
        }

        selected_label = st.selectbox(
            "Select Trajectory",
            options=list(trajectory_options.keys()),
        )

        selected = trajectory_options[selected_label]

        st.markdown("---")
        st.markdown(f"**ID:** `{selected['id'][:8]}...`")
        st.markdown(f"**Duration:** {selected['duration_ms']}ms")

    # Main content
    if selected:
        trajectory = load_trajectory(Path(selected["path"]))
        events = trajectory["events"]
        metadata = trajectory["metadata"]

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Calls", len(events))
        with col2:
            st.metric("Total Tokens", metadata["total_tokens"] if metadata else sum(
                e.get("input_tokens", 0) + e.get("output_tokens", 0) for e in events
            ))
        with col3:
            st.metric("Total Duration", f"{metadata['total_duration_ms'] if metadata else sum(e.get('duration_ms', 0) for e in events)}ms")
        with col4:
            errors = sum(1 for e in events if e.get("error"))
            st.metric("Errors", errors)

        st.markdown("---")

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Overview", "🌳 Execution Tree", "📋 Event Details"])

        with tab1:
            col1, col2 = st.columns(2)

            with col1:
                st.plotly_chart(render_token_chart(events), use_container_width=True)

            with col2:
                st.plotly_chart(render_duration_chart(events), use_container_width=True)

            # Tool usage breakdown
            st.subheader("Tool Usage")
            tool_counts: dict[str, int] = {}
            for event in events:
                for tc in event.get("tool_calls", []):
                    tool_counts[tc["name"]] = tool_counts.get(tc["name"], 0) + 1

            if tool_counts:
                fig = px.pie(
                    values=list(tool_counts.values()),
                    names=list(tool_counts.keys()),
                    title="Tool Call Distribution",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No tool calls in this trajectory")

        with tab2:
            st.plotly_chart(render_event_tree(events), use_container_width=True)

            st.markdown("""
            **Legend:**
            - 🟢 Green nodes: Successful calls
            - 🔴 Red nodes: Calls with errors
            - Node size: Relative token usage
            """)

        with tab3:
            for i, event in enumerate(events):
                render_event_detail(event, i)

        # Raw JSON view
        with st.expander("Raw JSON"):
            st.json(trajectory)


if __name__ == "__main__":
    main()
