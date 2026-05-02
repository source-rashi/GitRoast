"""
GitRoast — MCP Server Entry Point
=====================================
Exposes 11 MCP tools to any compatible agent (Claude Desktop, Cursor, etc).
Communicates via stdio — the standard MCP protocol.

Tools:
  1. analyze_developer      — Full GitHub profile roast (Phase 1, LIVE)
  2. analyze_code_quality   — Real static analysis: pylint, radon, AST (Phase 2, LIVE)
  3. stress_test_idea        — Multi-agent idea debate (Phase 3, LIVE)
  4. scaffold_project        — Project scaffolding (Phase 3, LIVE)
  5. research_competitors    — Competitor intelligence (Phase 4, LIVE)
  6. set_personality         — Switch roast persona
  7. ask_followup            — Follow-up questions without re-fetch
  8. clear_session           — Clear cache and conversation history
  9. roast_team              — Multi-profile team comparison + group roast (Phase 5, LIVE)
 10. watch_workspace         — Real-time file watcher with micro-roasts (Phase 5, LIVE)
 11. send_to_webhook         — Send results to Slack/Discord/webhook (Phase 5, LIVE)

LLM: Groq (free, no credit card, llama-3.3-70b-versatile)
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from groq import Groq
from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from rich.console import Console

from mcp_server.tools.github_scraper import GitHubScraper
from mcp_server.tools.code_analyzer import CodeAnalyzer
from mcp_server.tools.idea_debater import IdeaDebater, DebateResult
from mcp_server.tools.scaffolder import ProjectScaffolder, ScaffoldResult
from mcp_server.tools.competitor_researcher import CompetitorResearcher, CompetitorReport
from mcp_server.personality.engine import PersonalityEngine
from mcp_server.orchestrator import GitRoastOrchestrator
from mcp_server.tools.team_roaster import TeamRoaster, TeamReport
from mcp_server.tools.file_watcher import FileWatcher
from mcp_server.tools.webhook_notifier import WebhookNotifier

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

ROAST_SYSTEM_PROMPT = """You are GitRoast — the most brutally honest, data-driven developer roaster on the internet.

You have been given REAL DATA scraped from a developer's GitHub profile. Every fact you use MUST come from this data. Never make anything up.

Your job:
1. Roast them using ONLY real facts from the profile data provided
2. Be genuinely funny — think comedy special, not cyberbullying  
3. Find their actual strengths and acknowledge them with equal energy
4. Give 3-5 specific, actionable improvement tips at the end

Format your response in this EXACT structure:

## 🔍 Profile Overview
[2-3 sentences summarizing who this developer is based on their data]

## 🔥 The Roast
[5-8 roast points, each grounded in a specific data fact from the profile]
[Use the roast_ammunition list as your source material — expand each into a full joke]

## 💪 What You're Actually Good At  
[3-5 genuine praise points from the praise_ammunition list]
[Be real — not sarcastic here]

## 📋 Actual Advice
[3-5 specific, actionable things they should do this week]
[Reference specific repos or patterns you found]

Rules:
- Every roast point MUST cite a specific number or fact
- Keep total length under 600 words
- Match the personality mode provided exactly
- End constructively — we build people up after tearing them down"""


CODE_ROAST_SYSTEM_PROMPT = """You are GitRoast analyzing real static analysis results from a developer's codebase.

You have REAL DATA from pylint, radon complexity analysis, and AST inspection.
Every point you make MUST reference a specific file, score, or finding from the data.

Format your response EXACTLY like this:

## 🔬 Code Quality Report

## 💣 What The Analysis Found
[5-7 specific findings with file names, scores, and line numbers where available]
[Use the roast_ammunition list — expand each into a full point with context]

## 🏆 What's Actually Good
[3-4 genuine strengths from the praise_ammunition list]

## 🔧 Fix This Week
[Top 3 highest-impact fixes, ordered by severity — be specific about which file and what to do]

## ☠️ The One Thing To Fix RIGHT NOW
[The single most critical finding — hardcoded secret, or highest complexity function, or worst file]

