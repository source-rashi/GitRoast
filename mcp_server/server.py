"""
GitRoast — MCP Server Entry Point
=====================================
Exposes 8 MCP tools to any compatible agent (Claude Desktop, Cursor, etc).
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

LLM: Groq (free, no credit card, llama3-70b-8192)
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
            model="llama3-70b-8192",
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
            model="llama3-70b-8192",
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
        "\n[bold red]GitRoast MCP Server v0.4.0 - Online[/bold red]\n"
        "[dim]LLM: Groq (llama3-70b-8192) - Free tier[/dim]\n"
        "[bold green]Phase 4 LIVE: Competitor Researcher + VS Code Polish[/bold green]\n"
        "[dim]8 tools registered. Waiting for connections via stdio...[/dim]\n"
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
