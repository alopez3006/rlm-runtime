"""Tests for RLM Trajectory Visualizer."""

from unittest.mock import MagicMock, patch


class TestLoadTrajectory:
    """Tests for load_trajectory function."""

    def test_loads_trajectory_with_metadata(self, tmp_path):
        """Should load trajectory with metadata and events."""
        from rlm.visualizer.app import load_trajectory

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            '{"_type": "trajectory_metadata", "trajectory_id": "abc123", "event_count": 2}\n'
            '{"call_id": "call1", "depth": 0, "prompt": "test"}\n'
            '{"call_id": "call2", "depth": 1, "prompt": "test2"}\n'
        )

        result = load_trajectory(log_file)

        assert result["metadata"]["_type"] == "trajectory_metadata"
        assert result["metadata"]["trajectory_id"] == "abc123"
        assert len(result["events"]) == 2
        assert result["events"][0]["call_id"] == "call1"
        assert result["events"][1]["call_id"] == "call2"

    def test_loads_trajectory_without_metadata(self, tmp_path):
        """Should load trajectory without metadata."""
        from rlm.visualizer.app import load_trajectory

        log_file = tmp_path / "test.jsonl"
        log_file.write_text('{"call_id": "call1", "depth": 0}\n{"call_id": "call2", "depth": 1}\n')

        result = load_trajectory(log_file)

        assert result["metadata"] is None
        assert len(result["events"]) == 2

    def test_skips_empty_lines(self, tmp_path):
        """Should skip empty lines in the file."""
        from rlm.visualizer.app import load_trajectory

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            '{"call_id": "call1", "depth": 0}\n\n   \n{"call_id": "call2", "depth": 1}\n'
        )

        result = load_trajectory(log_file)

        assert len(result["events"]) == 2


class TestListTrajectories:
    """Tests for list_trajectories function."""

    def test_lists_trajectories_sorted_by_mtime(self, tmp_path):
        """Should list trajectories sorted by modification time."""
        import time

        from rlm.visualizer.app import list_trajectories

        # Create files with different mtimes
        log1 = tmp_path / "old.jsonl"
        log1.write_text(
            '{"_type": "trajectory_metadata", "trajectory_id": "old", "timestamp": "2024-01-01T00:00:00", "event_count": 1, "total_tokens": 100, "total_duration_ms": 500}\n'
        )

        time.sleep(0.01)  # Ensure different mtime

        log2 = tmp_path / "new.jsonl"
        log2.write_text(
            '{"_type": "trajectory_metadata", "trajectory_id": "new", "timestamp": "2024-01-02T00:00:00", "event_count": 2, "total_tokens": 200, "total_duration_ms": 1000}\n'
        )

        result = list_trajectories(tmp_path)

        assert len(result) == 2
        assert result[0]["id"] == "new"  # Newer file first
        assert result[1]["id"] == "old"

    def test_extracts_trajectory_metadata(self, tmp_path):
        """Should extract trajectory metadata correctly."""
        from rlm.visualizer.app import list_trajectories

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(
            '{"_type": "trajectory_metadata", "trajectory_id": "test123", "timestamp": "2024-01-15T12:00:00", "event_count": 5, "total_tokens": 1500, "total_duration_ms": 2500}\n'
        )

        result = list_trajectories(tmp_path)

        assert len(result) == 1
        assert result[0]["id"] == "test123"
        assert result[0]["timestamp"] == "2024-01-15T12:00:00"
        assert result[0]["calls"] == 5
        assert result[0]["tokens"] == 1500
        assert result[0]["duration_ms"] == 2500
        assert result[0]["path"] == str(log_file)

    def test_skips_invalid_json(self, tmp_path):
        """Should skip files with invalid JSON."""
        from rlm.visualizer.app import list_trajectories

        # Valid file
        valid = tmp_path / "valid.jsonl"
        valid.write_text(
            '{"_type": "trajectory_metadata", "trajectory_id": "valid", "timestamp": "2024-01-01", "event_count": 1, "total_tokens": 100, "total_duration_ms": 500}\n'
        )

        # Invalid file
        invalid = tmp_path / "invalid.jsonl"
        invalid.write_text("not valid json\n")

        result = list_trajectories(tmp_path)

        assert len(result) == 1
        assert result[0]["id"] == "valid"

    def test_skips_missing_metadata(self, tmp_path):
        """Should skip files without trajectory metadata."""
        from rlm.visualizer.app import list_trajectories

        # File with metadata
        with_meta = tmp_path / "with_meta.jsonl"
        with_meta.write_text(
            '{"_type": "trajectory_metadata", "trajectory_id": "has_meta", "timestamp": "2024-01-01", "event_count": 1, "total_tokens": 100, "total_duration_ms": 500}\n'
        )

        # File without metadata
        no_meta = tmp_path / "no_meta.jsonl"
        no_meta.write_text('{"call_id": "call1", "depth": 0}\n')

        result = list_trajectories(tmp_path)

        assert len(result) == 1
        assert result[0]["id"] == "has_meta"

    def test_returns_empty_for_empty_directory(self, tmp_path):
        """Should return empty list for empty directory."""
        from rlm.visualizer.app import list_trajectories

        result = list_trajectories(tmp_path)

        assert result == []


