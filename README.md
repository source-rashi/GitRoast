<div align="center">

```
 ██████╗ ██╗████████╗██████╗  ██████╗  █████╗ ███████╗████████╗
██╔════╝ ██║╚══██╔══╝██╔══██╗██╔═══██╗██╔══██╗██╔════╝╚══██╔══╝
██║  ███╗██║   ██║   ██████╔╝██║   ██║███████║███████╗   ██║   
██║   ██║██║   ██║   ██╔══██╗██║   ██║██╔══██║╚════██║   ██║   
╚██████╔╝██║   ██║   ██║  ██║╚██████╔╝██║  ██║███████║   ██║   
 ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝   ╚═╝  
```

### 🔥 AI-Powered Developer Intelligence via MCP

**The most brutally honest, data-driven developer roaster on the internet.**  
Real GitHub data. Real roasts. Genuine feedback. Zero BS.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.0-orange?style=flat-square)](https://modelcontextprotocol.io)
[![Groq](https://img.shields.io/badge/LLM-Groq%20%28Free%29-green?style=flat-square)](https://console.groq.com)
[![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)

</div>

---

## 🤔 What Is GitRoast?

GitRoast is an **MCP (Model Context Protocol) server** that connects to any compatible AI agent (Claude Desktop, Cursor, Windsurf, etc.) and gives it superpowers to analyze real GitHub developer profiles.

It doesn't lie. It doesn't guess. It scrapes **your actual GitHub data** — commits, PRs, issues, READMEs, languages — and uses a free Groq LLM to turn it into:

- 🔥 **A personalized roast** grounded in specific facts ("17 commits titled 'fix'. Fix WHAT?")
- 💪 **Genuine praise** where it's actually earned
- 📋 **Actionable advice** tied to patterns it found in your actual repos

Five personality modes: **Comedian**, **YC Co-Founder**, **Senior Dev**, **Zen Mentor**, **Anonymous Stranger**.

> Built with: Python 3.11+, MCP SDK, PyGitHub, Groq (llama3-70b-8192), Pydantic v2, Rich.  
> **100% free APIs. No credit card required anywhere.**

---

## ✨ Features

| Feature | Status | Description |
|---|---|---|
| 🔍 **Deep GitHub Scraping** | ✅ Live | Repos, commits, PRs, issues, READMEs, languages |
| 🔥 **AI Roast Generation** | ✅ Live | Groq-powered, personality-aware, data-grounded. Now with **real static analysis** — pylint scores, cyclomatic complexity, hardcoded secret detection, and more. Every roast is backed by actual file-level findings. |
| 💬 **Multi-turn Follow-ups** | ✅ Live | Ask questions without re-fetching GitHub |
| 🎭 **5 Personality Modes** | ✅ Live | Comedian, YC, Senior Dev, Zen, Stranger |
| 🗂️ **Session Caching** | ✅ Live | Profiles cached for instant follow-ups |
| 🔨 **Code Quality Analysis** | ✅ Live | pylint + radon complexity + AST — secrets, nesting, bare excepts, missing tests |
| 🧠 **Idea Stress Tester** | ✅ Live | Three AI agents debate your idea in real time. The Believer finds every reason it could work. The Destroyer finds every reason it will fail. The Judge delivers a verdict with a refined version of your idea and concrete next steps. No more building in an echo chamber. |
| 🏗️ **Project Scaffolder** | ✅ Live | Survived the debate? GitRoast turns your idea into a real starter project — complete folder structure, tech stack recommendation (free tools only), core starter files with actual runnable code, and a week-by-week 4-week roadmap. Optionally creates the GitHub repo for you. |
| 💬 **Inline Code Comments** | ✅ Live | GitRoast drops color-coded review comments directly into your open VS Code files, with severity decorations (error/warning/info/praise) and Problems panel integration. |
| 🕵️ **Competitor Researcher** | 🔜 Phase 4 | GitHub + web intelligence |

---

## 🚀 Quick Start (5 minutes, all free)

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/gitroast.git
cd gitroast
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Get Your Free API Keys

| Key | Where | Time |
|-----|-------|------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → Create API Key | 30 seconds |
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) → New token (classic) | 1 minute |

**GitHub token scopes needed:** `read:user`, `public_repo` — that's it.

### 3. Configure Environment

```bash
cp .env.example .env
# Then edit .env with your keys:
```

```env
GROQ_API_KEY=gsk_your_groq_key_here
GITHUB_TOKEN=ghp_your_github_token_here
```

### 4. Connect to Claude Desktop (or any MCP agent)

Add this to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gitroast": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/gitroast"
    }
  }
}
```

**Config file location:**
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

Then restart Claude Desktop. You'll see the GitRoast tools appear in the tool list.

---

## 🎮 Usage Examples

### Roast a Developer

In Claude Desktop (or any compatible agent):

```
Analyze torvalds on GitHub and roast them as a yc_founder
```

```
analyze_developer(username="addyosmani", personality="senior_dev")
```

### Switch Personality Mid-Conversation

```
set_personality(personality="zen_mentor")
```

### Ask Follow-up Questions

```
ask_followup(question="Which of their repos has the best README?")
ask_followup(question="What language should they focus on?")
ask_followup(question="How many of their PRs actually had descriptions?")
```

### Clear Session

```
clear_session()
```

---

## 🎭 The 5 Personality Modes

| Mode | Emoji | Vibe | Example |
|------|-------|------|---------|
| `comedian` | 🎤 | Stand-up roast energy | *"17 commits called 'fix'. Fix WHAT? File a police report."* |
| `yc_founder` | 🚀 | Startup intensity | *"Your commit frequency is not investor-ready. We need to talk metrics."* |
| `senior_dev` | 😤 | Tired veteran | *"...I've seen this pattern since 2009. It's not nostalgia, it's concern."* |
| `zen_mentor` | 🧘 | Tough love with patience | *"Your gap of 47 days speaks to something. Let's examine that."* |
| `stranger` | 👻 | Unfiltered chaos | *"Zero stars. Two years. The algorithm has rendered its verdict."* |

---

## 🔬 What Data Does GitRoast Actually Analyze?

### Repository Analysis (up to 20 repos)
- Stars, forks, language, description
- README quality score (0–10): badges, screenshots, install/usage sections, word count
- Test file detection (does any file contain "test" in the path?)
- Days since last commit
- Commit count per repo

### Commit Analysis (last 90 days, up to 8 repos)
- Total commits and weekly average
- Bad commit message detection (exact match against 30+ lazy patterns: "fix", "wip", ".", "asdf"...)
- Late-night commits (11pm–4am)
- Weekend commits
- Most active coding hour
- Longest gap between commits

### Pull Request Analysis (top 5 starred repos)
- Total, merged, and open PR counts
- PR description length (< 20 chars = "no description")
- Average days to merge

### Issue Analysis (up to 5 repos)
- Open vs. closed ratio
- Issues open for > 30 days
- Issues with no labels
- Average days to close

---

## 📁 Project Structure

```
gitroast/
├── .github/workflows/ci.yml       # GitHub Actions CI
├── mcp_server/
│   ├── server.py                  # MCP entry point — 8 registered tools
│   ├── orchestrator.py            # Session cache, conversation history, debate context
│   ├── tools/
│   │   ├── github_scraper.py      # ★ Core engine — full GitHub analysis
│   │   ├── code_analyzer.py       # ★ Phase 2 LIVE — pylint + radon + AST
│   │   ├── idea_debater.py        # ★ Phase 3 LIVE — multi-agent debate system
│   │   ├── scaffolder.py          # ★ Phase 3 LIVE — project scaffolding engine
│   │   └── competitor_researcher.py  # Phase 4 stub
│   ├── personality/
│   │   └── engine.py              # 5 persona wrappers
│   └── utils/
│       └── helpers.py             # Formatting utilities
├── vscode_extension/              # VS Code sidebar + inline comments
│   ├── src/
│   │   ├── extension.ts           # Extension entry + 6 commands
│   │   ├── sidebar.ts             # Dark-themed WebView sidebar
│   │   ├── chat_panel.ts          # Chat panel
│   │   └── inline_comments.ts     # ★ Phase 3 LIVE — inline code review comments
│   └── package.json
├── tests/
│   ├── test_github_scraper.py     # 7 tests, all mocked
│   ├── test_personality.py        # 9 tests
│   ├── test_code_analyzer.py      # Phase 2 tests
│   ├── test_idea_debater.py       # ★ Phase 3 — 6 tests
│   └── test_scaffolder.py         # ★ Phase 3 — 7 tests
├── .env.example                   # Template — copy to .env
├── requirements.txt
└── pyproject.toml
```

---

## 🧪 Running Tests

```bash
# All tests (no real API calls — fully mocked)
pytest tests/ -v

