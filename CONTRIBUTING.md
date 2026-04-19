# Contributing to GitRoast

Thank you for wanting to make GitRoast better. This is an open, community-driven project and contributions are welcome at every level — from fixing a typo to adding a whole new tool.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Good First Issues](#good-first-issues)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Commit Style](#commit-style)
- [Pull Request Process](#pull-request-process)

---

## Code of Conduct

Be direct. Be honest. Don't be mean. This project roasts code, not people.

---

## Getting Started

```bash
git clone https://github.com/yourusername/gitroast.git
cd gitroast

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Fill in GROQ_API_KEY and GITHUB_TOKEN in .env
```

---

## How to Contribute

1. **Fork** the repo and create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/describe-the-bug
   ```

2. **Make your changes.** Keep them focused — one feature or fix per PR.

3. **Write or update tests.** All tests live in `tests/`. No API calls — use mocks.

4. **Run the full test suite:**
   ```bash
   pytest tests/ -v
   # All 75 tests must pass
   ```

5. **Commit using the style below**, then open a PR.

---

## Good First Issues

These are well-scoped, self-contained improvements anyone can make:

### Python (`mcp_server/`)

| Task | File | Difficulty |
|------|------|------------|
| Add more bad commit message patterns | `tools/github_scraper.py` → `BAD_MESSAGES` | ⭐ Beginner |
| Add a new roast ammunition condition | `tools/github_scraper.py` → `_build_roast_ammunition` | ⭐ Beginner |
| Improve README quality scoring | `tools/github_scraper.py` → `_score_readme` | ⭐⭐ Intermediate |
| Add a new personality mode (e.g. `hacker`) | `personality/engine.py` | ⭐⭐ Intermediate |
| Add more weakness detection heuristics | `tools/competitor_researcher.py` → `_detect_weaknesses` | ⭐ Beginner |
| Add new differentiation angle detectors | `tools/competitor_researcher.py` → `_find_differentiation_angles` | ⭐⭐ Intermediate |
| Add tests for `competitor_researcher.py` edge cases | `tests/test_competitor_researcher.py` | ⭐ Beginner |
| Support analyzing private repos (with proper token scope) | `tools/code_analyzer.py` | ⭐⭐⭐ Advanced |

### TypeScript (`vscode_extension/`)

| Task | File | Difficulty |
|------|------|------------|
| Add a "Research Competitors" button to the sidebar | `src/sidebar.ts` | ⭐⭐ Intermediate |
| Add a "Stress Test Idea" button to the sidebar | `src/sidebar.ts` | ⭐⭐ Intermediate |
| Persist username across sidebar sessions | `src/sidebar.ts` | ⭐ Beginner |
| Add a status bar tooltip with last-run details | `src/extension.ts` | ⭐ Beginner |

---

## Development Setup

### Python Server

```bash
# Test the GitHub scraper standalone
python -m mcp_server.tools.github_scraper

# Test the competitor researcher standalone
python -m mcp_server.tools.competitor_researcher

# Test the idea debater standalone
python -m mcp_server.tools.idea_debater

# Run the MCP server locally
python -m mcp_server.server
```

### VS Code Extension

```bash
cd vscode_extension
npm install

# Compile TypeScript
npm run compile

# Run in development mode
# Press F5 in VS Code with vscode_extension/ as workspace root
```

---

## Running Tests

```bash
# All tests — must be 100% green before opening a PR
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=mcp_server --cov-report=term-missing

# Single file
pytest tests/test_competitor_researcher.py -v
```

**Rules for tests:**
- No real API calls — use `unittest.mock.MagicMock` and `AsyncMock`
- Tests must be deterministic (no `time.sleep`, no random seeds)
- One assertion per test where possible
- Name tests descriptively: `test_abandoned_repo_flagged`, not `test_1`

---

## Commit Style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scraper): add support for organization repos
fix(competitor): handle rate limit on second search query
test(debater): add test for short idea rejection
docs(readme): update quick start for Windows users
refactor(personality): extract signoff to separate method
chore: bump dependencies
```

**Types:** `feat` · `fix` · `test` · `docs` · `refactor` · `chore` · `perf`

**Scopes:** `scraper` · `analyzer` · `debater` · `scaffolder` · `competitor` · `personality` · `orchestrator` · `server` · `extension` · `readme` · `ci`

Do NOT commit:
- `.env` files (your real API keys)
- `__pycache__/` or `.pytest_cache/`
- `node_modules/`
- `out/` (compiled extension)

---

## Pull Request Process

1. **Title:** Use the same format as your commit message: `feat(scope): description`

2. **Description must include:**
   - What you changed and why
   - How to test it manually
   - Screenshot or output sample if it changes visible behavior

3. **Checklist before submitting:**
   - [ ] `pytest tests/ -v` — all tests pass
   - [ ] No `.env`, secrets, or debug-only code committed
   - [ ] TypeScript compiles: `cd vscode_extension && npm run compile`
   - [ ] New functionality has at least one test

4. **Review:** PRs are reviewed within 48 hours. Feedback will be direct and specific.

---

## Project Architecture (Quick Reference)

```
MCP Server (Python)
├── server.py              ← Tool registration + request routing
├── orchestrator.py        ← Session cache + conversation history
├── tools/
│   ├── github_scraper.py  ← GitHub API → profile data + roast ammo
│   ├── code_analyzer.py   ← pylint + radon + AST → quality scores
│   ├── idea_debater.py    ← 3-agent debate: Believer/Destroyer/Judge
│   ├── scaffolder.py      ← Project scaffolding + GitHub repo creation
│   └── competitor_researcher.py  ← GitHub Search + Groq synthesis
└── personality/engine.py  ← 5 persona wrappers

VS Code Extension (TypeScript)
├── extension.ts           ← Activation + commands + status bar
├── sidebar.ts             ← WebView sidebar provider
├── chat_panel.ts          ← Persistent chat WebView
└── inline_comments.ts     ← Code decoration + Problems panel
```

---

*GitRoast roasts code because code can take it.*
