"""
Tests for competitor_researcher.py — Phase 4

All tests are fully mocked — no real GitHub or Groq API calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from mcp_server.tools.competitor_researcher import (
    CompetitorResearcher,
    CompetitorRepo,
    DifferentiationAngle,
    CompetitorReport,
    STOP_WORDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_repo(
    name="test-tool",
    full_name="owner/test-tool",
    stars=150,
    forks=20,
    language="Python",
    open_issues=5,
    days_old=30,
    readme_words=300,
    has_readme=True,
    topics=None,
    description="A test tool",
) -> CompetitorRepo:
    """Factory for CompetitorRepo with sane defaults."""
    return CompetitorRepo(
        name=name,
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        description=description,
        stars=stars,
        forks=forks,
        language=language,
        last_updated_days_ago=days_old,
        open_issues=open_issues,
        has_readme=has_readme,
        readme_word_count=readme_words,
        topics=topics or ["tool", "ai"],
        is_actively_maintained=days_old < 90,
        apparent_weaknesses=[],
    )


def make_researcher() -> CompetitorResearcher:
    """Build a CompetitorResearcher with mock Groq client and no real GitHub."""
    groq_client = MagicMock()
    groq_response = MagicMock()
    groq_response.choices = [MagicMock()]
    groq_response.choices[0].message.content = (
        "## \U0001f575\ufe0f Competitor Intelligence Report\n\n"
        "### The Landscape\nLight competition.\n\n"
        "### Top Competitors\n- owner/test-tool — \u2b505 stars — weak docs\n\n"
        "### The Gap In The Market\nMissing personality engine.\n\n"
        "### Your Wedge\nBuild the only tool with a personality engine.\n\n"
        "### Strategic Recommendation: Build it\nProceed.\n\n"
        "### 3 Things To Do This Week\n1. Validate.\n2. Build.\n3. Ship.\n"
    )
    groq_client.chat.completions.create.return_value = groq_response
    # Pass empty string — no real GitHub calls in these tests
    return CompetitorResearcher(groq_client, github_token="")


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    def test_removes_stop_words(self):
        researcher = make_researcher()
        keywords = researcher._extract_keywords("Build a tool for code review")
        assert "a" not in keywords
        assert "for" not in keywords
        assert "build" not in keywords

    def test_returns_meaningful_words(self):
        researcher = make_researcher()
        keywords = researcher._extract_keywords("VS Code extension for GitHub analysis")
        assert "code" in keywords or "extension" in keywords or "github" in keywords or "analysis" in keywords

    def test_max_five_keywords(self):
        researcher = make_researcher()
        idea = "super long idea with many words developer pipeline orchestration intelligence analysis automation"
        keywords = researcher._extract_keywords(idea)
        assert len(keywords) <= 5

    def test_deduplicates_keywords(self):
        researcher = make_researcher()
        keywords = researcher._extract_keywords("developer developer developer tool")
        assert keywords.count("developer") == 1

    def test_adds_compound_terms(self):
        researcher = make_researcher()
        keywords = researcher._extract_keywords("automated code review tool for teams")
        assert "code-review" in keywords

    def test_empty_idea_returns_empty(self):
        researcher = make_researcher()
        keywords = researcher._extract_keywords("")
        assert isinstance(keywords, list)


# ---------------------------------------------------------------------------
# Weakness detection
# ---------------------------------------------------------------------------

class TestDetectWeaknesses:
    def _mock_repo(self, stars=100, issues=5, forks=10):
        repo = MagicMock()
        repo.stargazers_count = stars
        repo.open_issues_count = issues
        repo.forks_count = forks
        return repo

    def test_abandoned_repo_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo()
        weaknesses = researcher._detect_weaknesses(repo, "", 400, 0, [])
        texts = " ".join(weaknesses).lower()
        assert "abandon" in texts

    def test_stale_repo_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo()
        weaknesses = researcher._detect_weaknesses(repo, "has install instructions", 200, 500, ["topic"])
        texts = " ".join(weaknesses).lower()
        assert "stale" in texts

    def test_no_readme_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo()
        weaknesses = researcher._detect_weaknesses(repo, "", 30, 0, ["topic"])
        assert any("readme" in w.lower() or "no readme" in w.lower() for w in weaknesses)

    def test_poor_readme_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo()
        weaknesses = researcher._detect_weaknesses(repo, "short", 30, 50, ["topic"])
        assert any("100 words" in w.lower() or "poor" in w.lower() for w in weaknesses)

    def test_issue_backlog_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo(issues=80)
        weaknesses = researcher._detect_weaknesses(repo, "has install", 30, 300, ["topic"])
        assert any("issue" in w.lower() for w in weaknesses)

    def test_overwhelmed_maintainer_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo(issues=150)
        weaknesses = researcher._detect_weaknesses(repo, "has install", 30, 300, ["topic"])
        assert any("overwhelm" in w.lower() or "100+" in w.lower() for w in weaknesses)

    def test_no_topics_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo()
        weaknesses = researcher._detect_weaknesses(repo, "has install", 30, 300, [])
        assert any("topic" in w.lower() or "discoverabil" in w.lower() for w in weaknesses)

    def test_no_install_instructions_flagged(self):
        researcher = make_researcher()
        repo = self._mock_repo()
        weaknesses = researcher._detect_weaknesses(repo, "some content without instructions", 30, 300, ["topic"])
        assert any("install" in w.lower() for w in weaknesses)

    def test_healthy_repo_has_few_weaknesses(self):
        researcher = make_researcher()
        repo = self._mock_repo(stars=500, issues=10, forks=50)
        weaknesses = researcher._detect_weaknesses(
            repo, "install using pip. great tool for everyone.", 10, 800, ["ai", "tool"]
        )
        # A healthy repo should have 0 or 1 weaknesses max
        assert len(weaknesses) <= 1


# ---------------------------------------------------------------------------
# Differentiation angles
# ---------------------------------------------------------------------------

class TestFindDifferentiationAngles:
    def test_empty_competitors_returns_first_mover(self):
        researcher = make_researcher()
        angles = researcher._find_differentiation_angles("my idea", [])
        assert len(angles) == 1
        assert "first mover" in angles[0].angle.lower()
        assert angles[0].strength == "strong"

    def test_mostly_abandoned_triggers_maintenance_angle(self):
        researcher = make_researcher()
        # 3 inactive, 1 active
        inactive = [make_repo(days_old=200) for _ in range(3)]
        active = [make_repo(days_old=10)]
        angles = researcher._find_differentiation_angles("idea", inactive + active)
        texts = " ".join(a.angle for a in angles).lower()
        assert "abandon" in texts or "maintained" in texts

    def test_poor_docs_angle_triggered(self):
        researcher = make_researcher()
        repos = [make_repo(readme_words=50) for _ in range(3)]
        angles = researcher._find_differentiation_angles("idea", repos)
        texts = " ".join(a.angle for a in angles).lower()
        assert "doc" in texts

    def test_issue_backlog_angle_triggered(self):
        researcher = make_researcher()
        repos = [make_repo(open_issues=80)]
        angles = researcher._find_differentiation_angles("idea", repos)
        texts = " ".join(a.angle for a in angles).lower()
        assert "overwhelm" in texts or "support" in texts

    def test_all_same_language_triggers_angle(self):
        researcher = make_researcher()
        repos = [make_repo(language="JavaScript") for _ in range(3)]
        angles = researcher._find_differentiation_angles("idea", repos)
        texts = " ".join(a.angle for a in angles).lower()
        assert "javascript" in texts or "language" in texts

    def test_no_leader_angle_triggered(self):
        researcher = make_researcher()
        repos = [make_repo(stars=50) for _ in range(4)]
        angles = researcher._find_differentiation_angles("idea", repos)
        texts = " ".join(a.angle for a in angles).lower()
        assert "dominant" in texts or "leader" in texts or "market" in texts

    def test_returns_list_of_differentiation_angles(self):
        researcher = make_researcher()
        angles = researcher._find_differentiation_angles("idea", [make_repo()])
        assert isinstance(angles, list)
        for a in angles:
            assert isinstance(a, DifferentiationAngle)
            assert a.strength in ("strong", "medium", "weak")


# ---------------------------------------------------------------------------
# Market saturation classification
# ---------------------------------------------------------------------------

class TestMarketSaturation:
    @pytest.mark.asyncio
    async def test_empty_market(self):
        researcher = make_researcher()
        with patch.object(researcher, "_extract_keywords", return_value=["kw"]), \
             patch.object(researcher, "_search_github_repos", return_value=[]), \
             patch.object(researcher, "_find_differentiation_angles", return_value=[]), \
             patch.object(researcher, "_synthesize_with_groq", new=AsyncMock(return_value=("synth", "wedge", "Build it"))):
            report = await researcher.research("a test idea for research")
        assert report.market_saturation == "empty"

    @pytest.mark.asyncio
    async def test_light_market(self):
        researcher = make_researcher()
        repos = [make_repo(full_name=f"o/r{i}") for i in range(3)]
        with patch.object(researcher, "_extract_keywords", return_value=["kw"]), \
             patch.object(researcher, "_search_github_repos", return_value=repos), \
             patch.object(researcher, "_find_differentiation_angles", return_value=[]), \
             patch.object(researcher, "_synthesize_with_groq", new=AsyncMock(return_value=("synth", "wedge", "Build it"))):
            report = await researcher.research("a test idea for research")
        assert report.market_saturation == "light"

    @pytest.mark.asyncio
    async def test_moderate_market(self):
        researcher = make_researcher()
        repos = [make_repo(full_name=f"o/r{i}") for i in range(10)]
        with patch.object(researcher, "_extract_keywords", return_value=["kw"]), \
             patch.object(researcher, "_search_github_repos", return_value=repos), \
             patch.object(researcher, "_find_differentiation_angles", return_value=[]), \
             patch.object(researcher, "_synthesize_with_groq", new=AsyncMock(return_value=("synth", "wedge", "Niche down"))):
            report = await researcher.research("a test idea for research")
        assert report.market_saturation == "moderate"

    @pytest.mark.asyncio
    async def test_saturated_market(self):
        researcher = make_researcher()
        repos = [make_repo(full_name=f"o/r{i}") for i in range(20)]
        with patch.object(researcher, "_extract_keywords", return_value=["kw"]), \
             patch.object(researcher, "_search_github_repos", return_value=repos), \
             patch.object(researcher, "_find_differentiation_angles", return_value=[]), \
             patch.object(researcher, "_synthesize_with_groq", new=AsyncMock(return_value=("synth", "wedge", "Reconsider"))):
            report = await researcher.research("a test idea for research")
        assert report.market_saturation == "saturated"


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------

class TestCompetitorReport:
    def test_report_model_fields(self):
        report = CompetitorReport(
            idea="test idea",
            search_keywords=["test", "idea"],
            competitors_found=[],
            total_searched=0,
            market_saturation="empty",
            differentiation_angles=[],
            synthesis="synthesis text",
            your_wedge="your wedge text",
            recommendation="Build it",
            timestamp="2024-01-01T00:00:00+00:00",
        )
        assert report.idea == "test idea"
        assert report.market_saturation == "empty"
        assert report.total_searched == 0

    def test_competitor_repo_model_fields(self):
        repo = make_repo()
        assert repo.stars == 150
        assert repo.is_actively_maintained is True
        assert isinstance(repo.topics, list)
        assert isinstance(repo.apparent_weaknesses, list)

    def test_differentiation_angle_model_fields(self):
        angle = DifferentiationAngle(
            angle="No competitors have personality modes",
            evidence="0 of 5 competitors have this feature",
            strength="strong",
        )
        assert angle.strength == "strong"


# ---------------------------------------------------------------------------
# Format report for display
# ---------------------------------------------------------------------------

class TestFormatReportForDisplay:
    def test_format_contains_competitor_table(self):
        researcher = make_researcher()
        report = CompetitorReport(
            idea="Test idea",
            search_keywords=["test"],
            competitors_found=[make_repo()],
            total_searched=1,
            market_saturation="light",
            differentiation_angles=[
                DifferentiationAngle(
                    angle="Win with docs",
                    evidence="3 competitors poor docs",
                    strength="strong",
                )
            ],
            synthesis="## The Landscape\nLight market.\n\n### Your Wedge\nBetter docs.",
            your_wedge="Build with great documentation.",
            recommendation="Build it",
            timestamp="2024-01-01T00:00:00+00:00",
        )
        text = researcher.format_report_for_display(report)
        assert "owner/test-tool" in text
        assert "Win with docs" in text
        assert "Build with great documentation." in text
        assert "Build it" in text

    def test_format_shows_saturation_emoji(self):
        researcher = make_researcher()
        for saturation, expected_emoji in [("empty", "🟢"), ("saturated", "🔴")]:
            report = CompetitorReport(
                idea="idea",
                search_keywords=[],
                competitors_found=[],
                total_searched=0,
                market_saturation=saturation,
                differentiation_angles=[],
                synthesis="",
                your_wedge="wedge",
                recommendation="Build it",
                timestamp="2024-01-01T00:00:00+00:00",
            )
            text = researcher.format_report_for_display(report)
            assert expected_emoji in text

    def test_format_returns_string(self):
        researcher = make_researcher()
        report = CompetitorReport(
            idea="idea",
            search_keywords=[],
            competitors_found=[],
            total_searched=0,
            market_saturation="empty",
            differentiation_angles=[],
            synthesis="synth",
            your_wedge="wedge",
            recommendation="Build it",
            timestamp="2024-01-01T00:00:00",
        )
        result = researcher.format_report_for_display(report)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Section extractor
# ---------------------------------------------------------------------------

class TestExtractSection:
    def test_extracts_wedge_section(self):
        researcher = make_researcher()
        text = (
            "## Intro\nsome intro\n\n"
            "### Your Wedge\nBuild the only tool with personality.\n\n"
            "### Next Section\nmore content"
        )
        result = researcher._extract_section(text, "Your Wedge")
        assert "Build the only tool with personality." in result
        assert "Next Section" not in result

    def test_returns_empty_for_missing_section(self):
        researcher = make_researcher()
        result = researcher._extract_section("## Some Section\ncontent", "Nonexistent")
        assert result == ""
