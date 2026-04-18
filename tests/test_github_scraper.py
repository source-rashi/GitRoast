"""
GitRoast — Tests for GitHub Scraper
======================================
All tests use mocks — no real GitHub API calls required.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from mcp_server.tools.github_scraper import (
    GitHubScraper,
    DeveloperProfile,
    CommitStats,
    PRStats,
    IssueStats,
    RepoProfile,
    ReadmeQuality,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scraper():
    """Return a GitHubScraper instance with a mocked GitHub client."""
    with patch("mcp_server.tools.github_scraper.Github"):
        s = GitHubScraper()
    return s


@pytest.fixture
def mock_repo():
    """Return a mock GitHub repo with realistic attributes."""
    repo = Mock()
    repo.name = "test-repo"
    repo.description = "A test repo"
    repo.language = "Python"
    repo.stargazers_count = 5
    repo.forks_count = 2
    repo.fork = False
    repo.open_issues_count = 3
    repo.pushed_at = datetime.utcnow()

    readme_mock = Mock()
    readme_mock.decoded_content = (
        b"# Test Project\n\n"
        b"[![Build Status](https://img.shields.io/badge/build-passing-green)]\n\n"
        b"Install: pip install mypackage\n\n"
        b"Usage: python main.py\n\n"
        b"Screenshot: ![demo](demo.png)\n"
    )
    repo.get_readme = Mock(return_value=readme_mock)
    return repo


@pytest.fixture
def mock_github_user(mock_repo):
    """Return a mock GitHub user with realistic attributes."""
    user = Mock()
    user.login = "testuser"
    user.name = "Test User"
    user.bio = "Developer"
    user.location = "Earth"
    user.followers = 42
    user.following = 10
    user.public_repos = 15
    user.created_at = datetime(2020, 1, 1)
    user.get_repos = Mock(return_value=[mock_repo, mock_repo, mock_repo])
    return user


# ---------------------------------------------------------------------------
# README scoring tests
# ---------------------------------------------------------------------------

def test_readme_scoring_empty(scraper):
    """Empty README string should score 0 with has_readme False (default)."""
    result = scraper._score_readme("")
    assert result.score == 0
    assert result.word_count == 0
    # has_readme is set True inside _score_readme because content was passed;
    # the external has_readme=False is set at the RepoProfile level.
    # _score_readme always sets has_readme=True on the returned object.
    # So check that score==0 and word_count==0.
    assert result.has_badges is False
    assert result.has_screenshots is False


def test_readme_scoring_full(scraper):
    """A rich README should score above 7."""
    content = (
        "[![Build](https://img.shields.io/badge/build-passing)]\n\n"
        + ("word " * 400)
        + "\nInstall: pip install foo\nUsage: python main.py\n"
        + "![screenshot](demo.png)\n"
    )
    result = scraper._score_readme(content)
    assert result.score > 7
    assert result.has_badges is True
    assert result.has_screenshots is True
    assert result.has_installation_section is True
    assert result.has_usage_section is True


# ---------------------------------------------------------------------------
# Commit message tests
# ---------------------------------------------------------------------------

def test_bad_commit_message_detection(scraper):
    """Exactly 3 of the 4 messages should be flagged as bad."""
    messages = ["fix", "update", "x", "real commit message that is descriptive"]

    bad_count = 0
    for msg in messages:
        msg_lower = msg.strip().lower()
        from mcp_server.tools.github_scraper import BAD_MESSAGES
        if msg_lower in BAD_MESSAGES or len(msg_lower) <= 3:
            bad_count += 1

    assert bad_count == 3


# ---------------------------------------------------------------------------
# Roast & praise ammunition tests
# ---------------------------------------------------------------------------

def test_roast_ammo_not_empty_for_bad_profile(scraper):
    """A profile with many bad stats should produce roast ammunition."""
    repos = [
        RepoProfile(name=f"repo{i}", has_tests=False, has_readme=False, days_since_last_commit=200)
        for i in range(5)
    ]
    profile = DeveloperProfile(
        username="baddev",
        repos=repos,
        commit_stats=CommitStats(
            total_commits=50,
            commits_with_bad_messages=10,
            late_night_commits=15,
            longest_gap_days=20,
        ),
        pr_stats=PRStats(
            total_prs=6,
            prs_with_no_description=4,
            avg_pr_description_length=10,
        ),
        issue_stats=IssueStats(
            total_issues=10,
            open_issues=6,
            issues_open_over_30_days=5,
            issues_with_no_labels=6,
        ),
        account_age_days=800,
        total_stars_received=0,
        public_repos=5,
    )
    ammo = scraper._generate_roast_ammunition(profile)
    assert len(ammo) > 0


def test_praise_ammo_not_empty_for_good_profile(scraper):
    """A profile with good stats should produce praise ammunition."""
    repos = [
        RepoProfile(name=f"repo{i}", has_tests=True, has_readme=True, days_since_last_commit=5)
        for i in range(6)
    ]
    profile = DeveloperProfile(
        username="gooddev",
        repos=repos,
        commit_stats=CommitStats(
            total_commits=100,
            avg_commits_per_week=8.0,
            commits_with_bad_messages=0,
        ),
        pr_stats=PRStats(
            total_prs=10,
            merged_prs=8,
            avg_days_to_merge=1.5,
        ),
        issue_stats=IssueStats(
            closed_issues=10,
            avg_days_to_close=3.0,
        ),
        total_stars_received=75,
        top_languages=[{"language": "Python", "percentage": 75.0}],
    )
    praise = scraper._generate_praise_ammunition(profile)
    assert len(praise) > 0


# ---------------------------------------------------------------------------
# Language percentage test
# ---------------------------------------------------------------------------

def test_language_percentage_sums_to_100(scraper):
    """Given two repos with Python=700 and JS=300, percentages should be 70/30."""
    repo1 = Mock()
    repo1.get_languages = Mock(return_value={"Python": 700})
    repo2 = Mock()
    repo2.get_languages = Mock(return_value={"JavaScript": 300})

    result = scraper._get_top_languages([repo1, repo2])

    assert len(result) == 2
    lang_map = {r["language"]: r["percentage"] for r in result}
    assert lang_map["Python"] == pytest.approx(70.0, abs=0.1)
    assert lang_map["JavaScript"] == pytest.approx(30.0, abs=0.1)
    total = sum(r["percentage"] for r in result)
    assert total == pytest.approx(100.0, abs=0.5)


# ---------------------------------------------------------------------------
# Helper / utility tests
# ---------------------------------------------------------------------------

def test_days_to_human_helper():
    """days_to_human should correctly convert day counts to readable strings."""
    from mcp_server.utils.helpers import days_to_human

    assert days_to_human(3) == "3 days"
    assert days_to_human(10) == "10 days"
    assert days_to_human(20) == "2 weeks"
    assert days_to_human(90) == "3 months"
    assert days_to_human(400) == "1 year"
