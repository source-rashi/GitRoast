"""
GitRoast — GitHub Deep Scraper Tool
=====================================
Fetches comprehensive developer profile data from GitHub API including:
- All public repos with metadata (stars, forks, language, description)
- Commit history: frequency, patterns, message quality, late night activity
- Pull requests: open/closed/merged, description quality, time to merge
- Issues: open/closed ratio, time to close, labeling habits
- README quality scoring
- Language distribution across all repos
- Auto-generated roast ammunition from real data points
- Auto-generated praise ammunition for genuine strengths

Free tier: 5,000 API requests/hour with a GitHub Personal Access Token
No credit card required. Token at: github.com/settings/tokens
"""

import os
import asyncio
from datetime import datetime, timezone
from collections import Counter
from typing import Optional

from dotenv import load_dotenv
from github import Github, GithubException
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ReadmeQuality(BaseModel):
    has_readme: bool = False
    word_count: int = 0
    has_badges: bool = False
    has_screenshots: bool = False
    has_installation_section: bool = False
    has_usage_section: bool = False
    score: int = 0


class RepoProfile(BaseModel):
    name: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    is_fork: bool = False
    has_readme: bool = False
    has_tests: bool = False
    commit_count: int = 0
    open_issues: int = 0
    days_since_last_commit: int = 0
    readme_quality: ReadmeQuality = Field(default_factory=ReadmeQuality)


class CommitStats(BaseModel):
    total_commits: int = 0
    avg_commits_per_week: float = 0.0
    commits_with_bad_messages: int = 0
    commits_with_bad_messages_examples: list[str] = []
    longest_gap_days: int = 0
    late_night_commits: int = 0
    weekend_commits: int = 0
    most_active_hour: int = 0


class PRStats(BaseModel):
    total_prs: int = 0
    merged_prs: int = 0
    open_prs: int = 0
    avg_pr_description_length: int = 0
    prs_with_no_description: int = 0
    avg_days_to_merge: float = 0.0


class IssueStats(BaseModel):
    total_issues: int = 0
    open_issues: int = 0
    closed_issues: int = 0
    avg_days_to_close: float = 0.0
    issues_open_over_30_days: int = 0
    issues_with_no_labels: int = 0


class DeveloperProfile(BaseModel):
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    followers: int = 0
    following: int = 0
    public_repos: int = 0
    account_age_days: int = 0
    total_stars_received: int = 0
    top_languages: list[dict] = []
    repos: list[RepoProfile] = []
    commit_stats: CommitStats = Field(default_factory=CommitStats)
    pr_stats: PRStats = Field(default_factory=PRStats)
    issue_stats: IssueStats = Field(default_factory=IssueStats)
    roast_ammunition: list[str] = []
    praise_ammunition: list[str] = []
    scrape_timestamp: str = ""


# ---------------------------------------------------------------------------
# Bad commit messages list
# ---------------------------------------------------------------------------

BAD_MESSAGES = [
    "fix", "update", "wip", "test", "temp", "tmp",
    "changes", "stuff", "misc", "lol", "ok", "done", "final", "final2",
    "new", "old", "save", "commit", ".", "..", "x", "asd", "asdf",
    "qwerty", "work", "working", "refactor", "cleanup", "minor", "patch"
]


# ---------------------------------------------------------------------------
# GitHubScraper
# ---------------------------------------------------------------------------

