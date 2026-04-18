"""Tests for GitRoast Idea Stress Tester (Phase 3)"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.tools.idea_debater import (
    AgentArgument,
    DebateResult,
    DebateVerdict,
    IdeaDebater,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_mock_groq(content: str):
    """Return a Groq client mock that always returns `content`."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_completion.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


BELIEVER_RESPONSE = """## 🟢 The Case FOR This Idea

### Why The Timing Is Right
AI developer tools are exploding. Copilot crossed 1M users in 2023.

### The Real Market Opportunity
$10B market for developer tooling.

### Why This Team / Person Can Win
Solo devs have shipped great VS Code extensions before.

### The Unfair Advantage
First mover with personality-driven feedback.

### Comparable Wins
GitHub Copilot, Tabnine, Sourcery all found massive audiences.

### Key Points Summary
- Timing is right with AI wave
- Developer tools market is huge
- Strong meme potential for viral growth
- Low barrier to entry
- Can iterate fast

Confidence Score: 8/10"""


DESTROYER_RESPONSE = """## 🔴 The Case AGAINST This Idea

### The Believer Got This Wrong
The market is already saturated with AI code tools.

### Why The Market Won't Care
Developers don't want to be roasted — they want real help.

### The Graveyard
Sourcery, DeepCode, Codacy all struggled with adoption.

### Technical / Execution Risks
LLM rate limits will throttle heavy users immediately.

### The Timeline Problem
Building a production VS Code extension takes 3x longer than expected.

### Key Points Summary
- Saturated market
- Wrong user psychology
- Rate limit ceiling
- Extension maintenance burden
- Novelty wears off fast

Confidence Score: 7/10"""


JUDGE_RESPONSE = """## ⚖️ The Verdict

### Who Won The Debate
The Destroyer made the stronger case on market saturation, but missed the entertainment angle.

### The Refined Idea
A VS Code extension that gives personality-driven code reviews tied to real static analysis metrics, not just jokes.

### Verdict: VALIDATE FIRST
This is a novelty product that could go viral or die in a week. Validate with 100 real users before building more.

### The One Thing That Will Make Or Break This
Whether developers find the roast tone entertaining or annoying after the first use.

### Next Steps (In Order)
1. Build a landing page and collect 100 email signups
2. Release a beta to those 100 users
3. Measure day-7 retention
4. Iterate on the personality tone based on feedback
5. Add real static analysis data to back up every roast

### Scores
- Fundability: 4/10
- Technical Difficulty: 6/10
- Market Size: Medium
- Overall Recommendation: VALIDATE FIRST"""


