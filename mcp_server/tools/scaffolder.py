"""
GitRoast — Project Scaffolder
================================
Turns a validated idea into a complete starter project structure.

What it generates:
- Full folder structure with all files listed
- Tech stack recommendation with reasoning
- Week-by-week 4-week roadmap
- Core starter files with actual code
- README.md draft
- .env.example
- requirements.txt or package.json
- Optionally: creates actual GitHub repo via API (if token has repo scope)

Uses Groq (free) to generate all content.
"""

import re
from datetime import datetime, timezone
from typing import Optional

from github import Github
from loguru import logger
from pydantic import BaseModel
from rich.console import Console


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TechStackChoice(BaseModel):
    """A single technology recommendation with reasoning."""
    name: str
    reasoning: str
    alternatives: list[str]
    free_tier_available: bool = True


class ScaffoldFile(BaseModel):
    """A generated project file with its content."""
    path: str           # e.g. "src/main.py"
    content: str        # actual file content
    description: str    # one line about this file


class WeeklyMilestone(BaseModel):
    """A single week in the 4-week MVP roadmap."""
    week: int
    title: str
    goals: list[str]    # 3-5 concrete goals for this week
    deliverable: str    # what exists at end of this week


class ScaffoldResult(BaseModel):
    """Complete output of the project scaffolding process."""
    idea: str
    project_name: str           # slug like "my-cool-project"
    project_description: str
    tech_stack: list[TechStackChoice]
    folder_structure: str       # ASCII tree as string
    files: list[ScaffoldFile]
    roadmap: list[WeeklyMilestone]  # 4 weeks
    readme_content: str
    env_example_content: str
    github_repo_url: Optional[str] = None
    timestamp: str


# ---------------------------------------------------------------------------
# System prompts (stored as module-level constants for clarity)
# ---------------------------------------------------------------------------

SCAFFOLD_SYSTEM_PROMPT = """You are GitRoast's Project Scaffolder. You turn validated ideas into real starter projects.

Given an idea (and optionally the debate result that validated it), generate a complete project scaffold.

Respond in this EXACT format — do not deviate:

## PROJECT NAME
[slug-style name, lowercase, hyphens, no spaces, e.g. "smart-todo-ai"]

## DESCRIPTION
[One sentence describing what this project does]

## TECH STACK
### Primary Language
[Language name] — [reason it's the right choice for this idea]
Alternatives: [2 alternatives]

### Framework
[Framework name] — [reason]
Alternatives: [2 alternatives]

### Database (if needed)
[DB name or "None needed"] — [reason]

### Key Libraries
- [library 1]: [what it does]
- [library 2]: [what it does]
- [library 3]: [what it does]

### Free Hosting Option
[Vercel / Railway / Render / Fly.io / GitHub Pages / None] — [why it fits]

## FOLDER STRUCTURE
[ASCII tree of the complete project structure, every file listed]
Example format:
my-project/
├── src/
│   ├── main.py
│   └── utils.py
├── tests/
│   └── test_main.py
├── .env.example
├── requirements.txt
└── README.md

## 4-WEEK ROADMAP

### Week 1: Foundation
Goals:
- [goal 1]
- [goal 2]
- [goal 3]
Deliverable: [what exists at end of week 1]

### Week 2: Core Features
Goals:
- [goal 1]
- [goal 2]
- [goal 3]
Deliverable: [what exists at end of week 2]

### Week 3: Polish & Testing
Goals:
- [goal 1]
- [goal 2]
- [goal 3]
Deliverable: [what exists at end of week 3]

### Week 4: Launch Prep
Goals:
- [goal 1]
- [goal 2]
- [goal 3]
Deliverable: [what exists at end of week 4 — this is your MVP]

Rules:
- Only recommend FREE tools and services
- Tech stack must match the idea's actual needs — don't over-engineer
- The folder structure must be complete — every file that will ever exist
- Week 1 goals must be achievable in a weekend
- Week 4 deliverable must be a shippable MVP"""


