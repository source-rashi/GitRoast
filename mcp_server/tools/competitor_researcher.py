"""
GitRoast — Competitor Researcher
====================================
Searches GitHub for similar projects and synthesizes competitor intelligence.

Strategy (100% free):
1. GitHub Search API — search repos by keywords extracted from the idea
2. Analyze top results: stars, last commit, README quality, open issues
3. Find gaps: what do competitors lack? where do they fall short?
4. Groq synthesizes everything into a differentiation report

Why GitHub search instead of web search:
- Free with PAT (no Tavily, no Brave needed)
- Developers ship to GitHub — it's the most relevant signal
- Real data: stars, forks, activity, issues tell the story
- 30 searches/minute on free tier — more than enough

Output: "3 people built this. None of them have X. That's your wedge."
"""

import asyncio
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from github import Github, RateLimitExceededException
from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.status import Status

# ---------------------------------------------------------------------------
# System prompt for Groq synthesis
# ---------------------------------------------------------------------------

COMPETITOR_SYSTEM_PROMPT = """You are GitRoast's Competitor Intelligence Engine.

You have real data from GitHub search about existing projects similar to the user's idea.
Your job: synthesize this into sharp, actionable competitor intelligence.

Respond in this EXACT format:

## 🕵️ Competitor Intelligence Report

### The Landscape
[2-3 sentences describing the competitive landscape based on the data]

### Top Competitors
[For each top competitor (max 5): one line with name, stars, and their biggest weakness]

### The Gap In The Market
[What specifically is missing from ALL competitors? Be precise.]

### Your Wedge
[THE single most important differentiator to focus on. One sentence. Make it sharp.]
Example: "Build the only competitor researcher tool with a personality engine — competitors are dry and boring."

### Strategic Recommendation: [Build it / Niche down / Find a gap / Reconsider]
[2 sentences explaining the recommendation]

### 3 Things To Do This Week
1. [Specific action]
2. [Specific action]
3. [Specific action]

Rules:
- Every claim must reference actual data from the competitor list
- "Your Wedge" must be a single sentence that could fit on a pitch deck
- Be direct — no hedging
- If there are no competitors: focus on first-mover risks and validation strategy"""

# ---------------------------------------------------------------------------
# Stop words for keyword extraction
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "a", "an", "the", "is", "are", "for", "with", "that", "this",
    "and", "or", "of", "to", "in", "it", "my", "i", "we", "you",
    "build", "make", "create", "app", "tool", "platform", "system",
    "using", "use", "like", "can", "will", "want", "need", "based",
    "which", "where", "when", "what", "how", "who", "why", "but",
    "from", "into", "on", "at", "by", "as", "be", "has", "have",
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CompetitorRepo(BaseModel):
    name: str
    full_name: str
    url: str
    description: Optional[str]
    stars: int
    forks: int
    language: Optional[str]
    last_updated_days_ago: int
    open_issues: int
    has_readme: bool
    readme_word_count: int
    topics: list[str]
    is_actively_maintained: bool
    apparent_weaknesses: list[str]


class DifferentiationAngle(BaseModel):
    angle: str
    evidence: str
    strength: str  # "strong", "medium", "weak"


class CompetitorReport(BaseModel):
    idea: str
    search_keywords: list[str]
    competitors_found: list[CompetitorRepo]
    total_searched: int
    market_saturation: str  # "empty", "light", "moderate", "saturated"
    differentiation_angles: list[DifferentiationAngle]
    synthesis: str
    your_wedge: str
    recommendation: str
    timestamp: str


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------


