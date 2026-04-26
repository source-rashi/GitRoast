"""
GitRoast — Code Quality Analyzer
====================================
Performs real static analysis on GitHub repos. Not vibes — actual findings.

What it detects:
- Cyclomatic complexity per function (radon)
- Maintainability index per file (radon)
- Pylint score per Python file (pylint)
- Missing error handling (bare except, no try/except in risky code)
- Hardcoded secrets (passwords, API keys, tokens in plain text)
- Dead code hints (unused imports via AST)
- Missing docstrings (functions/classes with no docstring)
- Deeply nested logic (nesting depth > 4)
- Test coverage estimate (ratio of test files to source files)
- TODO/FIXME/HACK comment count

Scores each repo 1-10 with specific file-level evidence.
Works entirely free using GitHub API + local static analysis tools.
"""

import ast
import os
import re
import json
import tempfile
import subprocess
from collections import Counter
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from github import Github, GithubException
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger

try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False
    logger.warning("radon not installed — complexity/MI analysis will be skipped.")


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class CodeIssue(BaseModel):
    file_path: str
    line_number: Optional[int] = None
    issue_type: str   # "complexity","secret","no_docstring","deep_nesting","bare_except","unused_import","todo"
    severity: str     # "critical","warning","info"
    message: str
    evidence: str     # the actual code snippet or value that triggered this


class FileAnalysis(BaseModel):
    file_path: str
    language: str
    lines_of_code: int = 0
    complexity_score: float = 0.0
    maintainability_index: float = 0.0
    pylint_score: float = 0.0
    issues: list[CodeIssue] = []
    has_docstrings: bool = False
    has_error_handling: bool = False


class RepoQualityReport(BaseModel):
    repo_name: str
    repo_url: str
    language: Optional[str] = None
    overall_score: float = 0.0
    total_files_analyzed: int = 0
    total_issues: int = 0
    critical_issues: int = 0
    files: list[FileAnalysis] = []
    hardcoded_secrets_found: list[CodeIssue] = []
    todo_count: int = 0
    test_coverage_estimate: float = 0.0
    summary_bullets: list[str] = []
    roast_lines: list[str] = []


class CodeQualityResult(BaseModel):
    username: str
    repos_analyzed: list[RepoQualityReport] = []
    overall_grade: str = "F"
    worst_file: Optional[str] = None
    most_common_issue: Optional[str] = None
    total_secrets_found: int = 0
    total_todos: int = 0
    roast_ammunition: list[str] = []
    praise_ammunition: list[str] = []
    analysis_timestamp: str = ""


# ---------------------------------------------------------------------------
# CodeAnalyzer
# ---------------------------------------------------------------------------