class TestRenderEventTree:
    """Tests for render_event_tree function."""

    def test_returns_empty_figure_for_no_events(self):
        """Should return empty figure when no events."""
        import plotly.graph_objects as go

        from rlm.visualizer.app import render_event_tree

        result = render_event_tree([])

        assert isinstance(result, go.Figure)

    def test_creates_figure_with_nodes(self):
        """Should create figure with nodes for events."""
        import plotly.graph_objects as go

        from rlm.visualizer.app import render_event_tree

        events = [
            {
                "call_id": "call1",
                "parent_call_id": None,
                "depth": 0,
                "input_tokens": 100,
                "output_tokens": 50,
                "duration_ms": 500,
                "tool_calls": [],
                "error": None,
            },
            {
                "call_id": "call2",
                "parent_call_id": "call1",
                "depth": 1,
                "input_tokens": 80,
                "output_tokens": 40,
                "duration_ms": 300,
                "tool_calls": [{"name": "test"}],
                "error": None,
            },
        ]

        result = render_event_tree(events)

        assert isinstance(result, go.Figure)
        # Should have scatter traces for nodes and edges
        assert len(result.data) >= 1

    def test_marks_error_nodes_red(self):
        """Should mark nodes with errors in red."""
        from rlm.visualizer.app import render_event_tree

        events = [
            {
                "call_id": "call1",
                "parent_call_id": None,
                "depth": 0,
                "input_tokens": 100,
                "output_tokens": 50,
                "duration_ms": 500,
                "tool_calls": [],
                "error": "Some error",  # Has error
            },
        ]

        result = render_event_tree(events)

        # Check that red color is used for error nodes
        # The scatter trace for nodes should have red color
        node_trace = result.data[-1]  # Last trace is the nodes
        assert "#ff6b6b" in node_trace.marker.color  # Red for error


class TestRenderTokenChart:
    """Tests for render_token_chart function."""

    def test_returns_empty_figure_for_no_events(self):
        """Should return empty figure when no events."""
        import plotly.graph_objects as go

        from rlm.visualizer.app import render_token_chart

        result = render_token_chart([])

        assert isinstance(result, go.Figure)

    def test_creates_stacked_bar_chart(self):
        """Should create stacked bar chart for token usage."""
        import plotly.graph_objects as go

        from rlm.visualizer.app import render_token_chart

        events = [
            {"input_tokens": 100, "output_tokens": 50},
            {"input_tokens": 80, "output_tokens": 40},
        ]

        result = render_token_chart(events)

        assert isinstance(result, go.Figure)
        # Should have two bar traces (input and output)
        assert len(result.data) == 2
        assert result.data[0].name == "Input Tokens"
        assert result.data[1].name == "Output Tokens"

    def test_handles_missing_token_values(self):
        """Should handle events without token values."""
        from rlm.visualizer.app import render_token_chart

        events = [
            {"input_tokens": 100},  # Missing output_tokens
            {},  # Missing both
        ]

        result = render_token_chart(events)

        # Should not raise and should use 0 as default
        assert len(result.data) == 2


class TestRenderDurationChart:
    """Tests for render_duration_chart function."""

    def test_returns_empty_figure_for_no_events(self):
        """Should return empty figure when no events."""
        import plotly.graph_objects as go

        from rlm.visualizer.app import render_duration_chart

        result = render_duration_chart([])

        assert isinstance(result, go.Figure)

    def test_creates_bar_chart(self):
        """Should create bar chart for durations."""
        import plotly.graph_objects as go

        from rlm.visualizer.app import render_duration_chart

        events = [
            {"duration_ms": 500},
            {"duration_ms": 300},
            {"duration_ms": 700},
        ]

        result = render_duration_chart(events)

        assert isinstance(result, go.Figure)
        assert len(result.data) == 1
        assert result.data[0].name == "Duration"

    def test_handles_missing_duration_values(self):
        """Should handle events without duration values."""
        from rlm.visualizer.app import render_duration_chart

        events = [
            {"duration_ms": 500},
            {},  # Missing duration_ms
        ]

        result = render_duration_chart(events)

        # Should not raise and should use 0 as default
        assert len(result.data) == 1


