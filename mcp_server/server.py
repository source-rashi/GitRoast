"""
GitRoast — MCP Server Entry Point
=====================================
Exposes 5 MCP tools to any compatible agent (Claude Desktop, Cursor, etc).
Communicates via stdio — the standard MCP protocol.

Tools:
  1. analyze_developer      — Full GitHub profile roast (Phase 1, LIVE)
  2. analyze_code_quality   — Static code analysis (Phase 2, stub)
  3. stress_test_idea        — Multi-agent idea debate (Phase 3, stub)
  4. scaffold_project        — Project scaffolding (Phase 4, stub)
  5. research_competitors    — Competitor intelligence (Phase 4, stub)

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
from mcp_server.personality.engine import PersonalityEngine
from mcp_server.orchestrator import GitRoastOrchestrator

# ---------------------------------------------------------------------------
# System prompt
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

    # Build a rich prompt with all real data
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
        # Fallback: format raw ammunition as markdown
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


async def handle_followup(arguments: dict, orchestrator: GitRoastOrchestrator) -> str:
    """Answer a follow-up question about the last analyzed developer."""
    question = arguments.get("question", "").strip()
    if not question:
        return "❌ Please provide a question."
    return await orchestrator.answer_followup(question)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main():
    load_dotenv()
    console = Console()

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        console.print(
            "[bold red]❌ GROQ_API_KEY not found![/bold red]\n"
            "Get a free key at [link=https://console.groq.com]console.groq.com[/link] "
            "(no credit card required), then add it to your .env file:\n\n"
            "  GROQ_API_KEY=your_key_here"
        )
        return

    # Initialize components
    groq_client = Groq(api_key=groq_api_key)
    scraper = GitHubScraper()
    engine = PersonalityEngine()
    orchestrator = GitRoastOrchestrator(groq_client)

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
                description="Analyze code quality with static analysis. [Coming in Phase 2]",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_url": {
                            "type": "string",
                            "description": "GitHub repository URL to analyze",
                        },
                    },
                    "required": ["repo_url"],
                },
            ),
            types.Tool(
                name="stress_test_idea",
                description=(
                    "Run a multi-agent debate to stress test a startup or project idea. "
                    "[Coming in Phase 3]"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "idea": {
                            "type": "string",
                            "description": "Your startup or project idea",
                        },
                    },
                    "required": ["idea"],
                },
            ),
            types.Tool(
                name="scaffold_project",
                description="Scaffold a complete project structure from an idea. [Coming in Phase 4]",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "idea": {
                            "type": "string",
                            "description": "Your project idea",
                        },
                    },
                    "required": ["idea"],
                },
            ),
            types.Tool(
                name="research_competitors",
                description="Research existing competitors for your idea. [Coming in Phase 4]",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "idea": {
                            "type": "string",
                            "description": "Your project idea to research competitors for",
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
                result = "🔨 Code quality analyzer coming in Phase 2. Stay tuned."
            elif name == "stress_test_idea":
                result = "🧠 Idea stress tester (multi-agent debate) coming in Phase 3."
            elif name == "scaffold_project":
                result = "🏗️ Project scaffolder coming in Phase 4."
            elif name == "research_competitors":
                result = "🕵️ Competitor researcher coming in Phase 4."
            else:
                result = f"Unknown tool: {name}"
        except Exception as exc:
            logger.exception(f"Error in tool '{name}': {exc}")
            result = f"❌ Error: {exc}"

        return [types.TextContent(type="text", text=result)]

    # ------------------------------------------------------------------
    # Startup banner
    # ------------------------------------------------------------------
    console.print(
        "\n[bold red]🔥 GitRoast MCP Server v0.1.0 — Online[/bold red]\n"
        "[dim]LLM: Groq (llama3-70b-8192) — Free tier[/dim]\n"
        "[dim]Waiting for connections via stdio...[/dim]\n"
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
