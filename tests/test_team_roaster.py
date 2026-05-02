"""
Tests for TeamRoaster — Phase 5
"""
import pytest
from mcp_server.tools.team_roaster import (
    TeamRoaster,
    TeamReport,
    MemberSummary,
    TeamLeaderboard,
)
from mcp_server.tools.github_scraper import (
    DeveloperProfile,
    CommitStats,
    PRStats,
    IssueStats,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_profile(
    username: str,
    commits: int = 30,
    bad_messages: int = 2,
    late_night: int = 3,
    stars: int = 10,
    repos: int = 5,
    followers: int = 5,
    top_lang: str = "Python",
    pr_merge_days: float = 2.0,
    readme_count: int = 3,
    test_count: int = 1,
) -> DeveloperProfile:
    """Create a mock DeveloperProfile for testing."""
    from mcp_server.tools.github_scraper import RepoProfile

    repos_list = []
    for i in range(repos):
        repos_list.append(RepoProfile(
            name=f"repo-{i}",
            has_readme=i < readme_count,
            has_tests=i < test_count,
            stars=stars // max(repos, 1),
        ))

    return DeveloperProfile(
        username=username,
        name=username.title(),
        public_repos=repos,
        total_stars_received=stars,
        followers=followers,
        account_age_days=400,
        top_languages=[{"language": top_lang, "percentage": 70.0}] if top_lang else [],
        repos=repos_list,
        commit_stats=CommitStats(
            total_commits=commits,
            avg_commits_per_week=round(commits / 13, 2),
            commits_with_bad_messages=bad_messages,
            late_night_commits=late_night,
        ),
        pr_stats=PRStats(
            total_prs=10,
            merged_prs=8,
            avg_days_to_merge=pr_merge_days,
        ),
        issue_stats=IssueStats(),
    )


class MockGroqClient:
    pass


# ---------------------------------------------------------------------------
# Tests — MemberSummary
# ---------------------------------------------------------------------------

class TestBuildMemberSummary:
    def test_builds_correct_username(self):
        roaster = TeamRoaster(MockGroqClient())
        profile = _make_profile("alice")
        summary = roaster._build_member_summary(profile)
        assert summary.username == "alice"

    def test_builds_correct_commit_stats(self):
        roaster = TeamRoaster(MockGroqClient())
        profile = _make_profile("bob", commits=50, bad_messages=5, late_night=12)
        summary = roaster._build_member_summary(profile)
        assert summary.total_commits_90d == 50
        assert summary.bad_commit_messages == 5
        assert summary.late_night_commits == 12

    def test_builds_correct_repo_counts(self):
        roaster = TeamRoaster(MockGroqClient())
        profile = _make_profile("charlie", repos=6, readme_count=4, test_count=2)
        summary = roaster._build_member_summary(profile)
        assert summary.repos_with_readme == 4
        assert summary.repos_with_tests == 2

    def test_top_language_na_when_empty(self):
        roaster = TeamRoaster(MockGroqClient())
        profile = _make_profile("dan", top_lang="")
        summary = roaster._build_member_summary(profile)
        assert summary.top_language == "N/A"


# ---------------------------------------------------------------------------
# Tests — Leaderboard
# ---------------------------------------------------------------------------

class TestLeaderboard:
    def _make_members(self) -> list[MemberSummary]:
        return [
            MemberSummary(
                username="alice", total_commits_90d=100, avg_commits_per_week=7.7,
                bad_commit_messages=2, late_night_commits=5, total_stars=50,
                repos_with_readme=5, repos_with_tests=3, pr_merge_speed_days=1.0,
            ),
            MemberSummary(
                username="bob", total_commits_90d=20, avg_commits_per_week=1.5,
                bad_commit_messages=10, late_night_commits=15, total_stars=200,
                repos_with_readme=2, repos_with_tests=0, pr_merge_speed_days=5.0,
            ),
            MemberSummary(
                username="charlie", total_commits_90d=60, avg_commits_per_week=4.6,
                bad_commit_messages=0, late_night_commits=1, total_stars=10,
                repos_with_readme=8, repos_with_tests=5, pr_merge_speed_days=0.5,
            ),
        ]

    def test_most_active(self):
        roaster = TeamRoaster(MockGroqClient())
        lb = roaster._build_leaderboard(self._make_members())
        assert lb.most_active == "alice"

    def test_most_starred(self):
        roaster = TeamRoaster(MockGroqClient())
        lb = roaster._build_leaderboard(self._make_members())
        assert lb.most_starred == "bob"

    def test_best_documented(self):
        roaster = TeamRoaster(MockGroqClient())
        lb = roaster._build_leaderboard(self._make_members())
        assert lb.best_documented == "charlie"

    def test_best_tested(self):
        roaster = TeamRoaster(MockGroqClient())
        lb = roaster._build_leaderboard(self._make_members())
        assert lb.best_tested == "charlie"

    def test_biggest_night_owl(self):
        roaster = TeamRoaster(MockGroqClient())
        lb = roaster._build_leaderboard(self._make_members())
        assert lb.biggest_night_owl == "bob"

    def test_best_commit_hygiene(self):
        roaster = TeamRoaster(MockGroqClient())
        lb = roaster._build_leaderboard(self._make_members())
        # charlie has 0 bad messages out of 60 commits
        assert lb.best_commit_hygiene == "charlie"

    def test_fastest_pr_merger(self):
        roaster = TeamRoaster(MockGroqClient())
        lb = roaster._build_leaderboard(self._make_members())
        assert lb.fastest_pr_merger == "charlie"


# ---------------------------------------------------------------------------
# Tests — Roast Ammunition
# ---------------------------------------------------------------------------

class TestTeamRoastAmmo:
    def test_commitment_gap_detected(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(
                username="hero", total_commits_90d=100, avg_commits_per_week=7.7,
                bad_commit_messages=0, total_stars=0,
            ),
            MemberSummary(
                username="ghost", total_commits_90d=0, avg_commits_per_week=0,
                bad_commit_messages=0, total_stars=0,
            ),
        ]
        lb = roaster._build_leaderboard(members)
        ammo = roaster._generate_team_roast_ammo(members, lb)
        assert any("carrying" in a.lower() or "solo" in a.lower() for a in ammo)

    def test_bad_commit_messages_called_out(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(
                username="offender", total_commits_90d=50,
                bad_commit_messages=15, total_stars=0,
            ),
            MemberSummary(
                username="clean", total_commits_90d=50,
                bad_commit_messages=0, total_stars=0,
            ),
        ]
        lb = roaster._build_leaderboard(members)
        ammo = roaster._generate_team_roast_ammo(members, lb)
        assert any("offender" in a for a in ammo)

    def test_no_tests_called_out(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(username="lazy", repos_with_tests=0, total_stars=0),
            MemberSummary(username="diligent", repos_with_tests=3, total_stars=0),
        ]
        lb = roaster._build_leaderboard(members)
        ammo = roaster._generate_team_roast_ammo(members, lb)
        assert any("lazy" in a for a in ammo)


# ---------------------------------------------------------------------------
# Tests — Praise Ammunition
# ---------------------------------------------------------------------------

class TestTeamPraiseAmmo:
    def test_team_consistency_praised(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(username="a", avg_commits_per_week=5.0, total_stars=0),
            MemberSummary(username="b", avg_commits_per_week=4.0, total_stars=0),
        ]
        lb = roaster._build_leaderboard(members)
        praise = roaster._generate_team_praise_ammo(members, lb)
        assert any("rhythm" in p.lower() for p in praise)

    def test_collective_stars_praised(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(username="a", total_stars=80),
            MemberSummary(username="b", total_stars=50),
        ]
        lb = roaster._build_leaderboard(members)
        praise = roaster._generate_team_praise_ammo(members, lb)
        assert any("stars" in p.lower() for p in praise)


# ---------------------------------------------------------------------------
# Tests — Team Stats
# ---------------------------------------------------------------------------

class TestTeamStats:
    def test_team_size(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(username="a"),
            MemberSummary(username="b"),
            MemberSummary(username="c"),
        ]
        stats = roaster._compute_team_stats(members)
        assert stats["team_size"] == 3

    def test_total_commits(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(username="a", total_commits_90d=30),
            MemberSummary(username="b", total_commits_90d=50),
        ]
        stats = roaster._compute_team_stats(members)
        assert stats["total_commits_90d"] == 80

    def test_language_distribution(self):
        roaster = TeamRoaster(MockGroqClient())
        members = [
            MemberSummary(username="a", top_language="Python"),
            MemberSummary(username="b", top_language="Python"),
            MemberSummary(username="c", top_language="JavaScript"),
        ]
        stats = roaster._compute_team_stats(members)
        assert stats["language_distribution"]["Python"] == 2
        assert stats["language_distribution"]["JavaScript"] == 1


# ---------------------------------------------------------------------------
# Tests — Formatting
# ---------------------------------------------------------------------------

class TestFormatTeamReport:
    def test_report_contains_leaderboard(self):
        roaster = TeamRoaster(MockGroqClient())
        report = TeamReport(
            members=[MemberSummary(username="alice"), MemberSummary(username="bob")],
            leaderboard=TeamLeaderboard(most_active="alice", most_starred="bob"),
            team_stats={"team_size": 2, "total_commits_90d": 100, "total_stars": 50, "total_repos": 10},
        )
        text = roaster.format_team_report(report, "comedian")
        assert "Leaderboard" in text
        assert "alice" in text

    def test_report_contains_comparison_table(self):
        roaster = TeamRoaster(MockGroqClient())
        report = TeamReport(
            members=[
                MemberSummary(username="alice", avg_commits_per_week=5.0),
                MemberSummary(username="bob", avg_commits_per_week=2.0),
            ],
            leaderboard=TeamLeaderboard(),
            team_stats={"team_size": 2, "total_commits_90d": 0, "total_stars": 0, "total_repos": 0},
        )
        text = roaster.format_team_report(report, "comedian")
        assert "Member Comparison" in text
        assert "5.0" in text