class TestRenderEventDetail:
    """Tests for render_event_detail function."""

    @patch("streamlit.expander")
    @patch("streamlit.columns")
    @patch("streamlit.metric")
    @patch("streamlit.markdown")
    @patch("streamlit.code")
    @patch("streamlit.button")
    @patch("streamlit.error")
    def test_renders_basic_event(
        self,
        mock_error,
        mock_button,
        mock_code,
        mock_markdown,
        mock_metric,
        mock_columns,
        mock_expander,
    ):
        """Should render basic event details."""
        from rlm.visualizer.app import render_event_detail

        # Mock the expander context manager
        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()

        # Mock columns
        mock_col = MagicMock()
        mock_col.__enter__ = MagicMock(return_value=mock_col)
        mock_col.__exit__ = MagicMock()
        mock_columns.return_value = [mock_col, mock_col, mock_col, mock_col]

        mock_button.return_value = False

        event = {
            "depth": 0,
            "input_tokens": 100,
            "output_tokens": 50,
            "duration_ms": 500,
            "tool_calls": [],
            "prompt": "Test prompt",
            "response": "Test response",
        }

        render_event_detail(event, 0)

        mock_expander.assert_called_once()
        # Should show metrics
        assert mock_metric.call_count >= 4

    @patch("streamlit.expander")
    @patch("streamlit.columns")
    @patch("streamlit.metric")
    @patch("streamlit.markdown")
    @patch("streamlit.code")
    @patch("streamlit.button")
    @patch("streamlit.error")
    def test_renders_event_with_error(
        self,
        mock_error,
        mock_button,
        mock_code,
        mock_markdown,
        mock_metric,
        mock_columns,
        mock_expander,
    ):
        """Should render event with error."""
        from rlm.visualizer.app import render_event_detail

        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()

        mock_col = MagicMock()
        mock_col.__enter__ = MagicMock(return_value=mock_col)
        mock_col.__exit__ = MagicMock()
        mock_columns.return_value = [mock_col, mock_col, mock_col, mock_col]

        mock_button.return_value = False

        event = {
            "depth": 0,
            "input_tokens": 100,
            "output_tokens": 50,
            "duration_ms": 500,
            "tool_calls": [],
            "prompt": "Test prompt",
            "error": "Something went wrong",
        }

        render_event_detail(event, 0)

        mock_error.assert_called_once()
        assert "Something went wrong" in str(mock_error.call_args)

    @patch("streamlit.expander")
    @patch("streamlit.columns")
    @patch("streamlit.metric")
    @patch("streamlit.markdown")
    @patch("streamlit.code")
    @patch("streamlit.button")
    @patch("streamlit.error")
    def test_renders_tool_calls(
        self,
        mock_error,
        mock_button,
        mock_code,
        mock_markdown,
        mock_metric,
        mock_columns,
        mock_expander,
    ):
        """Should render tool calls."""
        from rlm.visualizer.app import render_event_detail

        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()

        mock_col = MagicMock()
        mock_col.__enter__ = MagicMock(return_value=mock_col)
        mock_col.__exit__ = MagicMock()
        mock_columns.return_value = [mock_col, mock_col, mock_col, mock_col]

        mock_button.return_value = False

        event = {
            "depth": 0,
            "input_tokens": 100,
            "output_tokens": 50,
            "duration_ms": 500,
            "tool_calls": [
                {"name": "execute_python", "arguments": {"code": "print(1)"}},
            ],
            "prompt": "Test prompt",
        }

        render_event_detail(event, 0)

        # Check that tool calls are rendered
        markdown_calls = [str(call) for call in mock_markdown.call_args_list]
        assert any("Tool Calls" in str(call) for call in markdown_calls)

    @patch("streamlit.expander")
    @patch("streamlit.columns")
    @patch("streamlit.metric")
    @patch("streamlit.markdown")
    @patch("streamlit.code")
    @patch("streamlit.button")
    @patch("streamlit.error")
    def test_truncates_long_prompt(
        self,
        mock_error,
        mock_button,
        mock_code,
        mock_markdown,
        mock_metric,
        mock_columns,
        mock_expander,
    ):
        """Should truncate long prompts."""
        from rlm.visualizer.app import render_event_detail

        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()

        mock_col = MagicMock()
        mock_col.__enter__ = MagicMock(return_value=mock_col)
        mock_col.__exit__ = MagicMock()
        mock_columns.return_value = [mock_col, mock_col, mock_col, mock_col]

        mock_button.return_value = False

        event = {
            "depth": 0,
            "input_tokens": 100,
            "output_tokens": 50,
            "duration_ms": 500,
            "tool_calls": [],
            "prompt": "x" * 600,  # Long prompt
        }

        render_event_detail(event, 0)

        # Should show truncated prompt
        code_calls = [str(call) for call in mock_code.call_args_list]
        assert any("..." in str(call) for call in code_calls)