def make_debate_result() -> DebateResult:
    """Create a mock DebateResult for display tests."""
    believer = AgentArgument(
        agent_name="Believer",
        agent_emoji="🟢",
        argument=BELIEVER_RESPONSE,
        key_points=["Timing is right", "Big market", "Viral potential"],
        confidence=8,
        word_count=100,
    )
    destroyer = AgentArgument(
        agent_name="Destroyer",
        agent_emoji="🔴",
        argument=DESTROYER_RESPONSE,
        key_points=["Saturated market", "Wrong psychology", "Rate limits"],
        confidence=7,
        word_count=90,
    )
    verdict = DebateVerdict(
        recommendation="VALIDATE FIRST",
        verdict_reasoning="Novelty product — validate before building.",
        refined_idea="Personality-driven code reviews backed by real static analysis.",
        biggest_risk="Whether developers find the roast entertaining or annoying.",
        biggest_opportunity="Viral potential in developer communities.",
        next_steps=["Build landing page", "Get 100 signups", "Release beta"],
        fundability_score=4,
        technical_difficulty=6,
        market_size_estimate="Medium",
    )
    return DebateResult(
        original_idea="A VS Code extension that roasts your code",
        believer_argument=believer,
        destroyer_argument=destroyer,
        verdict=verdict,
        debate_duration_seconds=12.5,
        personality="yc_founder",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debate_returns_all_three_agents():
    """All three agents (Believer, Destroyer, Judge) must be present in the result."""
    client = make_mock_groq(BELIEVER_RESPONSE)

    # Each call returns progressively different content
    responses = [BELIEVER_RESPONSE, DESTROYER_RESPONSE, JUDGE_RESPONSE]
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        mock = MagicMock()
        mock.choices[0].message.content = responses[min(call_count, 2)]
        call_count += 1
        return mock

    client.chat.completions.create.side_effect = side_effect

    debater = IdeaDebater(client)
    result = await debater.run_debate("A todo app with AI")

    assert result.believer_argument.agent_name == "Believer"
    assert result.destroyer_argument.agent_name == "Destroyer"
    assert result.verdict is not None
    assert isinstance(result, DebateResult)


@pytest.mark.asyncio
async def test_believer_has_key_points():
    """Believer response with Key Points Summary section should parse key_points."""
    client = make_mock_groq(BELIEVER_RESPONSE)

    call_count = 0
    responses = [BELIEVER_RESPONSE, DESTROYER_RESPONSE, JUDGE_RESPONSE]

    def side_effect(*args, **kwargs):
        nonlocal call_count
        mock = MagicMock()
        mock.choices[0].message.content = responses[min(call_count, 2)]
        call_count += 1
        return mock

    client.chat.completions.create.side_effect = side_effect

    debater = IdeaDebater(client)
    result = await debater.run_debate("An idea")

    assert len(result.believer_argument.key_points) >= 1


@pytest.mark.asyncio
async def test_verdict_recommendation_is_valid():
    """Judge response containing 'BUILD IT' should produce a valid recommendation."""
    judge_text_build = JUDGE_RESPONSE.replace("VALIDATE FIRST", "BUILD IT")
    responses = [BELIEVER_RESPONSE, DESTROYER_RESPONSE, judge_text_build]
    call_count = 0

    client = MagicMock()

    def side_effect(*args, **kwargs):
        nonlocal call_count
        mock = MagicMock()
        mock.choices[0].message.content = responses[min(call_count, 2)]
        call_count += 1
        return mock

    client.chat.completions.create.side_effect = side_effect

    debater = IdeaDebater(client)
    result = await debater.run_debate("An idea")

    assert result.verdict.recommendation in ["BUILD IT", "PIVOT", "KILL IT", "VALIDATE FIRST"]


def test_parse_verdict_extracts_fundability():
    """_parse_verdict should correctly extract numeric scores."""
    judge_text = (
        "## ⚖️ The Verdict\n\n"
        "### Scores\n"
        "- Fundability: 7/10\n"
        "- Technical Difficulty: 5/10\n"
        "- Market Size: Medium\n"
        "- Overall Recommendation: BUILD IT\n"
    )
    debater = IdeaDebater(MagicMock())
    verdict = debater._parse_verdict(judge_text)

    assert verdict.fundability_score == 7
    assert verdict.technical_difficulty == 5


@pytest.mark.asyncio
async def test_short_idea_rejected():
    """Ideas shorter than 10 characters should be rejected with a helpful message."""
    from mcp_server.server import handle_stress_test_idea
    from mcp_server.personality.engine import PersonalityEngine

    engine = PersonalityEngine()
    debater = IdeaDebater(MagicMock())
    orchestrator = MagicMock()
    groq_client = MagicMock()

    result = await handle_stress_test_idea(
        {"idea": "hi"},
        debater,
        orchestrator,
        engine,
        groq_client,
    )

    assert "at least 10 characters" in result


def test_format_debate_for_display_contains_all_sections():
    """Formatted debate output must contain all three agent emojis."""
    debater = IdeaDebater(MagicMock())
    result = make_debate_result()
    formatted = debater.format_debate_for_display(result)

    assert "🟢" in formatted
    assert "🔴" in formatted
    assert "⚖️" in formatted
    assert result.original_idea in formatted
