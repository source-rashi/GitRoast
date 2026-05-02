"""
GitRoast — Real-Time File Watcher (Phase 5)
===============================================
Watches a workspace directory for Python file changes and provides
instant micro-roasts when files are saved.

Features:
- Lightweight AST-based analysis (no pylint subprocess on every save)
- Detects: secrets, bare excepts, deep nesting, TODOs, missing docstrings
- Returns issues as structured data for inline comment rendering
- Start/stop via MCP tool

Uses the watchdog library for cross-platform file system monitoring.
"""

import ast
import os
import re
import threading
from datetime import datetime, timezone
from typing import Optional, Callable

from pydantic import BaseModel, Field
from loguru import logger

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog not installed — real-time file watching disabled.")


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class FileIssue(BaseModel):
    file_path: str
    line_number: int = 1
    issue_type: str
    severity: str  # "critical", "warning", "info"
    message: str
    quick_fix: str = ""


class WatcherResult(BaseModel):
    file_path: str
    issues: list[FileIssue] = []
    analyzed_at: str = ""
    lines_of_code: int = 0
    overall_vibe: str = ""  # "clean", "messy", "dangerous"


class WatcherStatus(BaseModel):
    active: bool = False
    watch_path: str = ""
    files_analyzed: int = 0
    total_issues_found: int = 0
    started_at: str = ""


# ---------------------------------------------------------------------------
# Secret detection patterns (same as code_analyzer but standalone)
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (r'password\s*=\s*["\']([^"\']{4,})["\']', "password"),
    (r'api_key\s*=\s*["\']([^"\']{8,})["\']', "api_key"),
    (r'secret\s*=\s*["\']([^"\']{4,})["\']', "secret"),
    (r'token\s*=\s*["\']([^"\']{8,})["\']', "token"),
    (r'private_key\s*=\s*["\']([^"\']{4,})["\']', "private_key"),
]

ENV_PATTERNS = [
    r"os\.getenv\s*\(",
    r"os\.environ",
    r"environ\.get\s*\(",
]


# ---------------------------------------------------------------------------
# Lightweight file analyzer (runs on every save — must be fast)
# ---------------------------------------------------------------------------