class GitHubScraper:
    """Scrapes comprehensive developer data from the GitHub API."""

    def __init__(self):
        load_dotenv()
        self.token = os.getenv("GITHUB_TOKEN")
        self.github = Github(self.token) if self.token else Github()
        self.console = Console()

        if not self.token:
            logger.warning(
                "No GITHUB_TOKEN found in environment. "
                "You will be rate-limited to 60 requests/hour. "
                "Get a free token at: github.com/settings/tokens"
            )
        else:
            logger.info("GitHub client initialized with token (5,000 req/hr).")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def scrape_developer(self, username: str) -> DeveloperProfile:
        """Fetch and analyze a complete GitHub developer profile."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                # 1. Fetch profile
                task = progress.add_task("Fetching profile...", total=None)
                user = await asyncio.to_thread(self.github.get_user, username)

                profile = DeveloperProfile(
                    username=user.login,
                    name=user.name,
                    bio=user.bio,
                    location=user.location,
                    followers=user.followers,
                    following=user.following,
                    public_repos=user.public_repos,
                    account_age_days=(
                        datetime.now(timezone.utc) - user.created_at.replace(tzinfo=timezone.utc)
                    ).days,
                )

                # 2. Analyze repos
                progress.update(task, description="Analyzing repos...")
                repos_raw = list(await asyncio.to_thread(lambda: list(user.get_repos())))
                profile.total_stars_received = sum(r.stargazers_count for r in repos_raw)
                profile.top_languages = await asyncio.to_thread(self._get_top_languages, repos_raw)
                profile.repos = await asyncio.to_thread(self._analyze_repos, repos_raw)

                # 3. Scam commits
                progress.update(task, description="Scanning commits...")
                profile.commit_stats = await asyncio.to_thread(self._analyze_commits, repos_raw)

                # 4. Check PRs
                progress.update(task, description="Checking PRs...")
                profile.pr_stats = await asyncio.to_thread(self._analyze_prs, repos_raw)

                # 5. Check issues
                progress.update(task, description="Checking issues...")
                profile.issue_stats = await asyncio.to_thread(self._analyze_issues, repos_raw)

                # 6. Generate ammo
                progress.update(task, description="Generating roast ammo...")
                profile.roast_ammunition = self._generate_roast_ammunition(profile)
                profile.praise_ammunition = self._generate_praise_ammunition(profile)

                profile.scrape_timestamp = datetime.utcnow().isoformat()

            logger.success(f"Profile for '{username}' scraped successfully.")
            return profile

        except GithubException.UnknownObjectException:
            raise ValueError(
                f"GitHub user '{username}' not found. Check the username."
            )
        except GithubException as exc:
            if exc.status == 403:
                raise ValueError(
                    "GitHub API rate limit hit. Wait 1 hour or check your GITHUB_TOKEN in .env"
                )
            raise
        except Exception as exc:
            # Catch UnknownObjectException which may not be a subclass in all versions
            if "404" in str(exc) or "Not Found" in str(exc):
                raise ValueError(
                    f"GitHub user '{username}' not found. Check the username."
                )
            raise

    # ------------------------------------------------------------------
    # Language distribution
    # ------------------------------------------------------------------

    def _get_top_languages(self, repos: list) -> list[dict]:
        """Return top 5 languages by byte count as percentage dicts."""
        totals: dict[str, int] = {}
        for repo in repos:
            try:
                langs = repo.get_languages()
                for lang, count in langs.items():
                    totals[lang] = totals.get(lang, 0) + count
            except Exception:
                pass

        grand_total = sum(totals.values())
        if grand_total == 0:
            return []

        sorted_langs = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]
        result = []
        for lang, count in sorted_langs:
            result.append({
                "language": lang,
                "percentage": round((count / grand_total) * 100, 1),
            })
        return result

    # ------------------------------------------------------------------
    # Repo analysis
    # ------------------------------------------------------------------

    def _analyze_repos(self, repos) -> list[RepoProfile]:
        """Analyze up to 20 repos and return RepoProfile list."""
        original_repos = [r for r in repos if not r.fork]
        fork_repos = [r for r in repos if r.fork]

        # Include forks only if user has very few originals
        if len(original_repos) < 5:
            candidates = repos[:20]
        else:
            candidates = original_repos[:20]

        profiles = []
        for repo in candidates:
            try:
                # README
                readme_content = ""
                has_readme = False
                readme_quality = ReadmeQuality()
                try:
                    readme_file = repo.get_readme()
                    readme_content = readme_file.decoded_content.decode("utf-8", errors="replace")
                    has_readme = True
                    readme_quality = self._score_readme(readme_content)
                    readme_quality.has_readme = True
                except Exception:
                    pass

                # Test files
                has_tests = False
                try:
                    contents = repo.get_contents("")
                    stack = list(contents)
                    checked = 0
                    while stack and checked < 100:
                        item = stack.pop()
                        checked += 1
                        if "test" in item.path.lower():
                            has_tests = True
                            break
                        if item.type == "dir":
                            try:
                                stack.extend(repo.get_contents(item.path))
                            except Exception:
                                pass
                except Exception:
                    pass

                # Commit count
                commit_count = 0
                try:
                    commit_count = repo.get_commits().totalCount
                except Exception:
                    pass

                # Days since last commit
                days_since = 0
                if repo.pushed_at:
                    pushed_at = repo.pushed_at.replace(tzinfo=timezone.utc)
                    days_since = (datetime.now(timezone.utc) - pushed_at).days

                profiles.append(RepoProfile(
                    name=repo.name,
                    description=repo.description,
                    language=repo.language,
                    stars=repo.stargazers_count,
                    forks=repo.forks_count,
                    is_fork=repo.fork,
                    has_readme=has_readme,
                    has_tests=has_tests,
                    commit_count=commit_count,
                    open_issues=repo.open_issues_count,
                    days_since_last_commit=days_since,
                    readme_quality=readme_quality,
                ))
            except Exception as exc:
                logger.warning(f"Skipping repo '{repo.name}': {exc}")
                continue

        return profiles

    # ------------------------------------------------------------------
    # Commit analysis
    # ------------------------------------------------------------------

    def _analyze_commits(self, repos: list) -> CommitStats:
        """Analyze commit patterns from the last 90 days across up to 8 repos."""
        from datetime import timedelta

        since = datetime.utcnow() - timedelta(days=90)
        # Pick up to 8 repos sorted by stars
        candidates = sorted(repos, key=lambda r: r.stargazers_count, reverse=True)[:8]

        total_commits = 0
        bad_message_commits = 0
        bad_examples: list[str] = []
        late_night_commits = 0
        weekend_commits = 0
        all_hours: list[int] = []
        all_dates: list[datetime] = []

        for repo in candidates:
            try:
                commits = repo.get_commits(since=since)
                for commit in commits:
                    try:
                        total_commits += 1
                        msg = commit.commit.message.split("\n")[0].strip()
                        msg_lower = msg.lower()

                        # Bad message detection
                        if msg_lower in BAD_MESSAGES or len(msg_lower) <= 3:
                            bad_message_commits += 1
                            if len(bad_examples) < 5:
                                bad_examples.append(msg)

                        author_date = commit.commit.author.date
                        hour = author_date.hour
                        weekday = author_date.weekday()

                        if hour in [23, 0, 1, 2, 3, 4]:
                            late_night_commits += 1
                        if weekday in [5, 6]:
                            weekend_commits += 1

                        all_hours.append(hour)
                        all_dates.append(author_date)
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning(f"Could not fetch commits for '{repo.name}': {exc}")
                continue

        # Most active hour
        most_active_hour = 0
        if all_hours:
            most_active_hour = Counter(all_hours).most_common(1)[0][0]

        # Longest gap
        longest_gap_days = 0
        if len(all_dates) >= 2:
            sorted_dates = sorted(all_dates)
            gaps = [
                (sorted_dates[i + 1] - sorted_dates[i]).days
                for i in range(len(sorted_dates) - 1)
            ]
            longest_gap_days = max(gaps) if gaps else 0

        avg_commits_per_week = total_commits / 13  # 90 days ≈ 13 weeks

        return CommitStats(
            total_commits=total_commits,
            avg_commits_per_week=round(avg_commits_per_week, 2),
            commits_with_bad_messages=bad_message_commits,
            commits_with_bad_messages_examples=bad_examples,
            longest_gap_days=longest_gap_days,
            late_night_commits=late_night_commits,
            weekend_commits=weekend_commits,
            most_active_hour=most_active_hour,
        )

    # ------------------------------------------------------------------
    # PR analysis
    # ------------------------------------------------------------------

    def _analyze_prs(self, repos: list) -> PRStats:
        """Analyze pull requests from the top 5 starred repos."""
        candidates = sorted(repos, key=lambda r: r.stargazers_count, reverse=True)[:5]

        total_prs = 0
        merged_prs = 0
        open_prs = 0
        desc_lengths: list[int] = []
        prs_no_desc = 0
        days_to_merge: list[float] = []

        for repo in candidates:
            try:
                prs = repo.get_pulls(state="all")
                for pr in prs:
                    try:
                        total_prs += 1
                        body = pr.body or ""
                        desc_lengths.append(len(body.strip()))

                        if body is None or len(body.strip()) < 20:
                            prs_no_desc += 1

                        if pr.merged_at:
                            merged_prs += 1
                            gap = (pr.merged_at - pr.created_at).days
                            days_to_merge.append(float(gap))
                        elif pr.state == "open":
                            open_prs += 1
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning(f"Could not fetch PRs for '{repo.name}': {exc}")
                continue

        avg_desc_len = int(sum(desc_lengths) / len(desc_lengths)) if desc_lengths else 0
        avg_merge_days = (
            round(sum(days_to_merge) / len(days_to_merge), 1) if days_to_merge else 0.0
        )

        return PRStats(
            total_prs=total_prs,
            merged_prs=merged_prs,
            open_prs=open_prs,
            avg_pr_description_length=avg_desc_len,
            prs_with_no_description=prs_no_desc,
            avg_days_to_merge=avg_merge_days,
        )

    # ------------------------------------------------------------------
    # Issue analysis
    # ------------------------------------------------------------------

    def _analyze_issues(self, repos: list) -> IssueStats:
        """Analyze issues from up to 5 repos."""
        candidates = repos[:5]
        now = datetime.utcnow()

        total_issues = 0
        open_issues = 0
        closed_issues = 0
        close_times: list[float] = []
        issues_over_30 = 0
        issues_no_labels = 0

        for repo in candidates:
            try:
                issues = repo.get_issues(state="all")
                for issue in issues:
                    try:
                        # Filter out pull requests
                        if hasattr(issue, "pull_request") and issue.pull_request:
                            continue

                        total_issues += 1

                        if len(issue.labels) == 0:
                            issues_no_labels += 1

                        if issue.state == "open":
                            open_issues += 1
                            created = issue.created_at.replace(tzinfo=None)
                            if (now - created).days > 30:
                                issues_over_30 += 1
                        elif issue.state == "closed":
                            closed_issues += 1
                            if issue.closed_at:
                                created = issue.created_at.replace(tzinfo=None)
                                closed = issue.closed_at.replace(tzinfo=None)
                                close_times.append((closed - created).days)
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning(f"Could not fetch issues for '{repo.name}': {exc}")
                continue

        avg_close = (
            round(sum(close_times) / len(close_times), 1) if close_times else 0.0
        )

        return IssueStats(
            total_issues=total_issues,
            open_issues=open_issues,
            closed_issues=closed_issues,
            avg_days_to_close=avg_close,
            issues_open_over_30_days=issues_over_30,
            issues_with_no_labels=issues_no_labels,
        )

    # ------------------------------------------------------------------
    # README scoring
    # ------------------------------------------------------------------

    def _score_readme(self, readme_content: str) -> ReadmeQuality:
        """Score a README 0–10 based on completeness."""
        word_count = len(readme_content.split())
        has_badges = "[![" in readme_content
        has_screenshots = (
            ".png" in readme_content.lower() or ".gif" in readme_content.lower()
        )
        has_installation = "install" in readme_content.lower()
        has_usage = (
            "usage" in readme_content.lower() or "how to" in readme_content.lower()
        )

        score = 0
        if word_count > 100:
            score += 2
        if word_count > 300:
            score += 2
        if has_badges:
            score += 1
        if has_screenshots:
            score += 2
        if has_installation:
            score += 1
        if has_usage:
            score += 1
        if word_count > 600:
            score += 1
        score = min(score, 10)

        return ReadmeQuality(
            has_readme=True,
            word_count=word_count,
            has_badges=has_badges,
            has_screenshots=has_screenshots,
            has_installation_section=has_installation,
            has_usage_section=has_usage,
            score=score,
        )

    # ------------------------------------------------------------------
    # Roast ammunition
    # ------------------------------------------------------------------

    def _generate_roast_ammunition(self, profile: DeveloperProfile) -> list[str]:
        """Generate roast lines grounded in real profile data."""
        ammo: list[str] = []
        cs = profile.commit_stats
        ps = profile.pr_stats
        is_ = profile.issue_stats

        if cs.commits_with_bad_messages >= 5:
            ammo.append(
                f"{cs.commits_with_bad_messages} commits with messages like 'fix', 'update', or 'wip'."
                " Fix WHAT exactly? Describe your crime."
            )

        if cs.late_night_commits >= 10:
            ammo.append(
                f"{cs.late_night_commits} commits pushed between 11pm and 4am."
                " Your sleep schedule is a war crime."
            )

        if cs.late_night_commits >= 25:
            ammo.append(
                f"At this point your laptop screen IS your nightlight."
                f" {cs.late_night_commits} 3am commits detected."
            )

        if is_.issues_open_over_30_days >= 3:
            ammo.append(
                f"{is_.issues_open_over_30_days} issues have been open for over 30 days."
                " That's not a backlog — that's a museum exhibit."
            )

        if ps.prs_with_no_description >= 3:
            ammo.append(
                f"{ps.prs_with_no_description} pull requests with no description."
                " Your teammates are detectives because of you."
            )

        repos_with_no_tests = sum(1 for r in profile.repos if not r.has_tests)
        if repos_with_no_tests >= 3:
            ammo.append(
                f"{repos_with_no_tests} repos with zero test files. You don't test, you pray."
            )

        repos_with_no_readme = sum(1 for r in profile.repos if not r.has_readme)
        if repos_with_no_readme >= 3:
            ammo.append(
                f"{repos_with_no_readme} repos with no README."
                " Your projects are mysteries even to you."
            )

        if ps.avg_pr_description_length < 30 and ps.total_prs > 3:
            ammo.append(
                f"Average PR description is {ps.avg_pr_description_length} characters."
                " That's shorter than this sentence."
            )

        if cs.longest_gap_days >= 14:
            ammo.append(
                f"You disappeared for {cs.longest_gap_days} days between commits."
                " We were worried. We weren't, actually."
            )

        if cs.longest_gap_days >= 60:
            ammo.append(
                f"{cs.longest_gap_days} days between commits."
                " That's not a gap, that's a sabbatical you forgot to announce."
            )

        total_bad_repos = sum(1 for r in profile.repos if r.days_since_last_commit > 180)
        if total_bad_repos >= 3:
            ammo.append(
                f"{total_bad_repos} repos haven't been touched in over 6 months."
                " A graveyard with a GitHub URL."
            )

        if profile.account_age_days > 730 and profile.total_stars_received == 0:
            ammo.append(
                f"Account is {profile.account_age_days // 365} years old."
                " Zero stars received. The internet has spoken."
            )

        if profile.public_repos > 20 and profile.total_stars_received < 5:
            ammo.append(
                f"{profile.public_repos} public repos, {profile.total_stars_received} total stars."
                " Quantity is not a strategy."
            )

        if is_.issues_with_no_labels >= 5:
            ammo.append(
                f"{is_.issues_with_no_labels} issues with no labels."
                " Chaos filing system detected."
            )

        if profile.followers < 5 and profile.account_age_days > 365:
            ammo.append(
                f"{profile.followers} followers after {profile.account_age_days // 365} year(s)."
                " Your personal brand is under construction. Forever."
            )

        return ammo

    # ------------------------------------------------------------------
    # Praise ammunition
    # ------------------------------------------------------------------

    def _generate_praise_ammunition(self, profile: DeveloperProfile) -> list[str]:
        """Generate genuine praise lines from real profile data."""
        praise: list[str] = []
        cs = profile.commit_stats
        ps = profile.pr_stats
        is_ = profile.issue_stats

        if cs.avg_commits_per_week >= 5:
            praise.append(
                f"Averaging {cs.avg_commits_per_week:.1f} commits per week."
                " Consistency is rare — you have it."
            )

        if cs.commits_with_bad_messages == 0 and cs.total_commits > 10:
            praise.append(
                "Zero lazy commit messages found. Clean commit history is a love language."
            )

        repos_with_readme = sum(1 for r in profile.repos if r.has_readme)
        if repos_with_readme >= 5:
            praise.append(
                f"{repos_with_readme} repos with READMEs."
                " You actually document things. A dying art."
            )

        if profile.total_stars_received >= 50:
            praise.append(
                f"{profile.total_stars_received} total stars received."
                " People actually like your work. Don't ruin it."
            )

        if profile.total_stars_received >= 200:
            praise.append(
                f"{profile.total_stars_received} stars."
                " You've built something people care about. That's genuinely rare."
            )

        repos_with_tests = sum(1 for r in profile.repos if r.has_tests)
        if repos_with_tests >= 3:
            praise.append(
                f"{repos_with_tests} repos have test files."
                " You test your code. You are built different."
            )

        if ps.avg_days_to_merge < 3 and ps.total_prs >= 5:
            praise.append(
                f"Average {ps.avg_days_to_merge:.1f} days to merge PRs."
                " You don't let things rot in review. Respect."
            )

        if is_.avg_days_to_close < 7 and is_.closed_issues >= 5:
            praise.append(
                "Closing issues in under a week on average. You ship and you ship clean."
            )

        top_lang = profile.top_languages[0] if profile.top_languages else None
        if top_lang and top_lang["percentage"] > 60:
            praise.append(
                f"Deep focus in {top_lang['language']}"
                f" ({top_lang['percentage']:.0f}% of your code)."
                " Specialization is a superpower."
            )

        return praise


# ---------------------------------------------------------------------------
# CLI test entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    scraper = GitHubScraper()
    profile = asyncio.run(scraper.scrape_developer("torvalds"))
    print(profile.model_dump_json(indent=2))