class CompetitorResearcher:
    """Competitor intelligence engine powered by GitHub Search API + Groq."""

    def __init__(self, groq_client, github_token: str):
        self.groq_client = groq_client
        self.github = Github(github_token) if github_token else Github()
        self.console = Console(stderr=True)
        logger.info("CompetitorResearcher initialized")

    async def research(self, idea: str, personality: str = "yc_founder") -> CompetitorReport:
        """Main entry point — research competitors for an idea."""
        self.console.print(
            "\n[bold orange1]🕵️ GitRoast is searching GitHub for competitors...[/bold orange1]\n"
            "[dim]Using GitHub Search API (free, real data)[/dim]"
        )

        keywords = self._extract_keywords(idea)
        logger.info(f"Extracted keywords: {keywords}")
        self.console.print(f"[dim]Search keywords: {', '.join(keywords)}[/dim]")

        competitors = self._search_github_repos(keywords)
        logger.info(f"Found {len(competitors)} competitors")

        angles = self._find_differentiation_angles(idea, competitors)

        synthesis, your_wedge, recommendation = await self._synthesize_with_groq(
            idea, competitors, angles
        )

        count = len(competitors)
        if count == 0:
            market_saturation = "empty"
        elif count <= 5:
            market_saturation = "light"
        elif count <= 15:
            market_saturation = "moderate"
        else:
            market_saturation = "saturated"

        return CompetitorReport(
            idea=idea,
            search_keywords=keywords,
            competitors_found=competitors,
            total_searched=count,
            market_saturation=market_saturation,
            differentiation_angles=angles,
            synthesis=synthesis,
            your_wedge=your_wedge,
            recommendation=recommendation,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # -----------------------------------------------------------------------
    # Keyword extraction
    # -----------------------------------------------------------------------

    def _extract_keywords(self, idea: str) -> list[str]:
        """Pull meaningful keywords from the idea text."""
        words = idea.lower().replace("-", " ").replace("_", " ").split()
        meaningful = [
            w.strip(".,!?;:\"'()")
            for w in words
            if w.strip(".,!?;:\"'()") not in STOP_WORDS and len(w) > 2
        ]

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for w in meaningful:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        # Add compound terms
        idea_lower = idea.lower()
        compound_pairs = [
            ("code review", "code-review"),
            ("code quality", "code-quality"),
            ("machine learning", "machine-learning"),
            ("vs code", "vscode"),
            ("open source", "open-source"),
            ("command line", "cli"),
            ("developer tool", "devtool"),
            ("github action", "github-action"),
            ("pull request", "pull-request"),
        ]
        for phrase, compound in compound_pairs:
            if phrase in idea_lower and compound not in unique:
                unique.append(compound)

        keywords = unique[:5]
        return keywords

    # -----------------------------------------------------------------------
    # GitHub search
    # -----------------------------------------------------------------------

    def _search_github_repos(self, keywords: list[str]) -> list[CompetitorRepo]:
        """Search GitHub repos and return deduplicated, ranked results."""
        if not keywords:
            return []

        queries: list[str] = []
        queries.append(" ".join(keywords[:3]))
        if len(keywords) >= 2:
            queries.append(f"{keywords[0]} {keywords[1]}")
        queries.append(f"{keywords[0]} tool")

        seen_names: set[str] = set()
        raw_repos = []

        for query in queries:
            try:
                logger.info(f"GitHub search: '{query}'")
                results = self._run_search_with_retry(query)
                count = 0
                for repo in results:
                    if count >= 5:
                        break
                    if repo.full_name not in seen_names:
                        seen_names.add(repo.full_name)
                        raw_repos.append(repo)
                        count += 1
            except Exception as exc:
                logger.warning(f"Search query '{query}' failed: {exc}")
                continue

        # Analyze each repo
        competitors = []
        for repo in raw_repos:
            try:
                competitor = self._analyze_repo(repo)
                competitors.append(competitor)
            except Exception as exc:
                logger.warning(f"Failed to analyze repo {repo.full_name}: {exc}")
                continue

        # Sort by stars descending, return top 10
        competitors.sort(key=lambda c: c.stars, reverse=True)
        return competitors[:10]

    def _run_search_with_retry(self, query: str):
        """Run a GitHub search with one retry on rate limit."""
        try:
            return self.github.search_repositories(query, sort="stars", order="desc")
        except RateLimitExceededException:
            logger.warning("GitHub rate limit exceeded — waiting 60s and retrying")
            self.console.print("[yellow]⚠️ GitHub rate limit hit — waiting 60s...[/yellow]")
            time.sleep(60)
            return self.github.search_repositories(query, sort="stars", order="desc")

    # -----------------------------------------------------------------------
    # Repo analysis
    # -----------------------------------------------------------------------

    def _analyze_repo(self, repo) -> CompetitorRepo:
        """Build a CompetitorRepo from a PyGitHub repo object."""
        now = datetime.now(timezone.utc)
        updated_at = repo.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        last_updated_days_ago = (now - updated_at).days
        is_actively_maintained = last_updated_days_ago < 90

        # Try to get README
        readme_content = ""
        readme_word_count = 0
        has_readme = False
        try:
            readme = repo.get_readme()
            readme_content = readme.decoded_content.decode("utf-8", errors="ignore")
            readme_word_count = len(readme_content.split())
            has_readme = True
        except Exception:
            pass

        # Get topics
        topics: list[str] = []
        try:
            topics = repo.get_topics()
        except Exception:
            pass

        weaknesses = self._detect_weaknesses(
            repo, readme_content, last_updated_days_ago, readme_word_count, topics
        )

        return CompetitorRepo(
            name=repo.name,
            full_name=repo.full_name,
            url=repo.html_url,
            description=repo.description,
            stars=repo.stargazers_count,
            forks=repo.forks_count,
            language=repo.language,
            last_updated_days_ago=last_updated_days_ago,
            open_issues=repo.open_issues_count,
            has_readme=has_readme,
            readme_word_count=readme_word_count,
            topics=topics,
            is_actively_maintained=is_actively_maintained,
            apparent_weaknesses=weaknesses,
        )

    def _detect_weaknesses(
        self,
        repo,
        readme_content: str,
        last_updated_days_ago: int,
        readme_word_count: int,
        topics: list[str],
    ) -> list[str]:
        """Auto-detect gaps and weaknesses from repo data."""
        weaknesses: list[str] = []

        if last_updated_days_ago > 365:
            weaknesses.append(
                f"Abandoned — last updated {last_updated_days_ago} days ago"
            )
        elif last_updated_days_ago > 180:
            weaknesses.append("Stale — over 6 months since last update")

        if readme_word_count == 0:
            weaknesses.append("No README — users have to guess how to use it")
        elif readme_word_count < 100:
            weaknesses.append("Poor documentation — README under 100 words")

        if repo.open_issues_count > 100:
            weaknesses.append("Overwhelmed maintainer — 100+ open issues")
        elif repo.open_issues_count > 50:
            weaknesses.append(
                f"Issue backlog — {repo.open_issues_count} open issues unaddressed"
            )

        if repo.forks_count > repo.stargazers_count * 2 and repo.stargazers_count > 0:
            weaknesses.append(
                "More forks than stars — people modify it but don't endorse it"
            )

        if readme_content and "install" not in readme_content.lower():
            weaknesses.append("No installation instructions in README")

        if repo.stargazers_count < 10 and last_updated_days_ago < 30:
            weaknesses.append(
                "New and unproven — low adoption despite recent activity"
            )

        if not topics:
            weaknesses.append("No topics/tags — poor discoverability")

        return weaknesses

    # -----------------------------------------------------------------------
    # Differentiation angles
    # -----------------------------------------------------------------------

    def _find_differentiation_angles(
        self, idea: str, competitors: list[CompetitorRepo]
    ) -> list[DifferentiationAngle]:
        """Auto-detect differentiation opportunities from competitor data."""
        angles: list[DifferentiationAngle] = []

        # No competitors at all
        if len(competitors) == 0:
            angles.append(
                DifferentiationAngle(
                    angle="No direct competitors found on GitHub — first mover opportunity",
                    evidence="GitHub search returned 0 results for these keywords",
                    strength="strong",
                )
            )
            return angles

        # Maintenance gap
        active = [c for c in competitors if c.is_actively_maintained]
        if len(competitors) > 0 and len(active) < len(competitors) / 2:
            angles.append(
                DifferentiationAngle(
                    angle="Most competitors are abandoned — the field needs a maintained solution",
                    evidence=f"{len(competitors) - len(active)}/{len(competitors)} competitors inactive",
                    strength="strong",
                )
            )

        # Documentation gap
        poor_docs = [c for c in competitors if c.readme_word_count < 200]
        if len(poor_docs) >= 2:
            angles.append(
                DifferentiationAngle(
                    angle="Competitors have terrible documentation — win with great docs and onboarding",
                    evidence=f"{len(poor_docs)} competitors have under 200 word READMEs",
                    strength="medium",
                )
            )

        # Issue backlog gap
        overwhelmed = [c for c in competitors if c.open_issues > 50]
        if overwhelmed:
            angles.append(
                DifferentiationAngle(
                    angle="Competitors are overwhelmed with support — win with responsiveness",
                    evidence=f"{overwhelmed[0].full_name} has {overwhelmed[0].open_issues} open issues",
                    strength="strong",
                )
            )

        # Language monopoly
        languages = [c.language for c in competitors if c.language]
        if languages:
            lang_counts = Counter(languages)
            dominant_lang = lang_counts.most_common(1)[0][0]
            if len(set(languages)) == 1:
                angles.append(
                    DifferentiationAngle(
                        angle=f"All competitors are in {dominant_lang} — opportunity in other languages/platforms",
                        evidence=f"All {len(competitors)} competitors use {dominant_lang}",
                        strength="medium",
                    )
                )

        # Star gap — field is there but no clear leader
        max_stars = max((c.stars for c in competitors), default=0)
        if 0 < max_stars < 500 and len(competitors) >= 3:
            angles.append(
                DifferentiationAngle(
                    angle="No dominant player — the market leader hasn't been built yet",
                    evidence=f"Top competitor has only {max_stars} stars across {len(competitors)} projects",
                    strength="strong",
                )
            )

        return angles

    # -----------------------------------------------------------------------
    # Groq synthesis
    # -----------------------------------------------------------------------

    async def _synthesize_with_groq(
        self,
        idea: str,
        competitors: list[CompetitorRepo],
        angles: list[DifferentiationAngle],
    ) -> tuple[str, str, str]:
        """Use Groq to synthesize competitor data into strategic intelligence."""

        # Build competitor summary for the prompt
        comp_lines: list[str] = []
        for i, c in enumerate(competitors[:8], 1):
            top_weakness = c.apparent_weaknesses[0] if c.apparent_weaknesses else "None detected"
            comp_lines.append(
                f"{i}. {c.full_name} — ⭐{c.stars} stars, "
                f"last updated {c.last_updated_days_ago}d ago, "
                f"{'active' if c.is_actively_maintained else 'INACTIVE'}, "
                f"README: {c.readme_word_count} words, "
                f"open issues: {c.open_issues}\n"
                f"   Top weakness: {top_weakness}"
            )

        comp_text = "\n".join(comp_lines) if comp_lines else "No competitors found."

        angles_text = "\n".join(
            f"- [{a.strength.upper()}] {a.angle} (evidence: {a.evidence})"
            for a in angles
        ) or "None auto-detected."

        user_prompt = f"""IDEA: {idea}

COMPETITORS FOUND ({len(competitors)} total):
{comp_text}

AUTO-DETECTED DIFFERENTIATION ANGLES:
{angles_text}

Now synthesize this into a sharp competitor intelligence report following the format exactly."""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": COMPETITOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=900,
                temperature=0.7,
            )
            synthesis = response.choices[0].message.content
        except Exception as exc:
            logger.warning(f"Groq synthesis failed: {exc}")
            synthesis = self._fallback_synthesis(idea, competitors, angles)

        # Extract "Your Wedge" section
        your_wedge = self._extract_section(synthesis, "Your Wedge")
        if not your_wedge:
            your_wedge = angles[0].angle if angles else "Differentiate through better UX and documentation."

        # Extract recommendation
        recommendation = "Build it"
        for keyword in ["Niche down", "Find a gap", "Reconsider", "Build it"]:
            if keyword.lower() in synthesis.lower():
                recommendation = keyword
                break
        # Also catch "Strategic Recommendation:" line
        for line in synthesis.splitlines():
            if "Strategic Recommendation:" in line:
                rest = line.split("Strategic Recommendation:")[-1].strip()
                # Clean markdown bold etc
                rest = rest.strip("*[] ")
                if rest:
                    recommendation = rest
                break

        return synthesis, your_wedge, recommendation

    def _extract_section(self, text: str, section_title: str) -> str:
        """Extract the content of a markdown section by title."""
        lines = text.splitlines()
        capturing = False
        result_lines: list[str] = []
        for line in lines:
            if section_title.lower() in line.lower() and line.startswith("#"):
                capturing = True
                continue
            if capturing:
                if line.startswith("#"):
                    break
                result_lines.append(line)
        return "\n".join(result_lines).strip()

    def _fallback_synthesis(
        self,
        idea: str,
        competitors: list[CompetitorRepo],
        angles: list[DifferentiationAngle],
    ) -> str:
        """Generate a basic synthesis when Groq is unavailable."""
        lines = [
            "## 🕵️ Competitor Intelligence Report",
            "",
            "### The Landscape",
            f"Found {len(competitors)} GitHub projects similar to your idea.",
            "",
            "### Top Competitors",
        ]
        for c in competitors[:5]:
            weakness = c.apparent_weaknesses[0] if c.apparent_weaknesses else "No major issues"
            lines.append(f"- **{c.full_name}** — ⭐{c.stars} — {weakness}")
        lines += [
            "",
            "### Your Wedge",
            angles[0].angle if angles else "No clear wedge auto-detected — analyze manually.",
            "",
            "### Strategic Recommendation: Build it",
            "Proceed with validation. Check angles above for differentiation.",
        ]
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Display formatting
    # -----------------------------------------------------------------------

    def format_report_for_display(self, report: CompetitorReport) -> str:
        """Format the CompetitorReport as beautiful markdown."""
        saturation_emoji = {
            "empty": "🟢",
            "light": "🟡",
            "moderate": "🟠",
            "saturated": "🔴",
        }.get(report.market_saturation, "⚪")

        lines: list[str] = [
            f"# 🕵️ GitRoast Competitor Intelligence",
            f"",
            f"**Idea:** {report.idea}",
            f"**Market Saturation:** {saturation_emoji} {report.market_saturation.title()} "
            f"({report.total_searched} competitors found)",
            f"**Keywords Searched:** `{'`, `'.join(report.search_keywords)}`",
            f"",
        ]

        if report.competitors_found:
            lines += [
                "## 📊 Competitor Overview",
                "",
                "| Repo | ⭐ Stars | Active? | README | Open Issues | Top Weakness |",
                "|------|---------|---------|--------|------------|--------------|",
            ]
            for c in report.competitors_found:
                active_icon = "✅" if c.is_actively_maintained else "🔴"
                readme_str = f"{c.readme_word_count}w" if c.has_readme else "❌"
                top_weakness = (
                    c.apparent_weaknesses[0][:50] + "…"
                    if c.apparent_weaknesses and len(c.apparent_weaknesses[0]) > 50
                    else (c.apparent_weaknesses[0] if c.apparent_weaknesses else "—")
                )
                lines.append(
                    f"| [{c.full_name}]({c.url}) | {c.stars:,} | {active_icon} | {readme_str} "
                    f"| {c.open_issues} | {top_weakness} |"
                )
            lines.append("")

        if report.differentiation_angles:
            lines += ["## 🎯 Differentiation Angles", ""]
            for angle in report.differentiation_angles:
                strength_icon = {"strong": "🔥", "medium": "⚡", "weak": "💡"}.get(
                    angle.strength, "•"
                )
                lines.append(f"{strength_icon} **{angle.angle}**")
                lines.append(f"   *Evidence: {angle.evidence}*")
                lines.append("")

        lines += ["---", "", report.synthesis, "", "---", ""]

        # Wedge highlight box
        lines += [
            "## 🏹 Your Wedge",
            "",
            f"> **{report.your_wedge}**",
            "",
            f"**Recommendation:** {report.recommendation}",
            "",
            f"*Analysis run at {report.timestamp[:19].replace('T', ' ')} UTC*",
        ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import asyncio
    from groq import Groq
    from dotenv import load_dotenv

    load_dotenv()

    groq_key = os.getenv("GROQ_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN", "")

    if not groq_key:
        print("❌ GROQ_API_KEY not set. Add it to your .env file.")
        exit(1)

    client = Groq(api_key=groq_key)
    researcher = CompetitorResearcher(client, github_token)
    report = asyncio.run(
        researcher.research("VS Code extension that roasts your GitHub profile using AI")
    )
    print(researcher.format_report_for_display(report))
