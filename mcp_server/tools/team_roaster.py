"""
GitRoast — Team Roast Engine (Phase 5)
=========================================
Analyze multiple GitHub developers simultaneously and generate:
- Side-by-side comparison across 7+ dimensions
- Team leaderboard with rankings
- A group roast grounded in comparative data
- Team health report with actionable advice

Uses the existing GitHubScraper and caches profiles via the orchestrator.
100% free — GitHub API + Groq LLM. No credit card required.
"""

import asyncio
from typing import Optional

from pydantic import BaseModel, Field
from loguru import logger

from mcp_server.tools.github_scraper import GitHubScraper, DeveloperProfile


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class MemberSummary(BaseModel):
    username: str
    total_commits_90d: int = 0
    avg_commits_per_week: float = 0.0
    bad_commit_messages: int = 0
    late_night_commits: int = 0
    total_stars: int = 0
    total_repos: int = 0
    repos_with_readme: int = 0
    repos_with_tests: int = 0
    top_language: str = "N/A"
    pr_merge_speed_days: float = 0.0
    account_age_days: int = 0
    followers: int = 0


class TeamLeaderboard(BaseModel):
    most_active: str = ""
    best_commit_hygiene: str = ""
    most_starred: str = ""
    best_documented: str = ""
    best_tested: str = ""
    fastest_pr_merger: str = ""
    biggest_night_owl: str = ""


class TeamReport(BaseModel):
    members: list[MemberSummary] = []
    leaderboard: TeamLeaderboard = Field(default_factory=TeamLeaderboard)
    team_roast_ammunition: list[str] = []
    team_praise_ammunition: list[str] = []
    team_stats: dict = {}


# ---------------------------------------------------------------------------
# TeamRoaster
# ---------------------------------------------------------------------------

