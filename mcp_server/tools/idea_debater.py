"""
GitRoast — Idea Stress Tester
================================
Multi-agent debate system that pressure-tests startup and project ideas.

Three agents run sequentially using Groq (free tier, no credit card):
  Agent 1 — The Believer: builds the strongest case FOR the idea
  Agent 2 — The Destroyer: finds every flaw, risk, and reason it will fail
  Agent 3 — The Judge: weighs both sides, gives verdict + refined idea

The user watches the debate unfold in real time.
Each agent's output is streamed back as it completes.

Free tier: Groq llama3-70b-8192, ~14,400 requests/day
"""

import re
import time
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AgentArgument(BaseModel):
    """Structured output from a single debate agent."""
    agent_name: str          # "Believer", "Destroyer", "Judge"
    agent_emoji: str         # "🟢", "🔴", "⚖️"
    argument: str            # the full argument text
    key_points: list[str]    # 3-5 bullet point summary
    confidence: int          # 1-10 how confident this agent is
    word_count: int


class DebateVerdict(BaseModel):
    """Final verdict from The Judge."""
    recommendation: str          # "BUILD IT", "PIVOT", "KILL IT", "VALIDATE FIRST"
    verdict_reasoning: str       # 2-3 sentence explanation
    refined_idea: str            # improved version of the original idea
    biggest_risk: str            # the single most important risk to address
    biggest_opportunity: str     # the single most compelling opportunity
    next_steps: list[str]        # 3-5 concrete next steps ordered by priority
    fundability_score: int       # 1-10 how fundable this is
    technical_difficulty: int    # 1-10
    market_size_estimate: str    # "Small (<$1M)", "Medium ($1M-$100M)", "Large ($100M+)", "Unknown"