# Specific file
pytest tests/test_personality.py -v
pytest tests/test_github_scraper.py -v

# With coverage
pip install pytest-cov
pytest tests/ --cov=mcp_server --cov-report=term-missing
```

---

## 🛠️ Running the Scraper Directly (CLI)

```bash
# Test the scraper standalone — analyzes a real profile
python -m mcp_server.tools.github_scraper
# Default: analyzes "torvalds" — edit the __main__ block to change

# Run the full MCP server (stdio mode for agent connections)
python -m mcp_server.server
```

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | required | Free at [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | `llama3-70b-8192` | Groq model to use |
| `GITHUB_TOKEN` | optional | 5,000 req/hr vs 60/hr without |
| `MCP_SERVER_HOST` | `localhost` | Server host |
| `MCP_SERVER_PORT` | `8765` | Server port |
| `DEBUG` | `true` | Enable debug logging |

---

## 🔌 MCP Tools Reference

| Tool | Phase | Inputs | Description |
|------|-------|--------|-------------|
| `analyze_developer` | 1 ✅ | `username`, `personality` | Full GitHub roast |
| `set_personality` | 1 ✅ | `personality` | Switch roast mode |
| `ask_followup` | 1 ✅ | `question` | Follow-up without re-fetch |
| `clear_session` | 1 ✅ | — | Clear cache + history |
| `analyze_code_quality` | 2 ✅ | `username`, `personality`, `max_repos` | Static analysis — pylint, radon, AST |
| `stress_test_idea` | 3 ✅ | `idea`, `context`, `personality` | Multi-agent debate (Believer/Destroyer/Judge) |
| `scaffold_project` | 3 ✅ | `idea`, `create_repo`, `personality` | Full project scaffold + optional GitHub repo |
| `research_competitors` | 4 🔜 | `idea` | Market intelligence |

---

## 🗺️ Roadmap

- [x] **Phase 1** — GitHub scraper, roast engine, MCP server, 5 personalities, VS Code skeleton
- [x] **Phase 2** — Code quality analyzer ✅ (pylint + radon + AST, scored 1-10 per repo; VS Code extension UI)
- [x] **Phase 3** — Idea Stress Tester + Project Scaffolder ✅
- [ ] **Phase 4** — Competitor researcher + advanced scaffolding
- [ ] **Phase 5** — Full VS Code extension: real-time roasting, deeper AI integration

---

## 🎭 The Debate Arena

GitRoast's **Idea Stress Tester** is a 3-agent multi-AI debate system. You pitch your idea. Three distinct agents argue it to death.

```
User pitches idea
      ↓
