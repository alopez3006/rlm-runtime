"""Tests for REPL safety utilities."""

from rlm.repl.safety import (
    ALLOWED_IMPORTS,
    BLOCKED_IMPORTS,
    MAX_OUTPUT_SIZE,
    is_import_allowed,
    truncate_output,
)


class TestAllowedImports:
    """Tests for ALLOWED_IMPORTS constant."""

    def test_contains_json(self):
        """Should allow json import."""
        assert "json" in ALLOWED_IMPORTS

    def test_contains_math(self):
        """Should allow math import."""
        assert "math" in ALLOWED_IMPORTS

    def test_contains_datetime(self):
        """Should allow datetime import."""
        assert "datetime" in ALLOWED_IMPORTS

    def test_contains_collections(self):
        """Should allow collections import."""
        assert "collections" in ALLOWED_IMPORTS

    def test_contains_urllib_parse(self):
        """Should allow urllib.parse import."""
        assert "urllib.parse" in ALLOWED_IMPORTS

    def test_is_frozenset(self):
        """Should be an immutable frozenset."""
        assert isinstance(ALLOWED_IMPORTS, frozenset)


class TestBlockedImports:
    """Tests for BLOCKED_IMPORTS constant."""

    def test_contains_os(self):
        """Should block os import."""
        assert "os" in BLOCKED_IMPORTS

    def test_contains_subprocess(self):
        """Should block subprocess import."""
        assert "subprocess" in BLOCKED_IMPORTS

    def test_contains_socket(self):
        """Should block socket import."""
        assert "socket" in BLOCKED_IMPORTS

    def test_contains_pickle(self):
        """Should block pickle import."""
        assert "pickle" in BLOCKED_IMPORTS

    def test_contains_ctypes(self):
        """Should block ctypes import."""
        assert "ctypes" in BLOCKED_IMPORTS

    def test_is_frozenset(self):
        """Should be an immutable frozenset."""
        assert isinstance(BLOCKED_IMPORTS, frozenset)


class TestIsImportAllowed:
    """Tests for is_import_allowed function."""

    def test_allowed_exact_match(self):
        """Should allow exact match from allowed list."""
        assert is_import_allowed("json") is True
        assert is_import_allowed("math") is True
        assert is_import_allowed("datetime") is True

    def test_blocked_exact_match(self):
        """Should block exact match from blocked list."""
        assert is_import_allowed("os") is False
        assert is_import_allowed("subprocess") is False
        assert is_import_allowed("socket") is False

    def test_allowed_submodule(self):
        """Should allow submodules of allowed modules."""
        assert is_import_allowed("collections.abc") is True
        assert is_import_allowed("datetime.datetime") is True
        assert is_import_allowed("json.decoder") is True

    def test_blocked_submodule(self):
        """Should block submodules of blocked modules."""
        assert is_import_allowed("os.path") is False
        assert is_import_allowed("subprocess.run") is False
        assert is_import_allowed("socket.socket") is False

    def test_urllib_parse_allowed(self):
        """Should allow urllib.parse specifically."""
        assert is_import_allowed("urllib.parse") is True

    def test_urllib_request_blocked(self):
        """Should block urllib.request."""
        assert is_import_allowed("urllib.request") is False

    def test_unknown_module_blocked(self):
        """Should block unknown modules not in allowed list."""
        assert is_import_allowed("nonexistent_module") is False
        assert is_import_allowed("random_package.submodule") is False

    def test_parent_module_check_blocked(self):
        """Should check parent modules against blocked list."""
        # Even deep submodules should be blocked if parent is blocked
        assert is_import_allowed("os.path.join") is False
        assert is_import_allowed("subprocess.Popen") is False

    def test_parent_module_check_allowed(self):
        """Should allow submodules if parent is allowed."""
        assert is_import_allowed("collections.OrderedDict") is True
        assert is_import_allowed("itertools.chain") is True

    def test_blocked_takes_priority(self):
        """Blocked list should be checked first."""
        # os is in blocked, so any submodule should be blocked
        assert is_import_allowed("os") is False
        assert is_import_allowed("os.environ") is False


class TestTruncateOutput:
    """Tests for truncate_output function."""

    def test_no_truncation_small_output(self):
        """Should not truncate small outputs."""
        output = "Hello, World!"
        result, truncated = truncate_output(output)

        assert result == output
        assert truncated is False

    def test_truncation_large_output(self):
        """Should truncate large outputs."""
        output = "x" * (MAX_OUTPUT_SIZE + 1000)
        result, truncated = truncate_output(output)

        assert len(result) <= MAX_OUTPUT_SIZE + 50  # Some room for truncation message
        assert truncated is True
        assert "truncated" in result.lower()

    def test_custom_max_size(self):
        """Should respect custom max_size parameter."""
        output = "x" * 200
        result, truncated = truncate_output(output, max_size=100)

        assert len(result) <= 150  # 100 + truncation message
        assert truncated is True

    def test_truncates_at_line_boundary(self):
        """Should try to truncate at line boundary."""
        # Create output with newlines
        lines = ["line " + str(i) for i in range(20)]
        output = "\n".join(lines)

        result, truncated = truncate_output(output, max_size=50)

        assert truncated is True
        # Should end at a line boundary (before the truncation message)
        result_before_message = result.split("\n... (output truncated)")[0]
        assert not result_before_message.endswith(" ")  # Should be clean line break

    def test_no_truncation_at_line_boundary_if_too_early(self):
        """Should not truncate at line boundary if it would remove too much."""
        # Create output where the last newline is very early
        output = "first line\n" + "x" * 100

        result, truncated = truncate_output(output, max_size=60)

        # Since the newline is at position 10, which is less than 30 (60/2),
        # it should just truncate at 60 chars, not at the newline
        assert truncated is True
        assert "truncated" in result.lower()

    def test_exact_max_size_no_truncation(self):
        """Should not truncate if output is exactly max_size."""
        output = "x" * 100
        result, truncated = truncate_output(output, max_size=100)

        assert result == output
        assert truncated is False

    def test_empty_output(self):
        """Should handle empty output."""
        result, truncated = truncate_output("")

        assert result == ""
        assert truncated is False

    def test_single_char_output(self):
        """Should handle single character output."""
        result, truncated = truncate_output("x")

        assert result == "x"
        assert truncated is False


class TestConstants:
    """Tests for safety constants."""

    def test_max_output_size_is_positive(self):
        """MAX_OUTPUT_SIZE should be positive."""
        assert MAX_OUTPUT_SIZE > 0

    def test_max_output_size_reasonable(self):
        """MAX_OUTPUT_SIZE should be a reasonable value."""
        from rlm.repl.safety import MAX_OUTPUT_SIZE

        assert MAX_OUTPUT_SIZE >= 1000
        assert MAX_OUTPUT_SIZE <= 10_000_000

    def test_max_output_lines_is_positive(self):
        """MAX_OUTPUT_LINES should be positive."""
        from rlm.repl.safety import MAX_OUTPUT_LINES

        assert MAX_OUTPUT_LINES > 0

    def test_max_execution_time_is_positive(self):
        """MAX_EXECUTION_TIME should be positive."""
        from rlm.repl.safety import MAX_EXECUTION_TIME

        assert MAX_EXECUTION_TIME > 0

    def test_max_memory_mb_is_positive(self):
        """MAX_MEMORY_MB should be positive."""
        from rlm.repl.safety import MAX_MEMORY_MB

        assert MAX_MEMORY_MB > 0