class TeamRoaster:
    """Compare multiple GitHub developers and generate team intelligence."""

    MAX_TEAM_SIZE = 6  # Hard cap to avoid API abuse

    def __init__(self, groq_client):
        self.groq_client = groq_client

    async def analyze_team(
        self,
        usernames: list[str],
        scraper: GitHubScraper,
        cached_profiles: dict[str, DeveloperProfile],
    ) -> TeamReport:
        """Analyze a list of GitHub usernames and generate a team report."""
        usernames = [u.strip() for u in usernames if u.strip()][:self.MAX_TEAM_SIZE]

        if len(usernames) < 2:
            raise ValueError("Team roast requires at least 2 GitHub usernames.")

        logger.info(f"Team roast starting for {len(usernames)} members: {usernames}")

        # Fetch profiles concurrently (using cache when available)
        profiles: list[DeveloperProfile] = []
        errors: list[str] = []

        async def fetch_one(username: str) -> Optional[DeveloperProfile]:
            key = username.lower()
            if key in cached_profiles:
                logger.info(f"Using cached profile for {username}")
                return cached_profiles[key]
            try:
                profile = await scraper.scrape_developer(username)
                cached_profiles[key] = profile
                return profile
            except Exception as exc:
                errors.append(f"{username}: {exc}")
                logger.warning(f"Failed to fetch {username}: {exc}")
                return None

        results = await asyncio.gather(*[fetch_one(u) for u in usernames])
        profiles = [p for p in results if p is not None]

        if len(profiles) < 2:
            error_str = "; ".join(errors) if errors else "Unknown error"
            raise ValueError(
                f"Could only fetch {len(profiles)} profiles (need at least 2). "
                f"Errors: {error_str}"
            )

        # Build summaries
        members = [self._build_member_summary(p) for p in profiles]

        # Build leaderboard
        leaderboard = self._build_leaderboard(members)

        # Generate ammunition
        roast_ammo = self._generate_team_roast_ammo(members, leaderboard)
        praise_ammo = self._generate_team_praise_ammo(members, leaderboard)

        # Team-wide stats
        team_stats = self._compute_team_stats(members)

        return TeamReport(
            members=members,
            leaderboard=leaderboard,
            team_roast_ammunition=roast_ammo,
            team_praise_ammunition=praise_ammo,
            team_stats=team_stats,
        )

    # ------------------------------------------------------------------
    # Member summary
    # ------------------------------------------------------------------

    def _build_member_summary(self, profile: DeveloperProfile) -> MemberSummary:
        top_lang = (
            profile.top_languages[0]["language"]
            if profile.top_languages
            else "N/A"
        )
        repos_with_readme = sum(1 for r in profile.repos if r.has_readme)
        repos_with_tests = sum(1 for r in profile.repos if r.has_tests)

        return MemberSummary(
            username=profile.username,
            total_commits_90d=profile.commit_stats.total_commits,
            avg_commits_per_week=profile.commit_stats.avg_commits_per_week,
            bad_commit_messages=profile.commit_stats.commits_with_bad_messages,
            late_night_commits=profile.commit_stats.late_night_commits,
            total_stars=profile.total_stars_received,
            total_repos=profile.public_repos,
            repos_with_readme=repos_with_readme,
            repos_with_tests=repos_with_tests,
            top_language=top_lang,
            pr_merge_speed_days=profile.pr_stats.avg_days_to_merge,
            account_age_days=profile.account_age_days,
            followers=profile.followers,
        )

    # ------------------------------------------------------------------
    # Leaderboard
    # ------------------------------------------------------------------

    def _build_leaderboard(self, members: list[MemberSummary]) -> TeamLeaderboard:
        def best(key, reverse=True):
            sorted_m = sorted(members, key=lambda m: getattr(m, key), reverse=reverse)
            return sorted_m[0].username if sorted_m else ""

        def best_ratio(num_key, denom_key):
            ratios = []
            for m in members:
                denom = getattr(m, denom_key)
                num = getattr(m, num_key)
                ratios.append((m.username, num / denom if denom > 0 else 0))
            ratios.sort(key=lambda x: x[1], reverse=True)
            return ratios[0][0] if ratios else ""

        # Best commit hygiene = fewest bad messages relative to total
        hygiene_scores = []
        for m in members:
            if m.total_commits_90d > 0:
                ratio = m.bad_commit_messages / m.total_commits_90d
            else:
                ratio = 1.0  # No commits = worst
            hygiene_scores.append((m.username, ratio))
        hygiene_scores.sort(key=lambda x: x[1])  # lowest ratio = best
        best_hygiene = hygiene_scores[0][0] if hygiene_scores else ""

        # Fastest PR merger = lowest avg days (only if they have PRs)
        pr_members = [m for m in members if m.pr_merge_speed_days > 0]
        fastest_pr = min(pr_members, key=lambda m: m.pr_merge_speed_days).username if pr_members else best("total_commits_90d")

        return TeamLeaderboard(
            most_active=best("total_commits_90d"),
            best_commit_hygiene=best_hygiene,
            most_starred=best("total_stars"),
            best_documented=best("repos_with_readme"),
            best_tested=best("repos_with_tests"),
            fastest_pr_merger=fastest_pr,
            biggest_night_owl=best("late_night_commits"),
        )

    # ------------------------------------------------------------------
    # Roast ammunition
    # ------------------------------------------------------------------

    def _generate_team_roast_ammo(
        self, members: list[MemberSummary], lb: TeamLeaderboard
    ) -> list[str]:
        ammo: list[str] = []

        # Commitment gap
        commits = sorted(members, key=lambda m: m.total_commits_90d, reverse=True)
        if len(commits) >= 2:
            top, bottom = commits[0], commits[-1]
            if top.total_commits_90d > 0 and bottom.total_commits_90d == 0:
                ammo.append(
                    f"{top.username} pushed {top.total_commits_90d} commits in 90 days. "
                    f"{bottom.username} pushed zero. One of you is carrying this team."
                )
            elif top.total_commits_90d > 3 * max(bottom.total_commits_90d, 1):
                ammo.append(
                    f"{top.username} commits {top.avg_commits_per_week:.1f}x/week vs "
                    f"{bottom.username}'s {bottom.avg_commits_per_week:.1f}x/week. "
                    "That's not a team — that's a solo act with an audience."
                )

        # Bad messages comparison
        worst_msgs = max(members, key=lambda m: m.bad_commit_messages)
        if worst_msgs.bad_commit_messages >= 5:
            ammo.append(
                f"{worst_msgs.username} has {worst_msgs.bad_commit_messages} lazy commit messages. "
                f"The rest of the team is covering for your git crimes."
            )

        # Night owl callout
        owl = max(members, key=lambda m: m.late_night_commits)
        if owl.late_night_commits >= 10:
            ammo.append(
                f"{owl.username} has {owl.late_night_commits} commits between 11pm and 4am. "
                f"Someone check on them."
            )

        # No tests
        no_tests = [m for m in members if m.repos_with_tests == 0]
        if no_tests:
            names = ", ".join(m.username for m in no_tests)
            ammo.append(
                f"{names} — zero test files found. "
                "Your deployment strategy is apparently 'prayer'."
            )

        # Documentation gap
        no_docs = [m for m in members if m.repos_with_readme <= 1]
        if no_docs:
            names = ", ".join(m.username for m in no_docs)
            ammo.append(
                f"{names} have almost no READMEs. "
                "Future maintainers will need a Ouija board."
            )

        # Stars disparity
        stars_sorted = sorted(members, key=lambda m: m.total_stars, reverse=True)
        if len(stars_sorted) >= 2:
            if stars_sorted[0].total_stars > 10 * max(stars_sorted[-1].total_stars, 1):
                ammo.append(
                    f"{stars_sorted[0].username} has {stars_sorted[0].total_stars} stars. "
                    f"{stars_sorted[-1].username} has {stars_sorted[-1].total_stars}. "
                    "One of you is shipping products, the other is shipping PRs to nowhere."
                )

        return ammo

    # ------------------------------------------------------------------
    # Praise ammunition
    # ------------------------------------------------------------------

    def _generate_team_praise_ammo(
        self, members: list[MemberSummary], lb: TeamLeaderboard
    ) -> list[str]:
        praise: list[str] = []

        # Team consistency
        active = [m for m in members if m.avg_commits_per_week >= 3]
        if len(active) >= 2:
            praise.append(
                f"{len(active)} of {len(members)} team members commit 3+ times per week. "
                "This team has rhythm."
            )

        # Good hygiene across the board
        total_bad = sum(m.bad_commit_messages for m in members)
        total_commits = sum(m.total_commits_90d for m in members)
        if total_commits > 20 and total_bad / max(total_commits, 1) < 0.1:
            praise.append(
                "Less than 10% bad commit messages across the entire team. "
                "Clean git history is a superpower."
            )

        # Good documentation
        well_documented = [m for m in members if m.repos_with_readme >= 3]
        if len(well_documented) == len(members):
            praise.append(
                "Every team member has 3+ repos with READMEs. "
                "A team that documents together, ships together."
            )

        # Testing culture
        testers = [m for m in members if m.repos_with_tests >= 2]
        if len(testers) >= 2:
            praise.append(
                f"{len(testers)} team members have test files. "
                "A testing culture is forming. Protect it."
            )

        # Collective stars
        total_stars = sum(m.total_stars for m in members)
        if total_stars >= 100:
            praise.append(
                f"{total_stars} collective stars across the team. "
                "People are paying attention to what you're building."
            )

        return praise

    # ------------------------------------------------------------------
    # Team stats
    # ------------------------------------------------------------------

    def _compute_team_stats(self, members: list[MemberSummary]) -> dict:
        total_commits = sum(m.total_commits_90d for m in members)
        total_stars = sum(m.total_stars for m in members)
        total_repos = sum(m.total_repos for m in members)
        avg_commits_week = (
            sum(m.avg_commits_per_week for m in members) / len(members)
            if members
            else 0
        )

        # Language distribution
        lang_counter: dict[str, int] = {}
        for m in members:
            if m.top_language != "N/A":
                lang_counter[m.top_language] = lang_counter.get(m.top_language, 0) + 1

        return {
            "team_size": len(members),
            "total_commits_90d": total_commits,
            "avg_commits_per_week": round(avg_commits_week, 1),
            "total_stars": total_stars,
            "total_repos": total_repos,
            "language_distribution": lang_counter,
        }

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_team_report(self, report: TeamReport, personality: str) -> str:
        """Format a TeamReport into rich Markdown for display."""
        lines = [
            "# 👥 GitRoast — Team Roast Report",
            "",
            f"**Team Size:** {report.team_stats.get('team_size', 0)} developers",
            f"**Combined Commits (90d):** {report.team_stats.get('total_commits_90d', 0)}",
            f"**Combined Stars:** {report.team_stats.get('total_stars', 0)}",
            f"**Combined Repos:** {report.team_stats.get('total_repos', 0)}",
            "",
        ]

        # Leaderboard
        lb = report.leaderboard
        lines.append("## 🏆 Team Leaderboard")
        lines.append("")
        lines.append("| Category | Winner |")
        lines.append("|----------|--------|")
        lines.append(f"| 🔥 Most Active | **{lb.most_active}** |")
        lines.append(f"| 📝 Best Commit Messages | **{lb.best_commit_hygiene}** |")
        lines.append(f"| ⭐ Most Starred | **{lb.most_starred}** |")
        lines.append(f"| 📄 Best Documented | **{lb.best_documented}** |")
        lines.append(f"| 🧪 Best Tested | **{lb.best_tested}** |")
        lines.append(f"| ⚡ Fastest PR Merge | **{lb.fastest_pr_merger}** |")
        lines.append(f"| 🦉 Biggest Night Owl | **{lb.biggest_night_owl}** |")
        lines.append("")

        # Member comparison table
        lines.append("## 📊 Member Comparison")
        lines.append("")
        lines.append("| Username | Commits/wk | Stars | Repos w/ README | Repos w/ Tests | Bad Msgs | Night Commits |")
        lines.append("|----------|-----------|-------|----------------|---------------|----------|--------------|")
        for m in report.members:
            lines.append(
                f"| **{m.username}** | {m.avg_commits_per_week:.1f} | {m.total_stars} "
                f"| {m.repos_with_readme} | {m.repos_with_tests} "
                f"| {m.bad_commit_messages} | {m.late_night_commits} |"
            )
        lines.append("")

        # Roast
        lines.append("## 🔥 The Team Roast")
        lines.append("")
        for ammo in report.team_roast_ammunition:
            lines.append(f"- {ammo}")
        if not report.team_roast_ammunition:
            lines.append("- This team is suspiciously well-balanced. We'll find something next time.")
        lines.append("")

        # Praise
        lines.append("## 💪 What The Team Does Well")
        lines.append("")
        for p in report.team_praise_ammunition:
            lines.append(f"- {p}")
        if not report.team_praise_ammunition:
            lines.append("- You're a team. That's a start.")
        lines.append("")

        # Language distribution
        lang_dist = report.team_stats.get("language_distribution", {})
        if lang_dist:
            lines.append("## 🗂️ Language Distribution")
            lines.append("")
            for lang, count in sorted(lang_dist.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- **{lang}**: {count} member(s)")
            lines.append("")

        return "\n".join(lines)