🟢 Agent 1: The Believer   → "Here's every reason this could WIN"
🔴 Agent 2: The Destroyer  → "Here's every reason this will FAIL"
      ↓
⚖️  Agent 3: The Judge     → Verdict + Refined Idea + Next Steps
```

**Sample output:**

```
## 🟢 The Case FOR: "AI-powered todo app"
### The Unfair Advantage
The $47B productivity market hasn't seen a tool that learns
your actual work patterns — not just stores your tasks.

Confidence Score: 8/10

---

## 🔴 The Case AGAINST: "AI-powered todo app"
### The Graveyard
Todoist, Any.do, Things 3 — all profitable, all deep-moated.
"AI" doesn't help you finish the tasks on the list.

Confidence Score: 7/10

---

## ⚖️ The Verdict: VALIDATE FIRST
The Destroyer won on market saturation, but missed the B2B angle.
Refined idea: AI that integrates with Jira/Linear to auto-prioritize
from real engineering tickets, not a blank list.

Next Steps:
1. Interview 10 engineering managers this week
2. Build a no-code demo in Notion
3. Measure if they'd pay $20/seat
```

---

## 🤝 Contributing

Contributions are welcome! This is an open, community-driven project.

```bash
git checkout -b feature/your-feature-name
# Make your changes
pytest tests/ -v          # All tests must pass
git commit -m "feat: add your feature with a real commit message"
git push origin feature/your-feature-name
# Open a PR — describe what you did and why
```

**Good first issues:**
- Adding more bad commit message patterns to `BAD_MESSAGES`
- Adding a new roast ammunition condition
- Improving README quality scoring heuristics
- Adding a new personality mode

---

## ⚖️ License

MIT — see [LICENSE](LICENSE). Use it, fork it, ship it. Just don't make it mean.

---

## 🙏 Acknowledgments

Built with:
- [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) — the protocol that makes this work
- [Groq](https://console.groq.com) — blazing fast, genuinely free LLM inference
- [PyGithub](https://github.com/PyGithub/PyGithub) — GitHub API wrapper
- [Pydantic v2](https://docs.pydantic.dev) — data validation
- [Rich](https://github.com/Textualize/rich) — beautiful terminal output
- [Loguru](https://github.com/Delgan/loguru) — structured logging

---

<div align="center">

**Built with 🔥 by developers who have seen too many `git commit -m "fix"` messages.**

*GitRoast roasts you because it cares.*

</div>
