"""
Tests for FileWatcher + QuickAnalyzer — Phase 5
"""
import os
import tempfile
import pytest
from mcp_server.tools.file_watcher import (
    QuickAnalyzer,
    FileWatcher,
    WatcherResult,
    FileIssue,
)


# ---------------------------------------------------------------------------
# QuickAnalyzer tests
# ---------------------------------------------------------------------------

class TestQuickAnalyzerSecrets:
    def test_detects_hardcoded_password(self):
        code = '''password = "my_secret_pass_123"\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "secret" for i in result.issues)

    def test_detects_hardcoded_api_key(self):
        code = '''api_key = "sk-abc123def456ghi789"\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "secret" for i in result.issues)

    def test_no_false_positive_for_env_var(self):
        code = '''password = os.getenv("PASSWORD")\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert not any(i.issue_type == "secret" for i in result.issues)


class TestQuickAnalyzerBareExcept:
    def test_detects_bare_except(self):
        code = '''try:\n    x = 1\nexcept:\n    pass\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "bare_except" for i in result.issues)

    def test_no_false_positive_for_specific_except(self):
        code = '''try:\n    x = 1\nexcept ValueError:\n    pass\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert not any(i.issue_type == "bare_except" for i in result.issues)


class TestQuickAnalyzerDeepNesting:
    def test_detects_deep_nesting(self):
        code = "def f():\n" + "    " * 6 + "x = 1\n"
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "deep_nesting" for i in result.issues)


class TestQuickAnalyzerTodos:
    def test_detects_todo(self):
        code = '''# TODO: fix this later\nx = 1\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "todo" for i in result.issues)

    def test_detects_fixme(self):
        code = '''# FIXME: this is broken\nx = 1\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "todo" for i in result.issues)


class TestQuickAnalyzerLargeFunction:
    def test_detects_large_function(self):
        body = "\n".join(f"    x_{i} = {i}" for i in range(55))
        code = f"def big_function():\n{body}\n"
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "large_function" for i in result.issues)


class TestQuickAnalyzerDocstrings:
    def test_detects_missing_docstring(self):
        body = "\n".join(f"    x_{i} = {i}" for i in range(12))
        code = f"def undocumented():\n{body}\n"
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert any(i.issue_type == "no_docstring" for i in result.issues)


class TestQuickAnalyzerOverallVibe:
    def test_clean_file(self):
        code = '''"""Clean module."""\n\ndef add(a, b):\n    """Add two numbers."""\n    return a + b\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert result.overall_vibe == "clean"

    def test_dangerous_file(self):
        code = '''password = "hunter2"\napi_key = "sk-1234567890abcdef"\n'''
        analyzer = QuickAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = analyzer.analyze_file(f.name)
        os.unlink(f.name)
        assert result.overall_vibe == "dangerous"


# ---------------------------------------------------------------------------
# FileWatcher tests
# ---------------------------------------------------------------------------

class TestFileWatcher:
    def test_initial_status_inactive(self):
        watcher = FileWatcher()
        assert watcher.status.active is False

    def test_get_status_inactive(self):
        watcher = FileWatcher()
        status = watcher.get_status()
        assert "inactive" in status.lower()

    def test_analyze_single_file(self):
        code = '''x = 1\n'''
        watcher = FileWatcher()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            result = watcher.analyze_single_file(f.name)
        os.unlink(f.name)
        assert isinstance(result, WatcherResult)

    def test_stop_when_not_running(self):
        watcher = FileWatcher()
        msg = watcher.stop()
        assert "not running" in msg.lower()


class TestFormatResult:
    def test_clean_result_shows_no_issues(self):
        watcher = FileWatcher()
        result = WatcherResult(
            file_path="test.py",
            issues=[],
            overall_vibe="clean",
            lines_of_code=10,
        )
        text = watcher.format_result(result)
        assert "No issues" in text or "Clean" in text

    def test_dangerous_result_shows_issues(self):
        watcher = FileWatcher()
        result = WatcherResult(
            file_path="bad.py",
            issues=[
                FileIssue(
                    file_path="bad.py",
                    line_number=1,
                    issue_type="secret",
                    severity="critical",
                    message="Hardcoded password",
                ),
            ],
            overall_vibe="dangerous",
            lines_of_code=5,
        )
        text = watcher.format_result(result)
        assert "secret" in text.lower() or "password" in text.lower()