CORE_FILES_PROMPT = """Based on this project plan, generate the content for these starter files.
For EACH file, provide:
1. The complete file content (real, runnable code — not pseudocode)
2. A one-line description

Generate these files in order:
1. The main entry point file (e.g. main.py, index.js, app.py)
2. A config/settings file (.env.example or config.py)
3. requirements.txt or package.json with real, specific version pins
4. A basic README.md outline (just structure — the full README comes separately)
5. A .gitignore appropriate for the tech stack

Format each file EXACTLY like this:
===FILE: path/to/file.py===
DESCRIPTION: One sentence about what this file does
CONTENT:
[complete file content here]
===END FILE===

Rules:
- All code must be real and runnable
- Use only free, open-source libraries
- Include helpful comments in the code
- The main file must have a working __main__ block or equivalent
- requirements.txt must have pinned versions"""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ProjectScaffolder:
    """Generates complete starter projects from validated ideas."""

    SCAFFOLD_SYSTEM_PROMPT = SCAFFOLD_SYSTEM_PROMPT
    CORE_FILES_PROMPT = CORE_FILES_PROMPT

    def __init__(self, groq_client, github_token: Optional[str] = None):
        self.groq_client = groq_client
        self.github_token = github_token
        self.github = Github(github_token) if github_token else None
        self.console = Console(stderr=True)
        logger.info("ProjectScaffolder initialized.")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def scaffold(
        self,
        idea: str,
        debate_result: Optional[str] = None,
        personality: str = "yc_founder",
    ) -> ScaffoldResult:
        """Turn an idea into a complete starter project."""
        self.console.print(
            "\n[bold cyan]🏗️ GitRoast Scaffolder is designing your project...[/bold cyan]"
        )

        # Step 1: Generate the plan
        plan_text = await self._generate_scaffold_plan(idea, debate_result)

        # Step 2: Parse plan into structured data
        parsed = self._parse_scaffold_response(plan_text)

        # Step 3: Generate actual starter files
        files = await self._generate_core_files(plan_text, idea)

        # Step 4: Generate full README
        readme = await self._generate_readme(idea, plan_text, parsed.get("project_name", "my-project"))

        # Extract .env.example content from files if present
        env_content = ""
        for f in files:
            if ".env.example" in f.path or f.path.endswith(".env"):
                env_content = f.content
                break
        if not env_content:
            env_content = "# Add your environment variables here\n"

        return ScaffoldResult(
            idea=idea,
            project_name=parsed.get("project_name", "my-project"),
            project_description=parsed.get("description", idea[:100]),
            tech_stack=parsed.get("tech_stack", []),
            folder_structure=parsed.get("folder_structure", ""),
            files=files,
            roadmap=parsed.get("roadmap", []),
            readme_content=readme,
            env_example_content=env_content,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # -----------------------------------------------------------------------
    # Groq calls
    # -----------------------------------------------------------------------

    async def _generate_scaffold_plan(self, idea: str, debate_result: Optional[str]) -> str:
        """Call Groq to generate the complete scaffold plan."""
        user_message = f"Generate a complete project scaffold for this idea:\n\n{idea}"
        if debate_result:
            user_message += f"\n\nThe idea was validated in a debate. Here's the verdict:\n{debate_result[:1000]}"

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.SCAFFOLD_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=1500,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(f"Groq scaffold plan failed: {exc}")
            return self._fallback_plan(idea)

    async def _generate_core_files(self, plan: str, idea: str) -> list[ScaffoldFile]:
        """Call Groq to generate actual starter code files."""
        user_message = (
            f"Project plan:\n{plan[:2000]}\n\n"
            f"Original idea: {idea}\n\n"
            "Now generate the starter files as specified."
        )

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.CORE_FILES_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=2000,
                temperature=0.6,
            )
            raw = response.choices[0].message.content or ""
            return self._parse_core_files(raw)
        except Exception as exc:
            logger.warning(f"Groq core files failed: {exc}")
            return self._fallback_files(idea)

    async def _generate_readme(self, idea: str, plan: str, project_name: str) -> str:
        """Generate a proper project README."""
        system = (
            "You are a technical writer. Generate a professional README.md for a software project. "
            "Include: title with emoji, description, features list, installation steps, "
            "usage examples, contributing section, and MIT license footer. "
            "Use markdown properly. Keep it under 400 words."
        )
        user_message = (
            f"Project name: {project_name}\n"
            f"Idea: {idea}\n"
            f"Plan summary:\n{plan[:800]}"
        )

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=700,
                temperature=0.7,
            )
            return response.choices[0].message.content or f"# {project_name}\n\n{idea}\n"
        except Exception as exc:
            logger.warning(f"Groq README generation failed: {exc}")
            return f"# {project_name}\n\n{idea}\n\n## Installation\n\n```bash\npip install -r requirements.txt\n```\n"

    # -----------------------------------------------------------------------
    # Parsers
    # -----------------------------------------------------------------------

    def _parse_scaffold_response(self, response: str) -> dict:
        """Extract structured data from the Groq scaffold response."""
        result: dict = {}

        # Project name
        pn_match = re.search(r"## PROJECT NAME\s*\n([^\n]+)", response, re.IGNORECASE)
        if pn_match:
            raw_name = pn_match.group(1).strip()
            # Sanitize slug
            result["project_name"] = re.sub(r"[^a-z0-9\-]", "-", raw_name.lower()).strip("-")
        else:
            result["project_name"] = "my-project"

        # Description
        desc_match = re.search(r"## DESCRIPTION\s*\n([^\n]+)", response, re.IGNORECASE)
        if desc_match:
            result["description"] = desc_match.group(1).strip()
        else:
            result["description"] = ""

        # Folder structure
        fs_match = re.search(
            r"## FOLDER STRUCTURE\s*\n(.*?)(?=##|\Z)",
            response,
            re.DOTALL | re.IGNORECASE,
        )
        if fs_match:
            result["folder_structure"] = fs_match.group(1).strip()
        else:
            result["folder_structure"] = ""

        # Tech stack — extract language and framework as TechStackChoice objects
        tech_stack: list[TechStackChoice] = []

        lang_match = re.search(
            r"### Primary Language\s*\n([^\n]+)(?:\nAlternatives:\s*([^\n]+))?",
            response, re.IGNORECASE
        )
        if lang_match:
            parts = lang_match.group(1).split("—", 1)
            alts = [a.strip() for a in (lang_match.group(2) or "").split(",") if a.strip()]
            tech_stack.append(TechStackChoice(
                name=parts[0].strip(),
                reasoning=parts[1].strip() if len(parts) > 1 else "",
                alternatives=alts,
            ))

        fw_match = re.search(
            r"### Framework\s*\n([^\n]+)(?:\nAlternatives:\s*([^\n]+))?",
            response, re.IGNORECASE
        )
        if fw_match:
            parts = fw_match.group(1).split("—", 1)
            alts = [a.strip() for a in (fw_match.group(2) or "").split(",") if a.strip()]
            tech_stack.append(TechStackChoice(
                name=parts[0].strip(),
                reasoning=parts[1].strip() if len(parts) > 1 else "",
                alternatives=alts,
            ))

        result["tech_stack"] = tech_stack

        # Roadmap — 4 weeks
        roadmap: list[WeeklyMilestone] = []
        week_blocks = re.findall(
            r"### Week (\d+): ([^\n]+)\nGoals:\n(.*?)Deliverable: ([^\n]+)",
            response,
            re.DOTALL | re.IGNORECASE,
        )
        for match in week_blocks:
            week_num = int(match[0])
            title = match[1].strip()
            goals_raw = match[2]
            deliverable = match[3].strip()
            goals = [
                line.strip()[2:].strip()
                for line in goals_raw.splitlines()
                if line.strip().startswith("- ")
            ]
            roadmap.append(WeeklyMilestone(
                week=week_num,
                title=title,
                goals=goals,
                deliverable=deliverable,
            ))

        # If parsing failed, create a sensible default 4-week roadmap
        if len(roadmap) < 4:
            roadmap = self._default_roadmap()

        result["roadmap"] = roadmap
        return result

    def _parse_core_files(self, raw: str) -> list[ScaffoldFile]:
        """Extract ScaffoldFile objects from the ===FILE: ... ===END FILE=== blocks."""
        files: list[ScaffoldFile] = []
        pattern = re.compile(
            r"===FILE:\s*(.+?)===\s*\nDESCRIPTION:\s*(.+?)\nCONTENT:\s*\n(.*?)===END FILE===",
            re.DOTALL,
        )
        for match in pattern.finditer(raw):
            path = match.group(1).strip()
            description = match.group(2).strip()
            content = match.group(3).rstrip()
            files.append(ScaffoldFile(path=path, content=content, description=description))

        return files if files else self._fallback_files("")

    # -----------------------------------------------------------------------
    # GitHub repo creation
    # -----------------------------------------------------------------------

    async def create_github_repo(
        self,
        project_name: str,
        description: str,
        files: list[ScaffoldFile],
    ) -> Optional[str]:
        """
        Create an actual GitHub repo and push the scaffold files.
        Requires 'repo' scope on GitHub PAT.
        """
        if self.github is None:
            logger.info("No GitHub token provided — skipping repo creation.")
            return None

        try:
            user = self.github.get_user()
            repo = user.create_repo(
                name=project_name,
                description=description,
                private=False,
                auto_init=False,
            )
            logger.info(f"Created GitHub repo: {repo.html_url}")

            for scaffold_file in files:
                try:
                    repo.create_file(
                        path=scaffold_file.path,
                        message=f"chore: scaffold {scaffold_file.path}",
                        content=scaffold_file.content,
                    )
                except Exception as file_exc:
                    logger.warning(f"Could not push {scaffold_file.path}: {file_exc}")

            return repo.html_url
        except Exception as exc:
            logger.warning(f"GitHub repo creation failed (non-fatal): {exc}")
            return None

    # -----------------------------------------------------------------------
    # Display formatter
    # -----------------------------------------------------------------------

    def format_scaffold_for_display(self, result: ScaffoldResult) -> str:
        """Format the scaffold result as beautiful markdown."""
        lines = [
            f"# 🏗️ {result.project_name}",
            f"",
            f"> {result.project_description}",
            f"",
        ]

        if result.github_repo_url:
            lines += [f"**GitHub Repo:** {result.github_repo_url}", f""]

        # Tech stack table
        if result.tech_stack:
            lines += [
                f"## 🛠️ Tech Stack",
                f"",
                f"| Technology | Reasoning | Alternatives |",
                f"|------------|-----------|--------------|",
            ]
            for tech in result.tech_stack:
                alts = ", ".join(tech.alternatives) if tech.alternatives else "—"
                lines.append(f"| **{tech.name}** | {tech.reasoning} | {alts} |")
            lines.append("")

        # Folder structure
        if result.folder_structure:
            lines += [
                f"## 📁 Folder Structure",
                f"",
                f"```",
                result.folder_structure,
                f"```",
                f"",
            ]

        # Roadmap table
        if result.roadmap:
            lines += [
                f"## 🗓️ 4-Week Roadmap",
                f"",
                f"| Week | Theme | Deliverable |",
                f"|------|-------|-------------|",
            ]
            for m in result.roadmap:
                lines.append(f"| Week {m.week} | **{m.title}** | {m.deliverable} |")
            lines.append("")

        # First file content as preview
        if result.files:
            first = result.files[0]
            ext = first.path.rsplit(".", 1)[-1] if "." in first.path else "text"
            lines += [
                f"## 📄 Starter Code Preview — `{first.path}`",
                f"",
                f"*{first.description}*",
                f"",
                f"```{ext}",
                first.content[:1000] + ("..." if len(first.content) > 1000 else ""),
                f"```",
                f"",
            ]

        lines += [
            f"---",
            f"",
            f"*{len(result.files)} files generated | Run `create_github_repo` to push this to GitHub.*",
        ]

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Fallback helpers (never crash)
    # -----------------------------------------------------------------------

    def _fallback_plan(self, idea: str) -> str:
        """Return a minimal plan if Groq fails."""
        slug = re.sub(r"[^a-z0-9]", "-", idea[:30].lower()).strip("-")
        return (
            f"## PROJECT NAME\n{slug}\n\n"
            f"## DESCRIPTION\n{idea}\n\n"
            f"## TECH STACK\n### Primary Language\nPython — versatile and beginner-friendly\n"
            f"Alternatives: JavaScript, Go\n\n"
            f"## FOLDER STRUCTURE\n{slug}/\n├── main.py\n├── requirements.txt\n└── README.md\n\n"
            f"## 4-WEEK ROADMAP\n"
            f"### Week 1: Foundation\nGoals:\n- Set up project structure\n- Install dependencies\n"
            f"- Write first prototype\nDeliverable: Working prototype\n\n"
            f"### Week 2: Core Features\nGoals:\n- Implement main feature\n- Add basic tests\n"
            f"- Improve error handling\nDeliverable: Feature-complete alpha\n\n"
            f"### Week 3: Polish & Testing\nGoals:\n- Add tests\n- Improve UX\n"
            f"- Fix bugs\nDeliverable: Beta release\n\n"
            f"### Week 4: Launch Prep\nGoals:\n- Write documentation\n- Deploy\n"
            f"- Announce\nDeliverable: Shipped MVP\n"
        )

    def _fallback_files(self, idea: str) -> list[ScaffoldFile]:
        """Return minimal starter files if Groq fails."""
        return [
            ScaffoldFile(
                path="main.py",
                content=(
                    "#!/usr/bin/env python3\n"
                    '"""Main entry point."""\n\n'
                    "def main():\n"
                    f'    print("Starting: {idea[:50]}")\n\n\n'
                    'if __name__ == "__main__":\n'
                    "    main()\n"
                ),
                description="Main entry point",
            ),
            ScaffoldFile(
                path="requirements.txt",
                content="# Add your dependencies here\n",
                description="Python dependencies",
            ),
            ScaffoldFile(
                path=".gitignore",
                content="__pycache__/\n*.pyc\n.env\n.venv/\ndist/\nbuild/\n*.egg-info/\n",
                description="Git ignore file",
            ),
        ]

    def _default_roadmap(self) -> list[WeeklyMilestone]:
        """Return a generic 4-week roadmap."""
        return [
            WeeklyMilestone(
                week=1, title="Foundation",
                goals=["Set up dev environment", "Create project structure", "Build first prototype"],
                deliverable="Working prototype running locally",
            ),
            WeeklyMilestone(
                week=2, title="Core Features",
                goals=["Implement main feature", "Add error handling", "Write basic tests"],
                deliverable="Feature-complete alpha version",
            ),
            WeeklyMilestone(
                week=3, title="Polish & Testing",
                goals=["Improve UX", "Fix bugs from alpha", "Add integration tests"],
                deliverable="Beta ready for feedback",
            ),
            WeeklyMilestone(
                week=4, title="Launch Prep",
                goals=["Write documentation", "Deploy to free hosting", "Announce on social"],
                deliverable="Shipped MVP — real users can use it",
            ),
        ]