class DebateResult(BaseModel):
    """Complete result of a 3-agent idea debate."""
    original_idea: str
    believer_argument: AgentArgument
    destroyer_argument: AgentArgument
    verdict: DebateVerdict
    debate_duration_seconds: float
    personality: str
    timestamp: str


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class IdeaDebater:
    """Multi-agent idea stress tester — runs Believer vs Destroyer vs Judge on Groq."""

    # -----------------------------------------------------------------------
    # Agent system prompts
    # -----------------------------------------------------------------------

    BELIEVER_SYSTEM_PROMPT = """You are The Believer — Agent 1 in a startup idea debate.

Your job: Build the STRONGEST possible case FOR this idea.
You are not a cheerleader — you are a rigorous advocate.
Find the real reasons this could work. Be specific, not hype.

Structure your argument EXACTLY like this:

## 🟢 The Case FOR This Idea

### Why The Timing Is Right
[2-3 sentences on why NOW is the right moment for this]

### The Real Market Opportunity
[Specific market size reasoning, who has this problem and how badly]

### Why This Team / Person Can Win
[Based on what the person told you about themselves, why are THEY positioned to build this]

### The Unfair Advantage
[What moat or edge does this have that competitors can't easily copy]

### Comparable Wins
[2-3 real examples of similar ideas that succeeded and why this could follow the same path]

### Key Points Summary
- [bullet 1]
- [bullet 2]
- [bullet 3]
- [bullet 4]
- [bullet 5]

Confidence Score: [X]/10

Rules:
- Be specific — cite real companies, real numbers, real trends
- Do not mention any risks or downsides (that's the Destroyer's job)
- Keep total response under 500 words
- If the idea is genuinely weak, still make the best case you can"""

    DESTROYER_SYSTEM_PROMPT = """You are The Destroyer — Agent 2 in a startup idea debate.

Your job: Find EVERY reason this idea will fail. Be ruthless but accurate.
You are not a pessimist — you are a rigorous critic who has seen a thousand ideas die.
You have also read The Believer's argument. Directly counter its strongest points.

Structure your argument EXACTLY like this:

## 🔴 The Case AGAINST This Idea

### The Believer Got This Wrong
[Pick the 2 strongest points from The Believer's argument and dismantle them with specific counter-evidence]

### Why The Market Won't Care
[Specific reasons why target users won't pay / won't switch / won't adopt]

### The Graveyard
[2-3 real companies that tried this and failed, and what killed them]

### Technical / Execution Risks
[The hardest technical or operational problems that will actually kill this]

### The Timeline Problem
[Why this will take 3x longer and cost 5x more than expected]

### Key Points Summary
- [bullet 1]
- [bullet 2]
- [bullet 3]
- [bullet 4]
- [bullet 5]

Confidence Score: [X]/10

Rules:
- Be specific — cite real failures, real obstacles, real competitor moats
- Do not mention any positives (that was The Believer's job)
- Keep total response under 500 words
- If the idea is genuinely strong, still find the real risks"""

    JUDGE_SYSTEM_PROMPT = """You are The Judge — Agent 3 and final arbiter in a startup idea debate.

You have read both The Believer's case FOR and The Destroyer's case AGAINST.
Your job: weigh both sides objectively and deliver a final verdict with a refined version of the idea.

Structure your response EXACTLY like this:

## ⚖️ The Verdict

### Who Won The Debate
[1-2 sentences on which agent made the stronger case and why]

### The Refined Idea
[Improved version of the original idea that addresses the Destroyer's strongest objections
while preserving the Believer's strongest points. Be specific — this should be actionable.]

### Verdict: [BUILD IT / PIVOT / KILL IT / VALIDATE FIRST]
[2-3 sentences explaining the verdict]

### The One Thing That Will Make Or Break This
[Single most important factor — could be market timing, technical feasibility, team, or competition]

### Next Steps (In Order)
1. [Most important first step — specific and actionable]
2. [Second step]
3. [Third step]
4. [Fourth step]
5. [Fifth step]

### Scores
- Fundability: [X]/10
- Technical Difficulty: [X]/10
- Market Size: [Small/Medium/Large/Unknown]
- Overall Recommendation: [BUILD IT / PIVOT / KILL IT / VALIDATE FIRST]

Rules:
- Be the adult in the room — balanced, specific, actionable
- The refined idea must be genuinely better than the original
- Next steps must be things the person can actually do this week
- Keep total response under 600 words"""

    def __init__(self, groq_client):
        self.groq_client = groq_client
        self.console = Console()
        logger.info("IdeaDebater initialized.")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def run_debate(
        self,
        idea: str,
        context: str = "",
        personality: str = "yc_founder",
    ) -> DebateResult:
        """Run the full 3-agent debate and return structured results."""
        start_time = time.time()

        self.console.print(
            Panel(
                f"[bold white]{idea}[/bold white]",
                title="[bold yellow]🎭 GitRoast Debate Arena[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

        # ---- Agent 1: Believer ----
        self.console.print(
            "\n[bold green]Agent 1: The Believer is building the case FOR...[/bold green]"
        )
        believer_result = await self._run_agent(
            agent_name="Believer",
            emoji="🟢",
            system_prompt=self.BELIEVER_SYSTEM_PROMPT,
            idea=idea,
            context=context,
            previous_argument=None,
        )
        self.console.print(
            Panel(
                believer_result.argument,
                title="[green]🟢 The Believer[/green]",
                border_style="green",
            )
        )

        # ---- Agent 2: Destroyer ----
        self.console.print(
            "\n[bold red]Agent 2: The Destroyer is finding every flaw...[/bold red]"
        )
        destroyer_result = await self._run_agent(
            agent_name="Destroyer",
            emoji="🔴",
            system_prompt=self.DESTROYER_SYSTEM_PROMPT,
            idea=idea,
            context=context,
            previous_argument=believer_result.argument,
        )
        self.console.print(
            Panel(
                destroyer_result.argument,
                title="[red]🔴 The Destroyer[/red]",
                border_style="red",
            )
        )

        # ---- Agent 3: Judge ----
        self.console.print(
            "\n[bold yellow]Agent 3: The Judge is deliberating...[/bold yellow]"
        )
        judge_text, verdict = await self._run_agent_judge(
            system_prompt=self.JUDGE_SYSTEM_PROMPT,
            idea=idea,
            believer_arg=believer_result.argument,
            destroyer_arg=destroyer_result.argument,
        )
        self.console.print(
            Panel(
                judge_text,
                title="[yellow]⚖️ The Judge[/yellow]",
                border_style="yellow",
            )
        )

        duration = time.time() - start_time

        return DebateResult(
            original_idea=idea,
            believer_argument=believer_result,
            destroyer_argument=destroyer_result,
            verdict=verdict,
            debate_duration_seconds=round(duration, 2),
            personality=personality,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # -----------------------------------------------------------------------
    # Internal agent runners
    # -----------------------------------------------------------------------

    async def _run_agent(
        self,
        agent_name: str,
        emoji: str,
        system_prompt: str,
        idea: str,
        context: str,
        previous_argument: Optional[str],
    ) -> AgentArgument:
        """Call Groq for a single agent and parse the response."""
        user_message = f"The idea being debated: {idea}"
        if context:
            user_message += f"\nAdditional context from the person: {context}"
        if previous_argument:
            user_message += (
                f"\n\nThe Believer has already argued:\n{previous_argument}"
                "\n\nNow make your case against it."
            )

        try:
            response = self.groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=800,
                temperature=0.8,
            )
            argument_text = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(f"Groq call failed for agent {agent_name}: {exc}")
            argument_text = f"[{agent_name} could not generate argument: {exc}]"

        key_points = self._extract_key_points(argument_text)
        confidence = self._extract_confidence(argument_text)
        word_count = len(argument_text.split())

        return AgentArgument(
            agent_name=agent_name,
            agent_emoji=emoji,
            argument=argument_text,
            key_points=key_points,
            confidence=confidence,
            word_count=word_count,
        )

    async def _run_agent_judge(
        self,
        system_prompt: str,
        idea: str,
        believer_arg: str,
        destroyer_arg: str,
    ) -> tuple[str, DebateVerdict]:
        """Run the Judge agent and return (raw_text, DebateVerdict)."""
        user_message = (
            f"The idea being debated: {idea}\n\n"
            f"THE BELIEVER ARGUED:\n{believer_arg}\n\n"
            f"THE DESTROYER ARGUED:\n{destroyer_arg}\n\n"
            "Now deliver your verdict."
        )

        try:
            response = self.groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=900,
                temperature=0.7,
            )
            judge_text = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(f"Groq call failed for Judge: {exc}")
            judge_text = f"[Judge could not generate verdict: {exc}]"

        verdict = self._parse_verdict(judge_text)
        return judge_text, verdict

    # -----------------------------------------------------------------------
    # Parsing helpers
    # -----------------------------------------------------------------------

    def _extract_key_points(self, text: str) -> list[str]:
        """Extract bullet points from the Key Points Summary section."""
        points: list[str] = []
        in_summary = False
        for line in text.splitlines():
            if "Key Points Summary" in line:
                in_summary = True
                continue
            if in_summary:
                stripped = line.strip()
                if stripped.startswith("- "):
                    points.append(stripped[2:].strip())
                elif stripped.startswith("###") and points:
                    # Hit the next section — stop
                    break
        return points if points else []

    def _extract_confidence(self, text: str) -> int:
        """Extract the confidence score (X/10) from agent text."""
        match = re.search(r"Confidence Score:\s*(\d+)\s*/\s*10", text, re.IGNORECASE)
        if match:
            try:
                return max(1, min(10, int(match.group(1))))
            except ValueError:
                pass
        return 5  # Sensible default

    def _parse_verdict(self, judge_text: str) -> DebateVerdict:
        """Parse the Judge's text into a structured DebateVerdict."""

        # Recommendation
        recommendation = "VALIDATE FIRST"  # default
        for rec in ["BUILD IT", "KILL IT", "VALIDATE FIRST", "PIVOT"]:
            if rec in judge_text.upper():
                recommendation = rec
                break

        # Fundability score
        fundability = 5
        fm = re.search(r"Fundability:\s*(\d+)\s*/\s*10", judge_text, re.IGNORECASE)
        if fm:
            try:
                fundability = max(1, min(10, int(fm.group(1))))
            except ValueError:
                pass

        # Technical difficulty
        technical = 5
        tm = re.search(r"Technical Difficulty:\s*(\d+)\s*/\s*10", judge_text, re.IGNORECASE)
        if tm:
            try:
                technical = max(1, min(10, int(tm.group(1))))
            except ValueError:
                pass

        # Market size
        market_size = "Unknown"
        ms_match = re.search(
            r"Market Size[:\s]+(\w+)", judge_text, re.IGNORECASE
        )
        if ms_match:
            raw = ms_match.group(1).capitalize()
            if raw in ("Small", "Medium", "Large"):
                market_size = raw
            else:
                market_size = "Unknown"

        # Next steps — numbered list after "Next Steps"
        next_steps: list[str] = []
        in_steps = False
        for line in judge_text.splitlines():
            if "Next Steps" in line:
                in_steps = True
                continue
            if in_steps:
                stripped = line.strip()
                step_match = re.match(r"^\d+\.\s+(.+)", stripped)
                if step_match:
                    next_steps.append(step_match.group(1).strip())
                elif stripped.startswith("###") and next_steps:
                    break

        # Refined idea
        refined_idea = ""
        ri_match = re.search(
            r"###\s*The Refined Idea\s*\n(.*?)(?=###|\Z)",
            judge_text,
            re.DOTALL | re.IGNORECASE,
        )
        if ri_match:
            refined_idea = ri_match.group(1).strip()
        if not refined_idea:
            refined_idea = "See full verdict for the refined version of your idea."

        # Biggest risk (The One Thing section)
        biggest_risk = ""
        br_match = re.search(
            r"###\s*The One Thing.+?\n(.*?)(?=###|\Z)",
            judge_text,
            re.DOTALL | re.IGNORECASE,
        )
        if br_match:
            biggest_risk = br_match.group(1).strip()
        if not biggest_risk:
            biggest_risk = "Validate market demand before writing a single line of code."

        # Biggest opportunity (synthesized from verdict reasoning)
        biggest_opportunity = ""
        bo_match = re.search(
            r"###\s*Who Won The Debate\s*\n(.*?)(?=###|\Z)",
            judge_text,
            re.DOTALL | re.IGNORECASE,
        )
        if bo_match:
            biggest_opportunity = bo_match.group(1).strip()
        if not biggest_opportunity:
            biggest_opportunity = "Unique positioning if executed correctly."

        # Verdict reasoning (from the Verdict section)
        verdict_reasoning = ""
        vr_match = re.search(
            r"###\s*Verdict:.+?\n(.*?)(?=###|\Z)",
            judge_text,
            re.DOTALL | re.IGNORECASE,
        )
        if vr_match:
            verdict_reasoning = vr_match.group(1).strip()
        if not verdict_reasoning:
            verdict_reasoning = judge_text[:300].strip()

        return DebateVerdict(
            recommendation=recommendation,
            verdict_reasoning=verdict_reasoning,
            refined_idea=refined_idea,
            biggest_risk=biggest_risk,
            biggest_opportunity=biggest_opportunity,
            next_steps=next_steps if next_steps else ["Validate the core assumption", "Talk to 10 potential users", "Build a landing page"],
            fundability_score=fundability,
            technical_difficulty=technical,
            market_size_estimate=market_size,
        )

    # -----------------------------------------------------------------------
    # Display formatter
    # -----------------------------------------------------------------------

    def format_debate_for_display(self, result: DebateResult) -> str:
        """Format the complete debate as beautiful markdown for MCP response."""
        lines = [
            f"# 🎭 GitRoast Debate Arena",
            f"",
            f"> **Idea:** {result.original_idea}",
            f"> **Duration:** {result.debate_duration_seconds:.1f}s | **Timestamp:** {result.timestamp[:10]}",
            f"",
            f"---",
            f"",
            f"## 🟢 Agent 1: The Believer",
            f"",
            result.believer_argument.argument,
            f"",
            f"---",
            f"",
            f"## 🔴 Agent 2: The Destroyer",
            f"",
            result.destroyer_argument.argument,
            f"",
            f"---",
            f"",
            f"## ⚖️ Agent 3: The Judge",
            f"",
            f"### Verdict: **{result.verdict.recommendation}**",
            f"",
            result.verdict.verdict_reasoning,
            f"",
            f"### The Refined Idea",
            f"",
            result.verdict.refined_idea,
            f"",
            f"### The One Thing That Will Make Or Break This",
            f"",
            result.verdict.biggest_risk,
            f"",
            f"### Next Steps",
            f"",
        ]

        for i, step in enumerate(result.verdict.next_steps, 1):
            lines.append(f"{i}. {step}")

        lines += [
            f"",
            f"---",
            f"",
            f"## 📊 Scores",
            f"",
            f"| Metric | Score |",
            f"|--------|-------|",
            f"| 💰 Fundability | {result.verdict.fundability_score}/10 |",
            f"| 🔧 Technical Difficulty | {result.verdict.technical_difficulty}/10 |",
            f"| 📈 Market Size | {result.verdict.market_size_estimate} |",
            f"| ✅ Recommendation | **{result.verdict.recommendation}** |",
            f"",
            f"---",
            f"",
            f"*Run `scaffold_project` to turn this into a real starter project.*",
        ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import os

    from dotenv import load_dotenv
    from groq import Groq

    load_dotenv()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    debater = IdeaDebater(client)
    result = asyncio.run(
        debater.run_debate(
            idea="A VS Code extension that roasts your code using AI",
            context="Solo developer, 6 months experience",
            personality="yc_founder",
        )
    )
    print(debater.format_debate_for_display(result))