class QuickAnalyzer:
    """Fast, AST-based analysis for real-time feedback. No subprocess calls."""

    def analyze_file(self, file_path: str) -> WatcherResult:
        """Analyze a single Python file and return issues."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as exc:
            logger.warning(f"Could not read {file_path}: {exc}")
            return WatcherResult(
                file_path=file_path,
                analyzed_at=datetime.now(timezone.utc).isoformat(),
            )

        lines = content.splitlines()
        loc = sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))

        issues: list[FileIssue] = []

        # --- Secret detection ---
        issues.extend(self._detect_secrets(content, file_path))

        # --- Bare excepts ---
        issues.extend(self._detect_bare_excepts(content, file_path))

        # --- Deep nesting ---
        issues.extend(self._detect_deep_nesting(content, file_path))

        # --- Missing docstrings on large functions ---
        issues.extend(self._detect_missing_docstrings(content, file_path))

        # --- TODO/FIXME ---
        issues.extend(self._detect_todos(content, file_path))

        # --- Large function detection ---
        issues.extend(self._detect_large_functions(content, file_path))

        # Determine overall vibe
        critical_count = sum(1 for i in issues if i.severity == "critical")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        if critical_count > 0:
            vibe = "dangerous"
        elif warning_count >= 3:
            vibe = "messy"
        elif len(issues) == 0:
            vibe = "clean"
        else:
            vibe = "decent"

        return WatcherResult(
            file_path=file_path,
            issues=issues,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            lines_of_code=loc,
            overall_vibe=vibe,
        )

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _detect_secrets(self, content: str, file_path: str) -> list[FileIssue]:
        issues: list[FileIssue] = []
        for i, line in enumerate(content.splitlines(), 1):
            if any(re.search(p, line) for p in ENV_PATTERNS):
                continue
            for pattern, var_name in SECRET_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(FileIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="secret",
                        severity="critical",
                        message=f"Possible hardcoded {var_name} detected — use environment variables",
                        quick_fix=f"Replace with os.getenv('{var_name.upper()}')",
                    ))
                    break
        return issues[:3]  # Cap to avoid noise

    def _detect_bare_excepts(self, content: str, file_path: str) -> list[FileIssue]:
        issues: list[FileIssue] = []
        pattern = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
        for match in pattern.finditer(content):
            line_num = content[:match.start()].count("\n") + 1
            issues.append(FileIssue(
                file_path=file_path,
                line_number=line_num,
                issue_type="bare_except",
                severity="warning",
                message="Bare 'except:' catches everything — use 'except Exception:'",
                quick_fix="Replace with 'except Exception as exc:'",
            ))
        return issues[:3]

    def _detect_deep_nesting(self, content: str, file_path: str) -> list[FileIssue]:
        issues: list[FileIssue] = []
        for i, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            leading = len(line) - len(line.lstrip(" "))
            level = leading // 4
            if level > 4:
                issues.append(FileIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="deep_nesting",
                    severity="warning",
                    message=f"Nesting level {level} — extract into a helper function",
                    quick_fix="Move nested logic into a separate function",
                ))
        return issues[:3]

    def _detect_missing_docstrings(self, content: str, file_path: str) -> list[FileIssue]:
        issues: list[FileIssue] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno + 5)
                func_lines = end_line - node.lineno
                if func_lines > 10 and ast.get_docstring(node) is None:
                    issues.append(FileIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type="no_docstring",
                        severity="info",
                        message=f"Function '{node.name}' ({func_lines} lines) has no docstring",
                        quick_fix=f'Add a """docstring""" after def {node.name}(...):',
                    ))
                if len(issues) >= 3:
                    break
        return issues

    def _detect_todos(self, content: str, file_path: str) -> list[FileIssue]:
        issues: list[FileIssue] = []
        pattern = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
        for i, line in enumerate(content.splitlines(), 1):
            if pattern.search(line):
                issues.append(FileIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="todo",
                    severity="info",
                    message="TODO/FIXME comment — is this still relevant?",
                    quick_fix="Resolve or create an issue for tracking",
                ))
        return issues[:5]

    def _detect_large_functions(self, content: str, file_path: str) -> list[FileIssue]:
        issues: list[FileIssue] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno)
                func_lines = end_line - node.lineno
                if func_lines > 50:
                    issues.append(FileIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type="large_function",
                        severity="warning",
                        message=f"Function '{node.name}' is {func_lines} lines — consider splitting",
                        quick_fix="Break into smaller, focused functions",
                    ))
                if len(issues) >= 2:
                    break
        return issues


# ---------------------------------------------------------------------------
# File System Event Handler (watchdog)
# ---------------------------------------------------------------------------

class _PythonFileHandler(FileSystemEventHandler):
    """Handles file modification events for Python files."""

    SKIP_DIRS = {"__pycache__", ".git", "node_modules", "venv", ".venv", "env", ".env", "dist", "build"}

    def __init__(self, analyzer: QuickAnalyzer, callback: Callable[[WatcherResult], None]):
        super().__init__()
        self.analyzer = analyzer
        self.callback = callback
        self.files_analyzed = 0
        self.total_issues = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".py"):
            return
        # Skip excluded directories
        parts = event.src_path.replace("\\", "/").split("/")
        if any(p in self.SKIP_DIRS for p in parts):
            return

        logger.debug(f"File changed: {event.src_path}")
        result = self.analyzer.analyze_file(event.src_path)
        self.files_analyzed += 1
        self.total_issues += len(result.issues)
        self.callback(result)


# ---------------------------------------------------------------------------
# FileWatcher — main controller
# ---------------------------------------------------------------------------

class FileWatcher:
    """Manages real-time file watching for a workspace directory."""

    def __init__(self):
        self.observer: Optional[Observer] = None
        self.handler: Optional[_PythonFileHandler] = None
        self.analyzer = QuickAnalyzer()
        self.status = WatcherStatus()
        self._results_buffer: list[WatcherResult] = []
        self._lock = threading.Lock()

    def start(self, watch_path: str) -> str:
        """Start watching a directory for Python file changes."""
        if not WATCHDOG_AVAILABLE:
            return (
                "❌ watchdog is not installed. "
                "Run: pip install watchdog>=4.0.0"
            )

        if self.observer and self.observer.is_alive():
            return f"⚠️ Already watching: {self.status.watch_path}"

        if not os.path.isdir(watch_path):
            return f"❌ Directory not found: {watch_path}"

        self.handler = _PythonFileHandler(self.analyzer, self._on_result)
        self.observer = Observer()
        self.observer.schedule(self.handler, watch_path, recursive=True)
        self.observer.start()

        self.status = WatcherStatus(
            active=True,
            watch_path=watch_path,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(f"File watcher started: {watch_path}")
        return (
            f"👁️ File watcher active on: `{watch_path}`\n\n"
            "I'll analyze Python files when you save them and report issues instantly.\n"
            "Use `watch_workspace(action='stop')` to disable."
        )

    def stop(self) -> str:
        """Stop the file watcher."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None

            summary = (
                f"👁️ File watcher stopped.\n\n"
                f"**Session stats:**\n"
                f"- Files analyzed: {self.handler.files_analyzed if self.handler else 0}\n"
                f"- Total issues found: {self.handler.total_issues if self.handler else 0}\n"
            )
            self.status.active = False
            return summary

        self.status.active = False
        return "⚠️ File watcher was not running."

    def get_status(self) -> str:
        """Return the current watcher status."""
        if not self.status.active:
            return "👁️ File watcher is **inactive**. Use `watch_workspace(action='start')` to enable."

        return (
            f"👁️ File watcher is **active**\n\n"
            f"- **Watching:** `{self.status.watch_path}`\n"
            f"- **Files analyzed:** {self.handler.files_analyzed if self.handler else 0}\n"
            f"- **Issues found:** {self.handler.total_issues if self.handler else 0}\n"
            f"- **Started at:** {self.status.started_at}\n"
        )

    def get_recent_results(self, limit: int = 5) -> list[WatcherResult]:
        """Return the most recent analysis results."""
        with self._lock:
            return list(self._results_buffer[-limit:])

    def analyze_single_file(self, file_path: str) -> WatcherResult:
        """Analyze a single file on demand (doesn't require watcher to be running)."""
        return self.analyzer.analyze_file(file_path)

    def _on_result(self, result: WatcherResult) -> None:
        """Callback when a file is analyzed."""
        with self._lock:
            self._results_buffer.append(result)
            # Keep buffer bounded
            if len(self._results_buffer) > 50:
                self._results_buffer = self._results_buffer[-30:]

        if result.issues:
            logger.info(
                f"[Watcher] {result.file_path}: {len(result.issues)} issue(s) — {result.overall_vibe}"
            )

    # ------------------------------------------------------------------
    # Format results for display
    # ------------------------------------------------------------------

    def format_result(self, result: WatcherResult) -> str:
        """Format a single file analysis result."""
        vibe_emoji = {
            "clean": "✅",
            "decent": "👍",
            "messy": "⚠️",
            "dangerous": "🚨",
        }

        lines = [
            f"## {vibe_emoji.get(result.overall_vibe, '📄')} {os.path.basename(result.file_path)}",
            f"*{result.lines_of_code} lines · {result.overall_vibe} · {result.analyzed_at}*",
            "",
        ]

        if not result.issues:
            lines.append("No issues found. Clean code. 🎉")
        else:
            for issue in result.issues:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue.severity, "⚪")
                lines.append(f"- {icon} **L{issue.line_number}** [{issue.issue_type}] {issue.message}")
                if issue.quick_fix:
                    lines.append(f"  *Fix:* {issue.quick_fix}")

        return "\n".join(lines)

    def format_recent_results(self) -> str:
        """Format all recent results into a single Markdown report."""
        results = self.get_recent_results(10)
        if not results:
            return "No files analyzed yet. Save a Python file to trigger analysis."

        lines = ["# 👁️ GitRoast — Recent File Analysis", ""]
        for result in reversed(results):
            lines.append(self.format_result(result))
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)
