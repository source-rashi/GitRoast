import * as vscode from 'vscode';
import { GitRoastMCPClient } from './extension';

export class GitRoastSidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'gitroastView';

    private _view?: vscode.WebviewView;
    private _lastAction: { username: string; timestamp: number } | null = null;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _client: GitRoastMCPClient | null
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };

        webviewView.webview.html = this._getHtmlContent();

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage((message) => {
            switch (message.command) {
                case 'roast':
                    this._setLoading(true, `Roasting ${message.username}...`);
                    this._lastAction = { username: message.username, timestamp: Date.now() };
                    vscode.commands.executeCommand('gitroast.analyzeProfile', {
                        username: message.username,
                        personality: message.personality,
                    }).then(() => {
                        this._setLoading(false, null, message.username);
                    }, (err: Error) => {
                        this._setLoading(false, null, null, err.message);
                    });
                    break;
                case 'analyze':
                    this._setLoading(true, `Analyzing code for ${message.username}...`);
                    this._lastAction = { username: message.username, timestamp: Date.now() };
                    vscode.commands.executeCommand('gitroast.analyzeCodeQuality', {
                        username: message.username,
                        maxRepos: Number(message.maxRepos) || 3,
                    }).then(() => {
                        this._setLoading(false, null, message.username);
                    }, (err: Error) => {
                        this._setLoading(false, null, null, err.message);
                    });
                    break;
                case 'openChat':
                    vscode.commands.executeCommand('gitroast.openChat');
                    break;
                case 'clearSession':
                    vscode.commands.executeCommand('gitroast.clearSession');
                    webviewView.webview.postMessage({
                        type: 'status',
                        text: 'Session cleared. Ready to roast again.',
                        isLoading: false,
                    });
                    break;
                case 'stressTest':
                    this._setLoading(true, `Debating idea...`);
                    vscode.commands.executeCommand('gitroast.stressTestIdea', {
                        idea: message.idea,
                        personality: message.personality,
                    }).then(() => {
                        this._setLoading(false, null, 'Idea Debated');
                    }, (err: Error) => {
                        this._setLoading(false, null, null, err.message);
                    });
                    break;
                case 'scaffold':
                    this._setLoading(true, `Scaffolding project...`);
                    vscode.commands.executeCommand('gitroast.scaffoldProject', {
                        idea: message.idea,
                        personality: message.personality,
                    }).then(() => {
                        this._setLoading(false, null, 'Project Scaffolded');
                    }, (err: Error) => {
                        this._setLoading(false, null, null, err.message);
                    });
                    break;
                case 'research':
                    this._setLoading(true, `Researching competitors...`);
                    vscode.commands.executeCommand('gitroast.researchCompetitors', {
                        idea: message.idea,
                        personality: message.personality,
                    }).then(() => {
                        this._setLoading(false, null, 'Research Complete');
                    }, (err: Error) => {
                        this._setLoading(false, null, null, err.message);
                    });
                    break;
                case 'teamRoast':
                    this._setLoading(true, `Team roasting ${message.usernames}...`);
                    vscode.commands.executeCommand('gitroast.roastTeam', {
                        usernames: message.usernames,
                        personality: message.personality,
                    }).then(() => {
                        this._setLoading(false, null, 'Team Roasted');
                    }, (err: Error) => {
                        this._setLoading(false, null, null, err.message);
                    });
                    break;
                case 'toggleWatcher':
                    vscode.commands.executeCommand('gitroast.toggleFileWatcher');
                    break;
            }
        });
    }

    private _setLoading(loading: boolean, message: string | null, doneUsername?: string | null, errorMsg?: string): void {
        if (!this._view) { return; }

        if (loading) {
            this._view.webview.postMessage({
                type: 'loadingStart',
                text: message,
            });
        } else if (errorMsg) {
            this._view.webview.postMessage({
                type: 'status',
                text: `Error: ${errorMsg}`,
                isLoading: false,
            });
        } else {
            const elapsed = this._lastAction
                ? this._getRelativeTime(this._lastAction.timestamp)
                : '';
            this._view.webview.postMessage({
                type: 'loadingDone',
                text: `Done — result opened in editor`,
                lastInfo: doneUsername
                    ? `Last roast: ${doneUsername} • ${elapsed}`
                    : '',
            });
        }
    }

    private _getRelativeTime(ts: number): string {
        const seconds = Math.floor((Date.now() - ts) / 1000);
        if (seconds < 60) { return `${seconds} seconds ago`; }
        const minutes = Math.floor(seconds / 60);
        return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    }

    private _getHtmlContent(): string {
        const connected = this._client?.isRunning ?? false;
        const statusDot = connected ? '#34d399' : '#f87171';
        const statusLabel = connected ? 'Connected' : 'Disconnected';

        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GitRoast</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: var(--vscode-sideBar-background, #1e1e2e);
      --fg: var(--vscode-editor-foreground, #cdd6f4);
      --fg-dim: var(--vscode-descriptionForeground, #6c7086);
      --border: var(--vscode-panel-border, #313244);
      --input-bg: var(--vscode-input-background, #181825);
      --input-fg: var(--vscode-input-foreground, #cdd6f4);
      --input-border: var(--vscode-input-border, #45475a);
      --focus: var(--vscode-focusBorder, #f9e2af);
      --btn2-bg: var(--vscode-button-secondaryBackground, #313244);
      --btn2-fg: var(--vscode-button-secondaryForeground, #cdd6f4);
      --accent: #48cae4;
      --accent2: #b5e2fa;
    }

    body {
      padding: 0;
      color: var(--fg);
      font-family: var(--vscode-font-family, system-ui, -apple-system, sans-serif);
      font-size: var(--vscode-font-size, 13px);
      background: transparent;
      overflow-x: hidden;
    }

    .container {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
      padding: 16px 12px;
    }

    /* ---- HEADER ---- */
    .header {
      text-align: center;
      padding-bottom: 16px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border);
      position: relative;
    }
    .header::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 20%;
      right: 20%;
      height: 1px;
      background: linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent);
    }

    .brand {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .brand-icon {
      width: 28px;
      height: 28px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      box-shadow: 0 2px 8px rgba(72,202,228,0.30);
    }
    .brand-text {
      font-size: 18px;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.3px;
    }
    .tagline {
      font-size: 11px;
      color: var(--fg-dim);
      margin-top: 4px;
      letter-spacing: 0.5px;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 8px;
      padding: 3px 10px;
      border-radius: 99px;
      font-size: 10px;
      color: ${statusDot};
      font-weight: 600;
      letter-spacing: 0.3px;
      background: rgba(0,0,0,0.15);
      border: 1px solid rgba(0,0,0,0.1);
    }
    .status-pill::before {
      content: '';
      width: 6px; height: 6px;
      border-radius: 50%;
      background: ${statusDot};
      box-shadow: 0 0 6px ${statusDot};
      ${connected ? 'animation: pulse 2s infinite;' : ''}
    }
    @keyframes pulse {
      0%,100% { opacity:1; box-shadow: 0 0 6px ${statusDot}; }
      50% { opacity:0.5; box-shadow: 0 0 2px ${statusDot}; }
    }

    /* ---- FORM ---- */
    .section { margin-bottom: 14px; }
    .section-label {
      display: block;
      font-size: 11px;
      font-weight: 600;
      color: var(--fg);
      margin-bottom: 5px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    input[type="text"], input[type="number"] {
      width: 100%;
      padding: 8px 10px;
      background: var(--input-bg);
      color: var(--input-fg);
      border: 1px solid var(--input-border);
      border-radius: 6px;
      font-size: var(--vscode-font-size, 13px);
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(72,202,228,0.20);
    }

    /* ---- CUSTOM SELECT ---- */
    .select-wrapper {
      position: relative;
    }
    .select-wrapper::after {
      content: '▼';
      position: absolute;
      right: 10px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 9px;
      color: var(--fg-dim);
      pointer-events: none;
    }
    select {
      width: 100%;
      padding: 8px 30px 8px 10px;
      background: var(--input-bg);
      color: var(--input-fg);
      border: 1px solid var(--input-border);
      border-radius: 6px;
      font-size: var(--vscode-font-size, 13px);
      font-family: inherit;
      outline: none;
      appearance: none;
      -webkit-appearance: none;
      cursor: pointer;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(72,202,228,0.20);
    }
    select option {
      background: var(--input-bg);
      color: var(--input-fg);
    }

    /* ---- BUTTONS ---- */
    .btn {
      width: 100%;
      padding: 9px 14px;
      border: none;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
    }
    .btn-primary {
      background: linear-gradient(135deg, var(--accent), #00b4d8);
      color: #fff;
      box-shadow: 0 2px 8px rgba(72,202,228,0.35);
    }
    .btn-primary:hover {
      box-shadow: 0 4px 16px rgba(72,202,228,0.50);
      transform: translateY(-1px);
    }
    .btn-primary:active { transform: translateY(0); }

    .btn-secondary {
      background: var(--btn2-bg);
      color: var(--btn2-fg);
      border: 1px solid var(--border);
    }
    .btn-secondary:hover {
      border-color: var(--accent);
    }
    .btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      transform: none !important;
      box-shadow: none !important;
    }

    .shortcut-hint {
      text-align: center;
      font-size: 10px;
      color: var(--fg-dim);
      margin-top: 6px;
    }
    .shortcut-hint kbd {
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 1px 5px;
      font-size: 10px;
    }

    .divider {
      border: none;
      border-top: 1px solid var(--border);
      margin: 16px 0;
    }

    .action-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 14px;
    }
    .action-btn {
      padding: 7px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      background: var(--input-bg);
      color: var(--fg);
      border: 1px solid var(--border);
      transition: all 0.2s;
      text-align: center;
    }
    .action-btn:hover {
      border-color: var(--accent);
    }
    .action-btn.active {
      background: var(--accent);
      color: #000;
      border-color: var(--accent);
      font-weight: 700;
    }

    /* ---- STATUS ---- */
    .status-card {
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 12px 12px 15px;
      font-size: 12px;
      line-height: 1.5;
      min-height: 48px;
      position: relative;
      overflow: hidden;
    }
    .status-card::before {
      content: '';
      position: absolute;
      left: 0; top: 0; bottom: 0;
      width: 3px;
      background: linear-gradient(180deg, var(--accent), var(--accent2));
      border-radius: 3px 0 0 3px;
    }
    .status-card .highlight { color: var(--accent); font-weight: 600; }
    .status-card .success { color: #34d399; font-weight: 600; }
    .status-card .error { color: #f87171; }
    .last-action {
      font-size: 10px;
      color: var(--fg-dim);
      margin-top: 6px;
      padding-left: 15px;
    }
    .loading-dots::after {
      content: '';
      animation: dots 1.4s steps(4, end) infinite;
    }
    @keyframes dots {
      0%,20% { content: ''; }
      40% { content: '.'; }
      60% { content: '..'; }
      80%,100% { content: '...'; }
    }

    /* ---- CAPABILITIES ---- */
    .cap-section { margin-bottom: 12px; }
    .cap-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      padding: 6px 0;
      user-select: none;
    }
    .cap-header span {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--fg-dim);
      font-weight: 600;
    }
    .cap-toggle {
      color: var(--fg-dim);
      transition: transform 0.25s ease;
      font-size: 10px;
    }
    .cap-toggle.open { transform: rotate(180deg); }
    .cap-list {
      overflow: hidden;
      max-height: 0;
      transition: max-height 0.3s ease;
    }
    .cap-list.open { max-height: 500px; }
    .cap-item {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 7px 0;
      border-top: 1px solid rgba(128,128,128,0.15);
    }
    .cap-icon {
      flex-shrink: 0;
      width: 24px; height: 24px;
      border-radius: 6px;
      background: rgba(139,92,246,0.12);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
    }
    .cap-name { font-size: 12px; font-weight: 500; color: var(--fg); }
    .cap-desc { font-size: 10px; color: var(--fg-dim); margin-top: 1px; }

    .footer {
      margin-top: auto;
      padding-top: 14px;
      text-align: center;
      font-size: 10px;
      color: var(--fg-dim);
      border-top: 1px solid var(--border);
      letter-spacing: 0.3px;
    }
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="brand">
      <div class="brand-icon">&#x1f525;</div>
      <span class="brand-text">GitRoast</span>
    </div>
    <div class="tagline">AI-Powered Developer Intelligence</div>
    <div class="status-pill">${statusLabel}</div>
  </div>

  <div class="section">
    <label class="section-label" for="usernameInput">GitHub Username</label>
    <input type="text" id="usernameInput" placeholder="e.g. torvalds" autocomplete="off" spellcheck="false" />
  </div>
  <div class="section">
    <label class="section-label" for="personalitySelect">Roast Personality</label>
    <div class="select-wrapper">
      <select id="personalitySelect">
        <option value="comedian">&#x1f3a4; Stand-up Comedian</option>
        <option value="yc_founder">&#x1f680; YC Co-Founder</option>
        <option value="senior_dev">&#x1f624; Senior Developer</option>
        <option value="zen_mentor">&#x1f9d8; Zen Mentor</option>
        <option value="stranger">&#x1f47b; Anonymous Stranger</option>
      </select>
    </div>
  </div>
  <div class="section">
    <button class="btn btn-primary" id="roastBtn">&#x1f525; Roast This Dev</button>
    <div class="shortcut-hint">Or press <kbd>Ctrl+Shift+G</kbd></div>
  </div>

  <hr class="divider" />

  <div class="section">
    <label class="section-label" for="reposInput">Code Quality &mdash; Repos (1&ndash;5)</label>
    <input type="number" id="reposInput" min="1" max="5" value="3" />
  </div>
  <div class="section">
    <button class="btn btn-secondary" id="analyzeBtn">&#x1f52c; Analyze Code</button>
  </div>

  <div class="section">
    <label class="section-label" for="ideaInput">Startup / Project Idea</label>
    <input type="text" id="ideaInput" placeholder="e.g. VS Code extension for..." autocomplete="off" spellcheck="false" />
  </div>
  <div class="action-row" style="grid-template-columns: 1fr 1fr 1fr;">
    <button class="action-btn" id="stressTestBtn" style="font-size: 10px;">&#x2696;&#xfe0f; Debate</button>
    <button class="action-btn" id="scaffoldBtn" style="font-size: 10px;">&#x1f3d7; Scaffold</button>
    <button class="action-btn" id="researchBtn" style="font-size: 10px;">&#x1f575; Research</button>
  </div>

  <hr class="divider" />

  <div class="action-row">
    <button class="action-btn" id="chatBtn">&#x1f4ac; Chat</button>
    <button class="action-btn" id="clearBtn">&#x1f5d1; Clear</button>
  </div>

  <hr class="divider" />

  <div class="section">
    <label class="section-label" for="teamInput">&#x1f465; Team Roast &mdash; Usernames</label>
    <input type="text" id="teamInput" placeholder="e.g. alice,bob,charlie" autocomplete="off" spellcheck="false" />
  </div>
  <div class="section">
    <button class="btn btn-secondary" id="teamRoastBtn">&#x1f465; Roast The Team</button>
  </div>

  <hr class="divider" />

  <div class="action-row">
    <button class="action-btn" id="watcherBtn">&#x1f441; File Watcher</button>
    <button class="action-btn" id="chatBtn2" style="font-size: 11px">&#x1f517; Webhooks</button>
  </div>

  <div class="status-card" id="statusArea">Ready to roast. Enter a username above.</div>
  <div class="last-action" id="lastAction"></div>

  <hr class="divider" />

  <div class="cap-section">
    <div class="cap-header" id="capHeader">
      <span>What GitRoast Can Do</span>
      <span class="cap-toggle open" id="capToggle">&#x25BC;</span>
    </div>
    <div class="cap-list open" id="capList">
      <div class="cap-item">
        <div class="cap-icon">&#x1f525;</div>
        <div><div class="cap-name">Profile Roast</div><div class="cap-desc">Full roast from real commits, PRs &amp; issues</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f52c;</div>
        <div><div class="cap-name">Code Quality</div><div class="cap-desc">pylint + radon + AST analysis across repos</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f9e0;</div>
        <div><div class="cap-name">Debate Ideas</div><div class="cap-desc">3-agent debate: Believer &#x2022; Destroyer &#x2022; Judge</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x2696;&#xfe0f;</div>
        <div><div class="cap-name">Idea Stress Test</div><div class="cap-desc">Structured evaluation across multiple AI agents</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f3d7;</div>
        <div><div class="cap-name">Scaffold Projects</div><div class="cap-desc">Folder structure + tech stack + 4-week roadmap</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f575;</div>
        <div><div class="cap-name">Research Competitors</div><div class="cap-desc">GitHub intelligence + differentiation wedge</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f4ac;</div>
        <div><div class="cap-name">AI Chat Panel</div><div class="cap-desc">Free-form chat with context from your session</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f465;</div>
        <div><div class="cap-name">Team Roast</div><div class="cap-desc">Compare multiple devs with leaderboard + group roast</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f441;</div>
        <div><div class="cap-name">File Watcher</div><div class="cap-desc">Real-time micro-roasts when you save Python files</div></div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">&#x1f517;</div>
        <div><div class="cap-name">Webhooks</div><div class="cap-desc">Send results to Slack, Discord, or any webhook</div></div>
      </div>
    </div>
  </div>

  <div class="footer">GitRoast v0.5.0 &nbsp;&bull;&nbsp; Free Forever &nbsp;&bull;&nbsp; MCP Powered</div>
</div>

<script>
  const vscode = acquireVsCodeApi();
  let isLoading = false;

  function getUsername() { return document.getElementById('usernameInput').value.trim(); }

  function setStatus(text, extraClass) {
    const el = document.getElementById('statusArea');
    el.innerHTML = text;
    el.className = 'status-card' + (extraClass ? ' ' + extraClass : '');
  }

  function setLastAction(text) { document.getElementById('lastAction').textContent = text; }

  function setButtonsDisabled(disabled) {
    isLoading = disabled;
    ['roastBtn','analyzeBtn','chatBtn','clearBtn', 'stressTestBtn', 'scaffoldBtn', 'researchBtn', 'teamRoastBtn', 'watcherBtn'].forEach(id => {
      const btn = document.getElementById(id);
      if (btn) btn.disabled = disabled;
    });
  }

  document.getElementById('roastBtn').addEventListener('click', () => {
    const username = getUsername();
    if (!username) { setStatus('<span class="highlight">Please enter a GitHub username first.</span>'); return; }
    const personality = document.getElementById('personalitySelect').value;
    setStatus(\`<span class="highlight">Roasting \${username}</span> as <span class="highlight">\${personality}</span><span class="loading-dots"></span>\`);
    setButtonsDisabled(true);
    vscode.postMessage({ command: 'roast', username, personality });
  });

  document.getElementById('analyzeBtn').addEventListener('click', () => {
    const username = getUsername();
    if (!username) { setStatus('<span class="highlight">Please enter a GitHub username first.</span>'); return; }
    const maxRepos = document.getElementById('reposInput').value;
    setStatus(\`Analyzing code for <span class="highlight">\${username}</span> (\${maxRepos} repos)<span class="loading-dots"></span>\`);
    setButtonsDisabled(true);
    vscode.postMessage({ command: 'analyze', username, maxRepos });
  });

  document.getElementById('chatBtn').addEventListener('click', () => { vscode.postMessage({ command: 'openChat' }); });
  document.getElementById('clearBtn').addEventListener('click', () => { vscode.postMessage({ command: 'clearSession' }); });
  document.getElementById('usernameInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !isLoading) document.getElementById('roastBtn').click();
  });
  
  function getIdea() { return document.getElementById('ideaInput').value.trim(); }

  document.getElementById('stressTestBtn').addEventListener('click', () => {
    const idea = getIdea();
    if (!idea) { setStatus('<span class="highlight">Please enter an idea first.</span>'); return; }
    const personality = document.getElementById('personalitySelect').value;
    setStatus(\`Debating idea...<span class="loading-dots"></span>\`);
    setButtonsDisabled(true);
    vscode.postMessage({ command: 'stressTest', idea, personality });
  });

  document.getElementById('scaffoldBtn').addEventListener('click', () => {
    const idea = getIdea();
    if (!idea) { setStatus('<span class="highlight">Please enter an idea first.</span>'); return; }
    const personality = document.getElementById('personalitySelect').value;
    setStatus(\`Scaffolding project...<span class="loading-dots"></span>\`);
    setButtonsDisabled(true);
    vscode.postMessage({ command: 'scaffold', idea, personality });
  });

  document.getElementById('researchBtn').addEventListener('click', () => {
    const idea = getIdea();
    if (!idea) { setStatus('<span class="highlight">Please enter an idea first.</span>'); return; }
    const personality = document.getElementById('personalitySelect').value;
    setStatus(\`Researching competitors...<span class="loading-dots"></span>\`);
    setButtonsDisabled(true);
    vscode.postMessage({ command: 'research', idea, personality });
  });

  document.getElementById('ideaInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !isLoading) document.getElementById('stressTestBtn').click();
  });

  document.getElementById('capHeader').addEventListener('click', () => {
    document.getElementById('capList').classList.toggle('open');
    document.getElementById('capToggle').classList.toggle('open');
  });

  // -- Phase 5: Team Roast --
  document.getElementById('teamRoastBtn').addEventListener('click', () => {
    const usernames = document.getElementById('teamInput').value.trim();
    if (!usernames) { setStatus('<span class="highlight">Enter comma-separated usernames.</span>'); return; }
    const personality = document.getElementById('personalitySelect').value;
    setStatus(\`Team roasting <span class="highlight">\${usernames}</span><span class="loading-dots"></span>\`);
    setButtonsDisabled(true);
    vscode.postMessage({ command: 'teamRoast', usernames, personality });
  });

  document.getElementById('teamInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !isLoading) document.getElementById('teamRoastBtn').click();
  });

  // -- Phase 5: File Watcher Toggle --
  document.getElementById('watcherBtn').addEventListener('click', () => {
    const btn = document.getElementById('watcherBtn');
    btn.classList.toggle('active');
    vscode.postMessage({ command: 'toggleWatcher' });
  });

  // -- Phase 5: Webhooks info --
  document.getElementById('chatBtn2').addEventListener('click', () => {
    setStatus('<span class="highlight">Webhooks:</span> Use the MCP tool <code>send_to_webhook</code> via CLI/Claude Desktop with your Slack or Discord webhook URL.');
  });

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (msg.type === 'status') { setStatus(msg.text); setButtonsDisabled(false); }
    else if (msg.type === 'loadingStart') { setStatus(\`\${msg.text}<span class="loading-dots"></span>\`); setButtonsDisabled(true); }
    else if (msg.type === 'loadingDone') {
      setStatus(\`<span class="success">\${msg.text}</span>\`);
      if (msg.lastInfo) setLastAction(msg.lastInfo);
      setButtonsDisabled(false);
    }
  });
</script>
</body>
</html>`;
    }
}