class TestMainFunction:
    """Tests for main Streamlit function."""

    @patch("streamlit.set_page_config")
    @patch("streamlit.title")
    @patch("streamlit.sidebar")
    @patch("streamlit.text_input")
    @patch("streamlit.warning")
    @patch("streamlit.info")
    def test_handles_nonexistent_directory(
        self,
        mock_info,
        mock_warning,
        mock_text_input,
        mock_sidebar,
        mock_title,
        mock_page_config,
    ):
        """Should show warning for nonexistent directory."""
        from rlm.visualizer.app import main

        # Mock sidebar context manager
        mock_sidebar.__enter__ = MagicMock()
        mock_sidebar.__exit__ = MagicMock()

        mock_text_input.return_value = "/nonexistent/path"

        with patch("pathlib.Path.exists", return_value=False):
            main()

        mock_warning.assert_called()


class TestVisualizerImports:
    """Tests for visualizer module imports."""

    def test_imports_required_modules(self):
        """Should import all required modules."""
        from rlm.visualizer import app

        assert hasattr(app, "load_trajectory")
        assert hasattr(app, "list_trajectories")
        assert hasattr(app, "render_event_tree")
        assert hasattr(app, "render_token_chart")
        assert hasattr(app, "render_duration_chart")
        assert hasattr(app, "render_event_detail")
        assert hasattr(app, "main")

    def test_plotly_imported(self):
        """Should have plotly imports available."""
        from rlm.visualizer.app import go, px

        assert go is not None
        assert px is not None


class TestRenderEventDetailWithToolResults:
    """Test event detail rendering with tool results."""

    @patch("streamlit.expander")
    @patch("streamlit.columns")
    @patch("streamlit.metric")
    @patch("streamlit.markdown")
    @patch("streamlit.code")
    @patch("streamlit.button")
    @patch("streamlit.error")
    def test_renders_tool_results(
        self,
        mock_error,
        mock_button,
        mock_code,
        mock_markdown,
        mock_metric,
        mock_columns,
        mock_expander,
    ):
        """Should render tool results."""
        from rlm.visualizer.app import render_event_detail

        mock_expander.return_value.__enter__ = MagicMock()
        mock_expander.return_value.__exit__ = MagicMock()

        mock_col = MagicMock()
        mock_col.__enter__ = MagicMock(return_value=mock_col)
        mock_col.__exit__ = MagicMock()
        mock_columns.return_value = [mock_col, mock_col, mock_col, mock_col]

        mock_button.return_value = False

        event = {
            "depth": 0,
            "input_tokens": 100,
            "output_tokens": 50,
            "duration_ms": 500,
            "tool_calls": [],
            "tool_results": [
                {"tool_call_id": "tc1", "content": "Result content here", "is_error": False},
                {"tool_call_id": "tc2", "content": "Error content", "is_error": True},
            ],
            "prompt": "Test prompt",
        }

        render_event_detail(event, 0)

        # Should mention Tool Results
        markdown_calls = [str(call) for call in mock_markdown.call_args_list]
        assert any("Tool Results" in str(call) for call in markdown_calls)


class TestRenderEventTreeEdgeCases:
    """Additional edge case tests for render_event_tree."""

    def test_handles_event_without_parent(self):
        """Should handle events with no parent_call_id."""
        from rlm.visualizer.app import render_event_tree

        events = [
            {
                "call_id": "call1",
                "parent_call_id": None,  # Root node
                "depth": 0,
                "input_tokens": 100,
                "output_tokens": 50,
                "duration_ms": 500,
                "tool_calls": [],
                "error": None,
            },
        ]

        result = render_event_tree(events)

        # Should not raise
        assert result is not None

    def test_handles_missing_optional_fields(self):
        """Should handle events with missing optional fields."""
        from rlm.visualizer.app import render_event_tree

        events = [
            {
                "call_id": "call1",
                "depth": 0,
                # Missing: parent_call_id, input_tokens, output_tokens, etc.
            },
        ]

        result = render_event_tree(events)

        # Should use defaults without raising
        assert result is not None


class TestListTrajectoriesEdgeCases:
    """Additional edge case tests for list_trajectories."""

    def test_handles_empty_file(self, tmp_path):
        """Should handle empty JSONL files."""
        from rlm.visualizer.app import list_trajectories

        empty_file = tmp_path / "empty.jsonl"
        empty_file.write_text("")

        result = list_trajectories(tmp_path)

        # Should skip empty files
        assert result == []

    def test_handles_missing_fields(self, tmp_path):
        """Should skip files with missing required fields."""
        from rlm.visualizer.app import list_trajectories

        incomplete = tmp_path / "incomplete.jsonl"
        incomplete.write_text(
            '{"_type": "trajectory_metadata", "trajectory_id": "test"}\n'
        )  # Missing other fields

        result = list_trajectories(tmp_path)

        # Should skip due to missing fields (KeyError)
        assert result == []
