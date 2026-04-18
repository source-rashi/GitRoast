"""Tests for GitRoast Project Scaffolder (Phase 3)"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from mcp_server.tools.scaffolder import (
    ProjectScaffolder,
    ScaffoldFile,
    ScaffoldResult,
    TechStackChoice,
    WeeklyMilestone,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SCAFFOLD_PLAN_RESPONSE = """## PROJECT NAME
my-cool-app

## DESCRIPTION
A cool app that does cool things for cool people.

## TECH STACK
### Primary Language
Python — versatile and excellent for rapid prototyping
Alternatives: JavaScript, Go

### Framework
FastAPI — fast, modern, async Python framework
Alternatives: Flask, Django

### Database (if needed)
SQLite — simple, zero-config, perfect for MVP
 
### Key Libraries
- httpx: async HTTP client
- pydantic: data validation
- rich: beautiful terminal output

### Free Hosting Option
Railway — easy Python deployment with generous free tier

## FOLDER STRUCTURE
my-cool-app/
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
- Set up project structure
- Write the main data model
- Connect to the API
Deliverable: Basic CLI that fetches and displays data

### Week 2: Core Features
Goals:
- Build the main feature
- Add caching layer
- Write unit tests
Deliverable: Feature-complete alpha with 80% test coverage

### Week 3: Polish & Testing
Goals:
- Improve error handling
- Add integration tests
- Polish the output format
Deliverable: Beta ready for external testing

### Week 4: Launch Prep
Goals:
- Write full documentation
- Deploy to Railway
- Post on Hacker News
Deliverable: Public MVP live at cool-app.railway.app"""


CORE_FILES_RESPONSE = """===FILE: src/main.py===
DESCRIPTION: Main entry point for the application
CONTENT:
#!/usr/bin/env python3
\"\"\"Main entry point.\"\"\"


def main():
    print("Hello from my-cool-app!")


if __name__ == "__main__":
    main()
===END FILE===

===FILE: requirements.txt===
DESCRIPTION: Python dependencies with pinned versions
CONTENT:
fastapi==0.109.0
httpx==0.26.0
pydantic==2.5.3
rich==13.7.0
uvicorn==0.27.0
===END FILE===

===FILE: .gitignore===
DESCRIPTION: Git ignore file for Python projects
CONTENT:
__pycache__/
*.pyc
.env
.venv/
dist/
build/
*.egg-info/
===END FILE==="""


def make_mock_groq_scaffolder(plan_response: str = SCAFFOLD_PLAN_RESPONSE, files_response: str = CORE_FILES_RESPONSE):
    """Return a Groq mock for scaffolder tests."""
    call_count = 0
    responses = [plan_response, files_response, "# my-cool-app\n\nA cool app.\n"]

    client = MagicMock()

    def side_effect(*args, **kwargs):
        nonlocal call_count
        mock = MagicMock()
        mock.choices[0].message.content = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return mock

    client.chat.completions.create.side_effect = side_effect
    return client


def make_mock_scaffold_result() -> ScaffoldResult:
    """Create a mock ScaffoldResult with folder structure data."""
    return ScaffoldResult(
        idea="A note-taking app",
        project_name="my-notes-app",
        project_description="A fast note-taking app.",
        tech_stack=[
            TechStackChoice(
                name="Python",
                reasoning="Rapid prototyping",
                alternatives=["JavaScript"],
            )
        ],
        folder_structure="my-notes-app/\n├── src/\n│   └── main.py\n└── README.md",
        files=[
            ScaffoldFile(path="src/main.py", content='print("hello")', description="Main entry"),
            ScaffoldFile(path="requirements.txt", content="pydantic==2.5.3\n", description="Deps"),
        ],
        roadmap=[
            WeeklyMilestone(week=1, title="Foundation", goals=["Set up env"], deliverable="Running app"),
            WeeklyMilestone(week=2, title="Core", goals=["Build features"], deliverable="Alpha"),
            WeeklyMilestone(week=3, title="Polish", goals=["Fix bugs"], deliverable="Beta"),
            WeeklyMilestone(week=4, title="Launch", goals=["Deploy"], deliverable="MVP live"),
        ],
        readme_content="# my-notes-app\n\nA note-taking app.\n",
        env_example_content="# Environment variables\n",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_project_name():
    """PROJECT NAME section should be extracted and slugified."""
    response = "## PROJECT NAME\nmy-cool-app\n## DESCRIPTION\nA cool app"
    scaffolder = ProjectScaffolder(MagicMock())
    parsed = scaffolder._parse_scaffold_response(response)
    assert parsed["project_name"] == "my-cool-app"


def test_parse_description():
    """DESCRIPTION section should be extracted."""
    response = "## PROJECT NAME\nmy-cool-app\n## DESCRIPTION\nA cool app that does things"
    scaffolder = ProjectScaffolder(MagicMock())
    parsed = scaffolder._parse_scaffold_response(response)
    assert "cool app" in parsed.get("description", "")


@pytest.mark.asyncio
async def test_scaffold_result_has_files():
    """Scaffolding should return at least one generated file."""
    client = make_mock_groq_scaffolder()
    scaffolder = ProjectScaffolder(client)
    result = await scaffolder.scaffold("A note-taking app with AI summaries")
    assert len(result.files) > 0
    assert all(isinstance(f, ScaffoldFile) for f in result.files)


@pytest.mark.asyncio
async def test_scaffold_result_has_roadmap():
    """Scaffolding should return a 4-week roadmap."""
    client = make_mock_groq_scaffolder()
    scaffolder = ProjectScaffolder(client)
    result = await scaffolder.scaffold("A todo app with reminders")
    assert len(result.roadmap) == 4
    assert result.roadmap[0].week == 1
    assert result.roadmap[3].week == 4


@pytest.mark.asyncio
async def test_create_repo_returns_none_without_token():
    """create_github_repo should return None gracefully when no token is set."""
    scaffolder_no_token = ProjectScaffolder(MagicMock(), github_token=None)
    url = await scaffolder_no_token.create_github_repo(
        "test-project",
        "A test project",
        [],
    )
    assert url is None


def test_format_scaffold_contains_folder_structure():
    """format_scaffold_for_display must include the ASCII tree characters."""
    scaffolder = ProjectScaffolder(MagicMock())
    result = make_mock_scaffold_result()
    formatted = scaffolder.format_scaffold_for_display(result)
    assert "├──" in formatted or "└──" in formatted
    assert result.project_name in formatted


def test_parse_core_files():
    """_parse_core_files should extract ScaffoldFile objects from the expected format."""
    scaffolder = ProjectScaffolder(MagicMock())
    files = scaffolder._parse_core_files(CORE_FILES_RESPONSE)
    assert len(files) == 3
    paths = {f.path for f in files}
    assert "src/main.py" in paths
    assert "requirements.txt" in paths
    assert ".gitignore" in paths


def test_parse_roadmap_weeks():
    """Full scaffold plan response should produce a 4-week roadmap."""
    scaffolder = ProjectScaffolder(MagicMock())
    parsed = scaffolder._parse_scaffold_response(SCAFFOLD_PLAN_RESPONSE)
    roadmap = parsed.get("roadmap", [])
    assert len(roadmap) == 4
    assert roadmap[0].title == "Foundation"
    assert roadmap[3].title == "Launch Prep"