class CodeAnalyzer:
    """Real static analysis engine for GitHub Python repos."""

    # Secret patterns — we look for literals, NOT env var references
    SECRET_PATTERNS = [
        (r'password\s*=\s*["\']([^"\']{4,})["\']', "password"),
        (r'api_key\s*=\s*["\']([^"\']{8,})["\']', "api_key"),
        (r'secret\s*=\s*["\']([^"\']{4,})["\']', "secret"),
        (r'token\s*=\s*["\']([^"\']{8,})["\']', "token"),
        (r'private_key\s*=\s*["\']([^"\']{4,})["\']', "private_key"),
        (r'aws_access_key\s*=\s*["\']([^"\']{8,})["\']', "aws_access_key"),
    ]

    def __init__(self):
        load_dotenv()
        self.github = Github(os.getenv("GITHUB_TOKEN"))
        self.console = Console(stderr=True)
        logger.info("CodeAnalyzer initialized.")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def analyze_developer_repos(
        self, username: str, max_repos: int = 3
    ) -> CodeQualityResult:
        """Fetch and analyze top repos for a GitHub user."""
        import asyncio

        result = CodeQualityResult(
            username=username,
            analysis_timestamp=datetime.utcnow().isoformat(),
        )

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                task = progress.add_task("Fetching repos...", total=None)

                user = await asyncio.to_thread(self.github.get_user, username)
                all_repos = list(await asyncio.to_thread(lambda: list(user.get_repos())))

                # Filter: non-forks only, sorted by stars
                candidates = sorted(
                    [r for r in all_repos if not r.fork],
                    key=lambda r: r.stargazers_count,
                    reverse=True,
                )[: max(1, min(max_repos, 5))]

                progress.update(task, description="Downloading files...")

                reports = []
                for repo in candidates:
                    progress.update(task, description=f"Analyzing {repo.name}...")
                    try:
                        report = await asyncio.to_thread(self._analyze_single_repo_sync, repo)
                        reports.append(report)
                    except Exception as exc:
                        logger.warning(f"Skipping repo '{repo.name}': {exc}")

                progress.update(task, description="Running analysis...")

                result.repos_analyzed = reports

                # Aggregate
                all_scores = [r.overall_score for r in reports if r.overall_score > 0]
                avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
                result.overall_grade = self._calculate_overall_grade(avg_score)

                result.total_secrets_found = sum(
                    len(r.hardcoded_secrets_found) for r in reports
                )
                result.total_todos = sum(r.todo_count for r in reports)

                # Worst file across all repos
                all_files = [f for r in reports for f in r.files]
                if all_files:
                    worst = min(all_files, key=lambda f: f.complexity_score if f.complexity_score else 0)
                    worst_by_score = min(all_files, key=lambda f: f.pylint_score)
                    result.worst_file = worst_by_score.file_path

                # Most common issue type
                all_issues = [i for r in reports for f in r.files for i in f.issues]
                if all_issues:
                    counter = Counter(i.issue_type for i in all_issues)
                    result.most_common_issue = counter.most_common(1)[0][0]

                result.roast_ammunition = self._generate_final_roast(result)
                result.praise_ammunition = self._generate_final_praise(result)

        except GithubException as exc:
            if exc.status == 404:
                raise ValueError(f"GitHub user '{username}' not found.")
            if exc.status == 403:
                raise ValueError("GitHub API rate limit hit. Check your GITHUB_TOKEN.")
            raise

        logger.success(f"Code analysis complete for '{username}'.")
        return result

    # ------------------------------------------------------------------
    # Single repo analysis (sync — called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _analyze_single_repo_sync(self, repo) -> RepoQualityReport:
        """Synchronous repo analysis (runs in thread pool)."""
        report = RepoQualityReport(
            repo_name=repo.name,
            repo_url=repo.html_url,
            language=repo.language,
        )

        py_files = self._fetch_python_files(repo)
        all_files_count = len(py_files)
        test_files = [p for p, _ in py_files if "test" in p.lower()]

        report.test_coverage_estimate = (
            len(test_files) / all_files_count if all_files_count > 0 else 0.0
        )

        file_analyses = []
        for file_path, content in py_files:
            try:
                fa = self._analyze_python_file(file_path, content)
                file_analyses.append(fa)
                report.todo_count += sum(
                    1 for issue in fa.issues if issue.issue_type == "todo"
                )
                report.hardcoded_secrets_found.extend(
                    i for i in fa.issues if i.issue_type == "secret"
                )
            except Exception as exc:
                logger.warning(f"Could not analyze '{file_path}': {exc}")

        report.files = file_analyses
        report.total_files_analyzed = len(file_analyses)
        report.total_issues = sum(len(f.issues) for f in file_analyses)
        report.critical_issues = sum(
            1 for f in file_analyses for i in f.issues if i.severity == "critical"
        )

        # Weighted overall score
        scores = [f.pylint_score for f in file_analyses if f.pylint_score > 0]
        report.overall_score = round(sum(scores) / len(scores), 1) if scores else 5.0

        # Summary bullets
        bullets = []
        for fa in file_analyses[:5]:
            if fa.complexity_score > 10:
                bullets.append(
                    f"{fa.file_path} has complexity {fa.complexity_score:.1f} — consider refactoring."
                )
            if fa.maintainability_index < 30:
                bullets.append(
                    f"{fa.file_path} has maintainability index {fa.maintainability_index:.0f}/100 — hard to maintain."
                )
        report.summary_bullets = bullets

        report.roast_lines = self._generate_repo_roast_lines(report)
        return report

    # ------------------------------------------------------------------
    # File fetching
    # ------------------------------------------------------------------

    def _fetch_python_files(self, repo) -> list[tuple[str, str]]:
        """Return (path, decoded_content) tuples for Python files in the repo."""
        SKIP_DIRS = {"__pycache__", ".git", "node_modules", "venv", ".venv", "env", ".env", "dist", "build"}
        results: list[tuple[str, str]] = []

        def walk(path: str = ""):
            if len(results) >= 15:
                return
            try:
                items = repo.get_contents(path)
                if not isinstance(items, list):
                    items = [items]
                for item in items:
                    if len(results) >= 15:
                        return
                    parts = item.path.split("/")
                    if any(p in SKIP_DIRS for p in parts):
                        continue
                    if item.type == "dir":
                        walk(item.path)
                    elif item.name.endswith(".py"):
                        if item.size and item.size > 50_000:
                            logger.info(f"Skipping large file: {item.path} ({item.size} bytes)")
                            continue
                        try:
                            content = item.decoded_content.decode("utf-8", errors="replace")
                            results.append((item.path, content))
                        except Exception as exc:
                            logger.warning(f"Could not decode {item.path}: {exc}")
            except Exception as exc:
                logger.warning(f"Could not walk '{path}': {exc}")

        walk()
        return results

    # ------------------------------------------------------------------
    # File analysis
    # ------------------------------------------------------------------

    def _analyze_python_file(self, file_path: str, content: str) -> FileAnalysis:
        """Run full static analysis on a single Python file."""
        lines = content.splitlines()
        loc = sum(
            1 for line in lines
            if line.strip() and not line.strip().startswith("#")
        )

        fa = FileAnalysis(
            file_path=file_path,
            language="Python",
            lines_of_code=loc,
        )

        all_issues: list[CodeIssue] = []

        # --- Radon complexity ---
        if RADON_AVAILABLE:
            try:
                blocks = cc_visit(content)
                if blocks:
                    fa.complexity_score = round(
                        sum(b.complexity for b in blocks) / len(blocks), 2
                    )
                    for block in blocks:
                        if block.complexity > 15:
                            all_issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=block.lineno,
                                issue_type="complexity",
                                severity="critical",
                                message=f"Function '{block.name}' has cyclomatic complexity {block.complexity} (max recommended: 10)",
                                evidence=f"{block.name}() — complexity {block.complexity}",
                            ))
                        elif block.complexity > 10:
                            all_issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=block.lineno,
                                issue_type="complexity",
                                severity="warning",
                                message=f"Function '{block.name}' has cyclomatic complexity {block.complexity}",
                                evidence=f"{block.name}() — complexity {block.complexity}",
                            ))
            except Exception as exc:
                logger.debug(f"Radon CC failed for {file_path}: {exc}")

            # --- Radon MI ---
            try:
                mi_raw = mi_visit(content, True)
                fa.maintainability_index = round(float(mi_raw), 1)
            except Exception as exc:
                logger.debug(f"Radon MI failed for {file_path}: {exc}")

        # --- Pylint ---
        pylint_score, pylint_issues = self._run_pylint(file_path, content)
        fa.pylint_score = pylint_score
        all_issues.extend(pylint_issues)

        # --- Detectors ---
        all_issues.extend(self._detect_secrets(content, file_path))
        all_issues.extend(self._detect_missing_docstrings(content, file_path))
        all_issues.extend(self._detect_deep_nesting(content, file_path))
        all_issues.extend(self._detect_bare_excepts(content, file_path))
        all_issues.extend(self._detect_unused_imports(content, file_path))

        # --- TODO counting ---
        todo_pattern = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if todo_pattern.search(line):
                all_issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="todo",
                    severity="info",
                    message="TODO/FIXME/HACK comment found",
                    evidence=line.strip()[:80],
                ))

        fa.issues = all_issues

        # --- Aggregate booleans ---
        func_count = content.count("def ")
        docstring_issues = sum(1 for i in all_issues if i.issue_type == "no_docstring")
        fa.has_docstrings = func_count > 0 and (docstring_issues / max(func_count, 1)) < 0.5
        fa.has_error_handling = "try:" in content

        # --- File score ---
        score = fa.pylint_score if fa.pylint_score > 0 else 7.0
        critical_count = sum(1 for i in all_issues if i.severity == "critical")
        warning_count = sum(1 for i in all_issues if i.severity == "warning")
        score -= min(critical_count * 0.5, 3.0)
        score -= min(warning_count * 0.2, 2.0)
        if fa.maintainability_index > 0 and fa.maintainability_index < 20:
            score -= 1.0
        elif fa.maintainability_index > 0 and fa.maintainability_index < 50:
            score -= 0.5
        if fa.has_docstrings:
            score += 0.5
        if fa.has_error_handling:
            score += 0.5
        fa.pylint_score = round(max(1.0, min(10.0, score)), 1)

        return fa

    # ------------------------------------------------------------------
    # Pylint runner
    # ------------------------------------------------------------------

    def _run_pylint(self, file_path: str, content: str) -> tuple[float, list[CodeIssue]]:
        """Run pylint on content via subprocess. Returns (score, issues)."""
        issues: list[CodeIssue] = []
        score = 5.0

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            result = subprocess.run(
                ["python", "-m", "pylint", "--output-format=json", "--score=y", tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Parse JSON messages
            if result.stdout.strip():
                try:
                    messages = json.loads(result.stdout)
                    for msg in messages[:10]:  # cap at 10 pylint messages per file
                        severity = "warning"
                        if msg.get("type") in ("error", "fatal"):
                            severity = "critical"
                        elif msg.get("type") == "convention":
                            severity = "info"
                        issues.append(CodeIssue(
                            file_path=file_path,
                            line_number=msg.get("line"),
                            issue_type="pylint",
                            severity=severity,
                            message=f"[{msg.get('symbol', 'pylint')}] {msg.get('message', '')}",
                            evidence=msg.get("message", ""),
                        ))
                except json.JSONDecodeError:
                    pass

            # Parse score from stderr
            score_match = re.search(r"Your code has been rated at ([\d.]+)/10", result.stderr + result.stdout)
            if score_match:
                score = float(score_match.group(1))

        except subprocess.TimeoutExpired:
            logger.warning(f"Pylint timed out for {file_path}")
        except FileNotFoundError:
            logger.warning("pylint not found in PATH — skipping pylint analysis")
        except Exception as exc:
            logger.warning(f"Pylint failed for {file_path}: {exc}")
        finally:
            try:
                os.unlink(tmp_path)  # type: ignore[possibly-undefined]
            except Exception:
                pass

        return score, issues

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _detect_secrets(self, content: str, file_path: str) -> list[CodeIssue]:
        """Detect possible hardcoded secrets (never logs the actual value)."""
        issues: list[CodeIssue] = []

        # Skip obvious env var patterns to reduce false positives
        env_patterns = [
            r"os\.getenv\s*\(",
            r"os\.environ",
            r"environ\.get\s*\(",
        ]

        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            # Skip env var lines entirely
            if any(re.search(p, line) for p in env_patterns):
                continue
            for pattern, var_name in self.SECRET_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=i,
                        issue_type="secret",
                        severity="critical",
                        message=f"Possible hardcoded secret found: {var_name}",
                        evidence=f"Line {i} contains: {var_name} = '***REDACTED***'",
                    ))
                    break  # one issue per line

        return issues

    def _detect_missing_docstrings(self, content: str, file_path: str) -> list[CodeIssue]:
        """Flag functions with > 5 lines and no docstring."""
        issues: list[CodeIssue] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Estimate function length
                end_line = getattr(node, "end_lineno", node.lineno + 5)
                func_lines = end_line - node.lineno
                if func_lines > 5 and ast.get_docstring(node) is None:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type="no_docstring",
                        severity="info",
                        message=f"Function '{node.name}' has no docstring",
                        evidence=f"def {node.name}(...) at line {node.lineno}",
                    ))
                if len(issues) >= 5:
                    break

        return issues

    def _detect_deep_nesting(self, content: str, file_path: str) -> list[CodeIssue]:
        """Flag lines with indent level > 4 (nesting too deep)."""
        issues: list[CodeIssue] = []
        for i, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            leading = len(line) - len(line.lstrip(" "))
            level = leading // 4
            if level > 4:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="deep_nesting",
                    severity="warning",
                    message=f"Deep nesting detected at line {i} (indent level {level})",
                    evidence=line.strip()[:80],
                ))
            if len(issues) >= 3:
                break
        return issues

    def _detect_bare_excepts(self, content: str, file_path: str) -> list[CodeIssue]:
        """Detect bare `except:` clauses."""
        issues: list[CodeIssue] = []
        pattern = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
        for match in pattern.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            issues.append(CodeIssue(
                file_path=file_path,
                line_number=line_num,
                issue_type="bare_except",
                severity="warning",
                message=(
                    "Bare 'except:' catches everything including KeyboardInterrupt. "
                    "Use 'except Exception:' or be specific."
                ),
                evidence=match.group().strip(),
            ))
        return issues

    def _detect_unused_imports(self, content: str, file_path: str) -> list[CodeIssue]:
        """Flag imports that appear only on their import line."""
        issues: list[CodeIssue] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        imported_names: list[tuple[str, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names.append((name.split(".")[0], node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names.append((name, node.lineno))

        lines = content.splitlines()
        for name, lineno in imported_names:
            uses = sum(
                1 for i, line in enumerate(lines, 1)
                if i != lineno and re.search(r"\b" + re.escape(name) + r"\b", line)
            )
            if uses == 0:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=lineno,
                    issue_type="unused_import",
                    severity="info",
                    message=f"'{name}' is imported but may not be used",
                    evidence=f"import {name} at line {lineno}",
                ))
            if len(issues) >= 3:
                break

        return issues

    # ------------------------------------------------------------------
    # Roast generators
    # ------------------------------------------------------------------

    def _generate_repo_roast_lines(self, report: RepoQualityReport) -> list[str]:
        lines: list[str] = []

        if report.overall_score < 4:
            lines.append(
                f"{report.repo_name} scored {report.overall_score:.1f}/10. "
                "That's not a codebase, that's a crime scene."
            )

        if report.overall_score >= 8:
            lines.append(
                f"{report.repo_name} scored {report.overall_score:.1f}/10. "
                "Clean code. Suspicious, but impressive."
            )

        if report.critical_issues > 5:
            lines.append(
                f"{report.critical_issues} critical issues in {report.repo_name}. "
                "Critical means 'fix this now', not 'fix this someday'."
            )

        if report.hardcoded_secrets_found:
            n = len(report.hardcoded_secrets_found)
            lines.append(
                f"Found {n} possible hardcoded secret(s) in {report.repo_name}. "
                "Rotate those credentials. Right now. We'll wait."
            )

        if report.todo_count > 10:
            lines.append(
                f"{report.todo_count} TODO comments in {report.repo_name}. "
                "A TODO that survives 3 commits is a permanent feature."
            )

        if report.test_coverage_estimate == 0.0:
            lines.append(
                f"Zero test files in {report.repo_name}. "
                "You're not a developer, you're a gambler."
            )

        if report.files:
            worst = max(report.files, key=lambda f: f.complexity_score)
            if worst.complexity_score > 10:
                lines.append(
                    f"{worst.file_path} has average complexity {worst.complexity_score:.1f}. "
                    "Spaghetti is a food, not an architecture."
                )

        for fa in report.files:
            if fa.maintainability_index > 0 and fa.maintainability_index < 20:
                lines.append(
                    f"Maintainability index below 20 in {fa.file_path}. "
                    "Radon has declared this file a biohazard."
                )
                break

        return lines

    def _calculate_overall_grade(self, avg_score: float) -> str:
        if avg_score >= 9:
            return "A"
        elif avg_score >= 7:
            return "B"
        elif avg_score >= 5:
            return "C"
        elif avg_score >= 3:
            return "D"
        return "F"

    def _generate_final_roast(self, result: CodeQualityResult) -> list[str]:
        lines: list[str] = []

        if result.total_secrets_found > 0:
            lines.append(
                f"{result.total_secrets_found} hardcoded secret(s) found across your repos. "
                "Your security model is hope."
            )

        if result.overall_grade == "F":
            lines.append("Overall code quality grade: F. Even your code is asking for help.")

        if result.overall_grade in ("A", "B"):
            lines.append(
                f"Overall grade: {result.overall_grade}. "
                "You actually write decent code. Rare trait in the wild."
            )

        if result.total_todos > 20:
            lines.append(
                f"{result.total_todos} TODO comments total. "
                "You've been 'planning to fix it' for longer than some startups exist."
            )

        if result.most_common_issue:
            lines.append(
                f"Most common issue: {result.most_common_issue}. "
                "This is a pattern, not a mistake."
            )

        return lines

    def _generate_final_praise(self, result: CodeQualityResult) -> list[str]:
        praise: list[str] = []

        if result.overall_grade in ("A", "B"):
            praise.append(
                "High code quality scores across the board. Your future self will thank you."
            )

        if result.total_secrets_found == 0:
            praise.append(
                "No hardcoded secrets found. You understand that .env files exist. A hero."
            )

        repos_with_tests = sum(
            1 for r in result.repos_analyzed if r.test_coverage_estimate > 0
        )
        if repos_with_tests > 0:
            praise.append(
                f"{repos_with_tests} repo(s) have test files. "
                "You test before you ship. Evolved."
            )

        return praise


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    analyzer = CodeAnalyzer()
    result = asyncio.run(analyzer.analyze_developer_repos("torvalds", max_repos=2))
    print(result.model_dump_json(indent=2))
