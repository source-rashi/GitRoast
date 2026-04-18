"""
GitRoast — Utility Functions
==============================
Shared helpers used across the MCP server.
"""

from mcp_server.tools.github_scraper import DeveloperProfile


def format_profile_for_prompt(profile: DeveloperProfile) -> str:
    """Return a clean, structured string summary of the profile for LLM prompts."""
    lines = [
        f"# GitHub Profile: {profile.username}",
        "",
        "## Basic Info",
        f"- Name: {profile.name or 'N/A'}",
        f"- Bio: {profile.bio or 'N/A'}",
        f"- Location: {profile.location or 'N/A'}",
        f"- Followers: {profile.followers}",
        f"- Following: {profile.following}",
        f"- Public repos: {profile.public_repos}",
        f"- Account age: {days_to_human(profile.account_age_days)}",
        f"- Total stars received: {profile.total_stars_received}",
        "",
        "## Top Languages",
        format_language_list(profile.top_languages),
        "",
        "## Commit Stats",
        f"- Total commits (last 90 days): {profile.commit_stats.total_commits}",
        f"- Avg commits/week: {profile.commit_stats.avg_commits_per_week:.1f}",
        f"- Bad commit messages: {profile.commit_stats.commits_with_bad_messages}",
        f"- Late-night commits: {profile.commit_stats.late_night_commits}",
        f"- Weekend commits: {profile.commit_stats.weekend_commits}",
        f"- Longest gap: {profile.commit_stats.longest_gap_days} days",
        f"- Most active hour: {profile.commit_stats.most_active_hour}:00",
        "",
        "## PR Stats",
        f"- Total PRs: {profile.pr_stats.total_prs}",
        f"- Merged: {profile.pr_stats.merged_prs}",
        f"- Open: {profile.pr_stats.open_prs}",
        f"- Avg description length: {profile.pr_stats.avg_pr_description_length} chars",
        f"- PRs with no description: {profile.pr_stats.prs_with_no_description}",
        f"- Avg days to merge: {profile.pr_stats.avg_days_to_merge}",
        "",
        "## Issue Stats",
        f"- Total issues: {profile.issue_stats.total_issues}",
        f"- Open: {profile.issue_stats.open_issues}",
        f"- Closed: {profile.issue_stats.closed_issues}",
        f"- Avg days to close: {profile.issue_stats.avg_days_to_close}",
        f"- Issues open >30 days: {profile.issue_stats.issues_open_over_30_days}",
        f"- Issues with no labels: {profile.issue_stats.issues_with_no_labels}",
        "",
        "## Roast Ammunition",
    ]
    for i, line in enumerate(profile.roast_ammunition, 1):
        lines.append(f"{i}. {line}")

    lines.append("")
    lines.append("## Praise Ammunition")
    for i, line in enumerate(profile.praise_ammunition, 1):
        lines.append(f"{i}. {line}")

    return "\n".join(lines)


def truncate_text(text: str, max_chars: int = 500) -> str:
    """Truncate text to max_chars and append '...' if needed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def days_to_human(days: int) -> str:
    """Convert a day count to a human-readable string."""
    if days < 14:
        return f"{days} day{'s' if days != 1 else ''}"
    if days < 60:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''}"
    if days < 365:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''}"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def format_language_list(languages: list[dict]) -> str:
    """Format a top_languages list into a readable string."""
    if not languages:
        return "No language data available."
    parts = [f"{lang['language']} ({lang['percentage']:.0f}%)" for lang in languages]
    return ", ".join(parts)