Rules:
- NEVER make up findings — only use what's in the data
- Reference specific filenames when available
- Be direct about severity without being demoralizing
- Match the personality mode provided"""


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def handle_analyze_developer(
    arguments: dict,
    scraper: GitHubScraper,
    orchestrator: GitRoastOrchestrator,
    engine: PersonalityEngine,
    groq_client: Groq,
) -> str:
    """Fetch, analyze, and roast a GitHub developer profile."""
    username: str = arguments.get("username", "").strip()
    personality: str = arguments.get("personality", "comedian")

    if not username:
        return "❌ Please provide a GitHub username. Example: `analyze_developer(username='torvalds')`"

    engine.validate_personality(personality)

    profile = await orchestrator.get_or_fetch_profile(username, scraper)

    top_lang_str = (
        ", ".join(f"{l['language']} ({l['percentage']}%)" for l in profile.top_languages)
        if profile.top_languages
        else "No language data"
    )

    roast_ammo_str = "\n".join(
        f"{i + 1}. {line}" for i, line in enumerate(profile.roast_ammunition)
    ) or "No specific roast ammunition generated."

    praise_ammo_str = "\n".join(
        f"{i + 1}. {line}" for i, line in enumerate(profile.praise_ammunition)
    ) or "No specific praise ammunition generated."

    prompt = f"""Developer Profile Data for GitHub user: {profile.username}

