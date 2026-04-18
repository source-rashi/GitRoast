"""
GitRoast — Tests for Code Quality Analyzer
============================================
All tests use mocks or pure-static inputs — no real GitHub API calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mcp_server.tools.code_analyzer import (
    CodeAnalyzer,
    CodeQualityResult,
    RepoQualityReport,
    FileAnalysis,
    CodeIssue,
)


@pytest.fixture
def analyzer():
    """Return a CodeAnalyzer with a mocked GitHub client."""
    with patch("mcp_server.tools.code_analyzer.Github"):
        a = CodeAnalyzer()
    return a


# ---------------------------------------------------------------------------
# Secret detection tests
# ---------------------------------------------------------------------------

def test_detect_hardcoded_password(analyzer):
    content = 'password = "supersecret123"\nprint("hello")'
    issues = analyzer._detect_secrets(content, "test.py")
    assert len(issues) == 1
    assert issues[0].issue_type == "secret"
    assert "supersecret123" not in issues[0].evidence  # must be redacted


def test_detect_hardcoded_api_key(analyzer):
    content = 'api_key = "sk-abc123456789"\nresult = call_api(api_key)'
    issues = analyzer._detect_secrets(content, "test.py")
    assert len(issues) >= 1


def test_no_false_positive_for_env_var(analyzer):
    """References via os.getenv / environ should NOT be flagged as secrets."""
    content = (
        'api_key = os.getenv("API_KEY")\n'
        'password = os.environ.get("PASSWORD")\n'
    )
    issues = analyzer._detect_secrets(content, "test.py")
    assert len(issues) == 0


# ---------------------------------------------------------------------------
# Bare except tests
# ---------------------------------------------------------------------------

def test_detect_bare_except(analyzer):
    content = "try:\n    something()\nexcept:\n    pass"
    issues = analyzer._detect_bare_excepts(content, "test.py")
    assert len(issues) == 1
    assert issues[0].severity == "warning"


def test_no_bare_except_false_positive(analyzer):
    content = "try:\n    something()\nexcept Exception as e:\n    pass"
    issues = analyzer._detect_bare_excepts(content, "test.py")
    assert len(issues) == 0


# ---------------------------------------------------------------------------
# Deep nesting test
# ---------------------------------------------------------------------------

def test_detect_deep_nesting(analyzer):
    deeply_nested = "def f():\n" + "    " * 5 + "x = 1\n"
    issues = analyzer._detect_deep_nesting(deeply_nested, "test.py")
    assert len(issues) >= 1
    assert issues[0].issue_type == "deep_nesting"


# ---------------------------------------------------------------------------
# Grade calculation tests
# ---------------------------------------------------------------------------

def test_overall_grade_calculation(analyzer):
    assert analyzer._calculate_overall_grade(9.5) == "A"
    assert analyzer._calculate_overall_grade(9.0) == "A"
    assert analyzer._calculate_overall_grade(7.0) == "B"
    assert analyzer._calculate_overall_grade(8.9) == "B"
    assert analyzer._calculate_overall_grade(5.5) == "C"
    assert analyzer._calculate_overall_grade(5.0) == "C"
    assert analyzer._calculate_overall_grade(4.0) == "D"
    assert analyzer._calculate_overall_grade(3.0) == "D"
    assert analyzer._calculate_overall_grade(2.0) == "F"
    assert analyzer._calculate_overall_grade(0.0) == "F"


# ---------------------------------------------------------------------------
# Secret redaction test
# ---------------------------------------------------------------------------

def test_secret_evidence_is_redacted(analyzer):
    content = 'token = "ghp_realtoken12345"\n'
    issues = analyzer._detect_secrets(content, "test.py")
    for issue in issues:
        assert "ghp_realtoken12345" not in issue.evidence, (
            "Real secret value must never appear in issue evidence"
        )


# ---------------------------------------------------------------------------
# File analysis integration test (no GitHub, pure content)
# ---------------------------------------------------------------------------

def test_file_analysis_has_issues_for_bad_code(analyzer):
    """A file with bare except, no docstrings, and deep nesting should produce issues."""
    bad_code = (
        "import os\n"
        "import sys\n"
        "\n"
        "def do_something():\n"
        "    try:\n"
        "        for x in range(10):\n"
        "            for y in range(10):\n"
        "                for z in range(10):\n"
        "                    for w in range(10):\n"
        "                        for v in range(10):\n"
        "                            result = x + y + z + w + v\n"
        "    except:\n"
        "        pass\n"
    )
    # Patch pylint to return a stable score so the test is deterministic
    with patch.object(analyzer, "_run_pylint", return_value=(5.0, [])):
        fa = analyzer._analyze_python_file("bad_code.py", bad_code)

    assert len(fa.issues) > 0
    issue_types = {i.issue_type for i in fa.issues}
    # Should catch at least bare_except or deep_nesting
    assert issue_types & {"bare_except", "deep_nesting", "no_docstring"}


def test_file_score_clamped_between_1_and_10(analyzer):
    """Even a catastrophically bad file should never score below 1.0 or above 10.0."""
    # Create a file with many critical issues manually
    nightmare_code = (
        'password = "hunter2"\n'
        'api_key = "sk-realkey12345"\n'
        'token = "ghp_mytoken99"\n'
        "def a():\n"
        "    try:\n"
        "        pass\n"
        "    except:\n"
        "        pass\n"
        "def b():\n"
        "    try:\n"
        "        pass\n"
        "    except:\n"
        "        pass\n"
    )
    with patch.object(analyzer, "_run_pylint", return_value=(1.0, [])):
        fa = analyzer._analyze_python_file("nightmare.py", nightmare_code)

    assert fa.pylint_score >= 1.0, f"Score went below 1.0: {fa.pylint_score}"
    assert fa.pylint_score <= 10.0, f"Score went above 10.0: {fa.pylint_score}"