PROFILE SUMMARY:
- Name: {profile.name or "N/A"}
- Bio: {profile.bio or "N/A"}
- Location: {profile.location or "N/A"}
- Followers: {profile.followers}
- Following: {profile.following}
- Account age: {profile.account_age_days} days ({profile.account_age_days // 365} years)
- Total stars received: {profile.total_stars_received}
- Public repos: {profile.public_repos}

TOP LANGUAGES: {top_lang_str}

COMMIT STATS (last 90 days):
{json.dumps(profile.commit_stats.model_dump(), indent=2)}

PR STATS:
{json.dumps(profile.pr_stats.model_dump(), indent=2)}

ISSUE STATS:
{json.dumps(profile.issue_stats.model_dump(), indent=2)}

ROAST AMMUNITION (use these as your source material):
{roast_ammo_str}

PRAISE AMMUNITION (use these for genuine compliments):
{praise_ammo_str}

Personality mode: {personality}
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ROAST_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.85,
        )
        response_text = response.choices[0].message.content
    except Exception as exc:
        logger.warning(f"Groq API call failed, falling back to raw ammunition: {exc}")
        lines = [
            f"## 🔥 Roast: {profile.username}",
            "",
            "### The Roast",
        ]
        for item in profile.roast_ammunition:
            lines.append(f"- {item}")
        lines += ["", "### What You're Actually Good At"]
        for item in profile.praise_ammunition:
            lines.append(f"- {item}")
        response_text = "\n".join(lines)

    return engine.wrap_response(response_text, personality)


async def handle_analyze_code_quality(
    arguments: dict,
    analyzer: CodeAnalyzer,
    orchestrator: GitRoastOrchestrator,
    engine: PersonalityEngine,
    groq_client: Groq,
) -> str:
    """Run real static analysis on a developer's GitHub repos."""
    username: str = arguments.get("username", "").strip()
    personality: str = arguments.get("personality", "senior_dev")
    max_repos: int = min(int(arguments.get("max_repos", 3)), 5)

    if not username:
        return "❌ Please provide a GitHub username."

    engine.validate_personality(personality)

    result = await analyzer.analyze_developer_repos(username, max_repos)

    repo_summaries = []
    for r in result.repos_analyzed:
        repo_summaries.append(
            f"- {r.repo_name}: score {r.overall_score}/10, "
            f"{r.total_issues} issues ({r.critical_issues} critical), "
            f"test coverage: {'yes' if r.test_coverage_estimate > 0 else 'none'}"
        )

    roast_str = "\n".join(f"{i+1}. {line}" for i, line in enumerate(result.roast_ammunition)) or "No roast ammo."
    praise_str = "\n".join(f"{i+1}. {line}" for i, line in enumerate(result.praise_ammunition)) or "No praise ammo."

    prompt = f"""Code Quality Analysis for GitHub user: {username}

OVERALL GRADE: {result.overall_grade}
WORST FILE: {result.worst_file or 'N/A'}
MOST COMMON ISSUE: {result.most_common_issue or 'N/A'}
TOTAL SECRETS FOUND: {result.total_secrets_found}
TOTAL TODOS: {result.total_todos}

REPO SCORES:
{chr(10).join(repo_summaries)}

ROAST AMMUNITION:
{roast_str}

PRAISE AMMUNITION:
{praise_str}

Personality mode: {personality}
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": CODE_ROAST_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.8,
        )
        response_text = response.choices[0].message.content
    except Exception as exc:
        logger.warning(f"Groq failed for code quality, using fallback: {exc}")
        lines = [f"## 🔬 Code Quality: {username} — Grade {result.overall_grade}", ""]
        for line in result.roast_ammunition:
            lines.append(f"- {line}")
        response_text = "\n".join(lines)

    return engine.wrap_response(response_text, personality)


async def handle_followup(arguments: dict, orchestrator: GitRoastOrchestrator) -> str:
    """Answer a follow-up question about the last analyzed developer."""
    question = arguments.get("question", "").strip()
    if not question:
        return "❌ Please provide a question."
    return await orchestrator.answer_followup(question)


async def handle_stress_test_idea(
    arguments: dict,
    debater: IdeaDebater,
    orchestrator: GitRoastOrchestrator,
    engine: PersonalityEngine,
    groq_client: Groq,
) -> str:
    """Run the multi-agent debate to stress test a startup or project idea."""
    idea: str = arguments.get("idea", "").strip()
    context: str = arguments.get("context", "")
    personality: str = arguments.get("personality", "yc_founder")

    if len(idea) < 10:
        return "❌ Please describe your idea in at least 10 characters."

    engine.validate_personality(personality)

    try:
        result = await debater.run_debate(idea, context, personality)
        formatted_output = debater.format_debate_for_display(result)
        # Store debate result so scaffolder can use it for context
        orchestrator.last_debate_result = result
        return engine.wrap_response(formatted_output, personality)
    except Exception as exc:
        logger.exception(f"Idea stress test failed: {exc}")
        return (
            f"❌ The debate arena caught fire: {exc}\n\n"
            "Please check your GROQ_API_KEY and try again. "
            "Free tier: console.groq.com"
        )


async def handle_scaffold_project(
    arguments: dict,
    scaffolder: ProjectScaffolder,
    orchestrator: GitRoastOrchestrator,
    engine: PersonalityEngine,
    groq_client: Groq,
) -> str:
    """Turn an idea into a complete starter project."""
    idea: str = arguments.get("idea", "").strip()
    personality: str = arguments.get("personality", "yc_founder")
    create_repo: bool = bool(arguments.get("create_repo", False))

    if not idea:
        return "❌ Please provide a project idea."

    engine.validate_personality(personality)

    # Pass debate context if available
    debate_result_text: str | None = None
    if orchestrator.last_debate_result:
        debate_result_text = orchestrator.last_debate_result.verdict.verdict_reasoning

    try:
        result = await scaffolder.scaffold(idea, debate_result_text, personality)

        if create_repo:
            repo_url = await scaffolder.create_github_repo(
                result.project_name,
                result.project_description,
                result.files,
            )
            if repo_url:
                result = result.model_copy(update={"github_repo_url": repo_url})

        formatted_output = scaffolder.format_scaffold_for_display(result)
        return engine.wrap_response(formatted_output, personality)
    except Exception as exc:
        logger.exception(f"Scaffold failed: {exc}")
        return (
            f"❌ Scaffolding failed: {exc}\n\n"
            "Please check your GROQ_API_KEY and try again."
        )


# ---------------------------------------------------------------------------
# Competitor research handler
# ---------------------------------------------------------------------------

async def handle_research_competitors(
    arguments: dict,
    researcher: CompetitorResearcher,
    engine: PersonalityEngine,
    groq_client: Groq,
) -> str:
    """Search GitHub for competitor projects and synthesize intelligence."""
    idea: str = arguments.get("idea", "").strip()
    personality: str = arguments.get("personality", "yc_founder")

    if not idea or len(idea) < 10:
        return (
            "❌ Please describe your idea more specifically. "
            "Example: `research_competitors(idea='VS Code extension for AI code review')`"
        )

    engine.validate_personality(personality)

    try:
        report = await researcher.research(idea, personality)
        formatted = researcher.format_report_for_display(report)
        return engine.wrap_response(formatted, personality)
    except Exception as exc:
        logger.exception(f"Competitor research failed: {exc}")
        return (
            f"❌ Competitor research failed: {exc}\n\n"
            "Please check that your GITHUB_TOKEN is set in .env\n"
            "Get a free token at: https://github.com/settings/tokens\n"
            "Scopes needed: read:user, public_repo"
        )


# ---------------------------------------------------------------------------
# Phase 5 handlers
# ---------------------------------------------------------------------------

async def handle_roast_team(
    arguments: dict,
    team_roaster: TeamRoaster,
    scraper: GitHubScraper,
    orchestrator: GitRoastOrchestrator,
    engine: PersonalityEngine,
    groq_client: Groq,
) -> str:
    """Analyze multiple GitHub profiles and generate a team roast."""
    raw_usernames: str = arguments.get("usernames", "")
    personality: str = arguments.get("personality", "comedian")

    if not raw_usernames.strip():
        return "❌ Please provide comma-separated GitHub usernames. Example: `roast_team(usernames='alice,bob,charlie')`"

    usernames = [u.strip() for u in raw_usernames.split(",") if u.strip()]
    engine.validate_personality(personality)

    try:
        report = await team_roaster.analyze_team(
            usernames, scraper, orchestrator.session_profiles
        )
        formatted = team_roaster.format_team_report(report, personality)
        return engine.wrap_response(formatted, personality)
    except Exception as exc:
        logger.exception(f"Team roast failed: {exc}")
        return f"❌ Team roast failed: {exc}"


async def handle_watch_workspace(
    arguments: dict,
    file_watcher: FileWatcher,
) -> str:
    """Start, stop, or check status of the real-time file watcher."""
    action: str = arguments.get("action", "status").lower()
    watch_path: str = arguments.get("path", "").strip()

    if action == "start":
        if not watch_path:
            return "❌ Please provide a directory path. Example: `watch_workspace(action='start', path='/path/to/project')`"
        return file_watcher.start(watch_path)
    elif action == "stop":
        return file_watcher.stop()
    elif action == "results":
        return file_watcher.format_recent_results()
    elif action == "analyze":
        file_path = arguments.get("file", watch_path)
        if not file_path:
            return "❌ Provide a file path to analyze."
        result = file_watcher.analyze_single_file(file_path)
        return file_watcher.format_result(result)
    else:
        return file_watcher.get_status()


async def handle_send_to_webhook(
    arguments: dict,
    webhook_notifier: WebhookNotifier,
) -> str:
    """Send content to a Slack, Discord, or generic webhook."""
    webhook_url: str = arguments.get("webhook_url", "").strip()
    content: str = arguments.get("content", "").strip()
    title: str = arguments.get("title", "").strip() or None

    if not webhook_url:
        return (
            "❌ Please provide a webhook URL.\n\n"
            "**How to get one:**\n"
            "- Slack: api.slack.com/messaging/webhooks\n"
            "- Discord: Server Settings → Integrations → Webhooks"
        )
    if not content:
        return "❌ Please provide content to send."

    result = await webhook_notifier.send(webhook_url, content, title)
    return webhook_notifier.format_send_result(result)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main():
    load_dotenv()
    console = Console(stderr=True)

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        console.print(
            "[bold red]X GROQ_API_KEY not found![/bold red]\n"
            "Get a free key at [link=https://console.groq.com]console.groq.com[/link] "
            "(no credit card required), then add it to your .env file:\n\n"
            "  GROQ_API_KEY=your_key_here"
        )
        return

    # Initialize components
    groq_client = Groq(api_key=groq_api_key)
    scraper = GitHubScraper()
    analyzer = CodeAnalyzer()
    engine = PersonalityEngine()
    orchestrator = GitRoastOrchestrator(groq_client)
    debater = IdeaDebater(groq_client)
    scaffolder = ProjectScaffolder(groq_client, github_token=os.getenv("GITHUB_TOKEN"))
    researcher = CompetitorResearcher(groq_client, github_token=os.getenv("GITHUB_TOKEN", ""))

    # Phase 5 components
    team_roaster = TeamRoaster(groq_client)
    file_watcher = FileWatcher()
    webhook_notifier = WebhookNotifier()

    # Initialize MCP server
    server = Server("gitroast")

    # ------------------------------------------------------------------
    # Register tool list
    # ------------------------------------------------------------------
    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="analyze_developer",
                description=(
                    "Deeply analyze a GitHub developer profile and generate a personalized roast + "
                    "genuine feedback using real data from their commits, PRs, issues, and repos."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "GitHub username to analyze (e.g. 'torvalds')",
                        },
                        "personality": {
                            "type": "string",
                            "enum": ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"],
                            "default": "comedian",
                            "description": "Roast personality mode",
                        },
                    },
                    "required": ["username"],
                },
            ),
            types.Tool(
                name="set_personality",
                description="Switch the roast personality mode for the current session.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "personality": {
                            "type": "string",
                            "enum": ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"],
                            "description": "Personality mode to switch to",
                        },
                    },
                    "required": ["personality"],
                },
            ),
            types.Tool(
                name="ask_followup",
                description=(
                    "Ask a follow-up question about the last analyzed developer "
                    "without re-fetching GitHub."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Your follow-up question about the analyzed developer",
                        },
                    },
                    "required": ["question"],
                },
            ),
            types.Tool(
                name="clear_session",
                description="Clear the current session cache and conversation history.",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="analyze_code_quality",
                description=(
                    "Analyze code quality of a developer's GitHub repos using real static analysis "
                    "(pylint, radon complexity, AST inspection). Detects secrets, complexity issues, "
                    "missing tests, and more."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "GitHub username whose repos to analyze",
                        },
                        "personality": {
                            "type": "string",
                            "enum": ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"],
                            "default": "senior_dev",
                            "description": "Roast personality mode",
                        },
                        "max_repos": {
                            "type": "number",
                            "description": "Number of repos to analyze (1-5, default 3)",
                            "default": 3,
                        },
                    },
                    "required": ["username"],
                },
            ),
            types.Tool(
                name="stress_test_idea",
                description=(
                    "Run a multi-agent debate to stress test your startup or project idea. "
                    "Three AI agents debate it: The Believer builds the strongest case FOR it, "
                    "The Destroyer finds every flaw, The Judge delivers a verdict with a refined "
                    "version of your idea and concrete next steps."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "idea": {
                            "type": "string",
                            "description": "Your startup or project idea - describe it in 1-3 sentences",
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional: your background, target users, or any constraints",
                        },
                        "personality": {
                            "type": "string",
                            "enum": ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"],
                            "default": "yc_founder",
                        },
                    },
                    "required": ["idea"],
                },
            ),
            types.Tool(
                name="scaffold_project",
                description=(
                    "Turn your idea into a complete starter project with folder structure, "
                    "tech stack, core files, and a 4-week roadmap. "
                    "Run stress_test_idea first for best results."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "idea": {
                            "type": "string",
                            "description": "The project idea to scaffold",
                        },
                        "create_repo": {
                            "type": "boolean",
                            "description": (
                                "Create an actual GitHub repo with the scaffold "
                                "(requires repo scope on your GitHub PAT)"
                            ),
                            "default": False,
                        },
                        "personality": {
                            "type": "string",
                            "enum": ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"],
                            "default": "yc_founder",
                        },
                    },
                    "required": ["idea"],
                },
            ),
            types.Tool(
                name="research_competitors",
                description=(
                    "Search GitHub for similar projects and generate competitor intelligence - "
                    "who built what, where they fall short, and what your differentiating wedge is. "
                    "Uses GitHub Search API (free). "
                    "Output: competitor table, differentiation angles, strategic synthesis, and your wedge."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "idea": {
                            "type": "string",
                            "description": "Your idea or project concept to research competitors for",
                        },
                        "personality": {
                            "type": "string",
                            "enum": ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"],
                            "default": "yc_founder",
                            "description": "Personality mode for the intelligence report",
                        },
                    },
                    "required": ["idea"],
                },
            ),
            types.Tool(
                name="roast_team",
                description=(
                    "Analyze multiple GitHub developers simultaneously and generate a team roast. "
                    "Compares commit frequency, code quality, documentation, testing, and more. "
                    "Outputs a leaderboard, comparison table, and group roast."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "usernames": {
                            "type": "string",
                            "description": "Comma-separated GitHub usernames (2-6). Example: 'alice,bob,charlie'",
                        },
                        "personality": {
                            "type": "string",
                            "enum": ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"],
                            "default": "comedian",
                        },
                    },
                    "required": ["usernames"],
                },
            ),
            types.Tool(
                name="watch_workspace",
                description=(
                    "Control the real-time file watcher. Actions: 'start' (begin watching a directory), "
                    "'stop' (stop watching), 'status' (current state), 'results' (recent analysis), "
                    "'analyze' (analyze a single file on demand). "
                    "When active, automatically analyzes Python files on save."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["start", "stop", "status", "results", "analyze"],
                            "default": "status",
                            "description": "The watcher action to perform",
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory path to watch (required for 'start') or file path (for 'analyze')",
                        },
                        "file": {
                            "type": "string",
                            "description": "File path for 'analyze' action",
                        },
                    },
                },
            ),
            types.Tool(
                name="send_to_webhook",
                description=(
                    "Send GitRoast results to a Slack, Discord, or any webhook URL. "
                    "Auto-detects the platform and formats the content accordingly. "
                    "Supports Slack Block Kit, Discord Embeds, and generic JSON."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "webhook_url": {
                            "type": "string",
                            "description": "The webhook URL to send to",
                        },
                        "content": {
                            "type": "string",
                            "description": "The Markdown content to send",
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional title override (auto-detected from content if not provided)",
                        },
                    },
                    "required": ["webhook_url", "content"],
                },
            ),
        ]

    # ------------------------------------------------------------------
    # Register tool call handler
    # ------------------------------------------------------------------
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        try:
            if name == "analyze_developer":
                result = await handle_analyze_developer(
                    arguments, scraper, orchestrator, engine, groq_client
                )
            elif name == "set_personality":
                personality = arguments.get("personality", "")
                result = orchestrator.set_personality(personality, engine)
            elif name == "ask_followup":
                result = await handle_followup(arguments, orchestrator)
            elif name == "clear_session":
                result = orchestrator.clear_session()
            elif name == "analyze_code_quality":
                result = await handle_analyze_code_quality(
                    arguments, analyzer, orchestrator, engine, groq_client
                )
            elif name == "stress_test_idea":
                result = await handle_stress_test_idea(
                    arguments, debater, orchestrator, engine, groq_client
                )
            elif name == "scaffold_project":
                result = await handle_scaffold_project(
                    arguments, scaffolder, orchestrator, engine, groq_client
                )
            elif name == "research_competitors":
                result = await handle_research_competitors(
                    arguments, researcher, engine, groq_client
                )
            elif name == "roast_team":
                result = await handle_roast_team(
                    arguments, team_roaster, scraper, orchestrator, engine, groq_client
                )
            elif name == "watch_workspace":
                result = await handle_watch_workspace(arguments, file_watcher)
            elif name == "send_to_webhook":
                result = await handle_send_to_webhook(arguments, webhook_notifier)
            else:
                result = f"Unknown tool: {name}"
        except Exception as exc:
            logger.exception(f"Error in tool '{name}': {exc}")
            result = f"X Error: {exc}"

        return [types.TextContent(type="text", text=result)]

    # ------------------------------------------------------------------
    # Startup banner
    # ------------------------------------------------------------------
    console.print(
        "\n[bold red]GitRoast MCP Server v0.5.0 - Online[/bold red]\n"
        "[dim]LLM: Groq (llama-3.3-70b-versatile) - Free tier[/dim]\n"
        "[bold green]Phase 5 LIVE: Team Roast + File Watcher + Webhooks[/bold green]\n"
        "[dim]11 tools registered. Waiting for connections via stdio...[/dim]\n"
    )

    # ------------------------------------------------------------------
    # Run server
    # ------------------------------------------------------------------
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
