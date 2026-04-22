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
                        text: '🗑️ Session cleared. Ready to roast again.',
                        isLoading: false,
                    });
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
                text: `❌ Error: ${errorMsg}`,
                isLoading: false,
            });
        } else {
            const elapsed = this._lastAction
                ? this._getRelativeTime(this._lastAction.timestamp)
                : '';
            this._view.webview.postMessage({
                type: 'loadingDone',
                text: `✅ Done — result opened in editor`,
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
        const statusColor = connected ? '#4caf50' : '#f44336';
        const statusLabel = connected ? 'Connected' : 'Disconnected';

        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GitRoast</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      padding: 10px;
      color: var(--vscode-editor-foreground);
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      background-color: transparent;
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }

    /* ---- HEADER ---- */
    .header {
      text-align: center;
      padding-bottom: 12px;
      margin-bottom: 12px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }

    .logo-text {
      font-size: calc(var(--vscode-font-size) * 1.5);
      font-weight: 600;
      color: var(--vscode-activityBarBadge-background);
    }

    .subtitle {
      font-size: calc(var(--vscode-font-size) * 0.9);
      color: var(--vscode-descriptionForeground);
      margin-top: 4px;
    }

    .status-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      margin-top: 8px;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: ${statusColor};
    }

    .status-label {
      font-size: calc(var(--vscode-font-size) * 0.9);
      color: ${statusColor};
    }

    /* ---- SECTIONS ---- */
    .section { margin-bottom: 16px; }

    label {
      display: block;
      font-size: calc(var(--vscode-font-size) * 0.9);
      color: var(--vscode-foreground);
      margin-bottom: 4px;
    }

    input[type="text"],
    input[type="number"],
    select {
      width: 100%;
      padding: 6px 8px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      font-size: var(--vscode-font-size);
      outline: none;
      border-radius: 2px;
    }

    input[type="text"]:focus,
    input[type="number"]:focus,
    select:focus {
      border: 1px solid var(--vscode-focusBorder);
      outline: 1px solid var(--vscode-focusBorder);
      outline-offset: -1px;
    }

    /* ---- BUTTONS ---- */
    .btn {
      width: 100%;
      padding: 6px 12px;
      border: none;
      border-radius: 2px;
      font-size: var(--vscode-font-size);
      cursor: pointer;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 6px;
    }

    .btn-primary {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
    }
    .btn-primary:hover {
      background: var(--vscode-button-hoverBackground);
    }

    .btn-secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    .btn-secondary:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }

    .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .shortcut-hint {
      text-align: center;
      font-size: calc(var(--vscode-font-size) * 0.85);
      color: var(--vscode-descriptionForeground);
      margin-top: 6px;
    }
    .shortcut-hint kbd {
      background: var(--vscode-editorHoverWidget-background);
      border: 1px solid var(--vscode-editorHoverWidget-border);
      border-radius: 3px;
      padding: 1px 4px;
    }

    /* ---- SESSION ROW ---- */
    .btn-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .btn-small {
      padding: 4px 8px;
      border: 1px solid var(--vscode-button-secondaryBackground);
      border-radius: 2px;
      font-size: calc(var(--vscode-font-size) * 0.9);
      cursor: pointer;
      background: transparent;
      color: var(--vscode-button-secondaryBackground);
      text-align: center;
    }
    .btn-small:hover {
      background: var(--vscode-button-secondaryHoverBackground);
      color: var(--vscode-button-secondaryForeground);
    }

    /* ---- DIVIDER ---- */
    .divider { 
      border: none; 
      border-top: 1px solid var(--vscode-panel-border); 
      margin: 16px 0; 
    }

    /* ---- STATUS AREA ---- */
    .status-area {
      background: var(--vscode-textBlockQuote-background);
      border-left: 3px solid var(--vscode-textBlockQuote-border);
      padding: 8px 10px;
      font-size: calc(var(--vscode-font-size) * 0.9);
      color: var(--vscode-foreground);
      min-height: 48px;
    }
    .status-area .highlight { color: var(--vscode-textLink-foreground); }
    .status-area .success { color: var(--vscode-testing-iconPassed); }

    .last-action {
      font-size: calc(var(--vscode-font-size) * 0.85);
      color: var(--vscode-descriptionForeground);
      margin-top: 4px;
    }

    .loading-dots::after {
      content: '';
      animation: dots 1.4s steps(4, end) infinite;
    }
    @keyframes dots {
      0%, 20% { content: ''; }
      40% { content: '.'; }
      60% { content: '..'; }
      80%, 100% { content: '...'; }
    }

    /* ---- CAPABILITIES SECTION ---- */
    .capabilities { margin-bottom: 12px; }
    .capabilities-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      padding: 6px 0;
      user-select: none;
    }
    .capabilities-header span {
      font-size: calc(var(--vscode-font-size) * 0.9);
      text-transform: uppercase;
      color: var(--vscode-foreground);
    }
    .capabilities-toggle {
      color: var(--vscode-icon-foreground);
      transition: transform 0.2s;
    }
    .capabilities-toggle.open { transform: rotate(180deg); }
    .capabilities-list {
      overflow: hidden;
      max-height: 0;
      transition: max-height 0.3s ease;
    }
    .capabilities-list.open { max-height: 200px; }
    
    .cap-item {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 6px 0;
      border-top: 1px dotted var(--vscode-panel-border);
    }
    .cap-icon { flex-shrink: 0; }
    .cap-text { flex: 1; }
    .cap-name { font-size: calc(var(--vscode-font-size) * 0.9); color: var(--vscode-foreground); }
    .cap-desc { font-size: calc(var(--vscode-font-size) * 0.85); color: var(--vscode-descriptionForeground); margin-top: 2px; }

    /* ---- FOOTER ---- */
    .footer {
      margin-top: auto;
      padding-top: 12px;
      text-align: center;
      font-size: calc(var(--vscode-font-size) * 0.85);
      color: var(--vscode-descriptionForeground);
      border-top: 1px solid var(--vscode-panel-border);
    }
  </style>
</head>
<body>

  <!-- HEADER -->
  <div class="header">
    <div class="logo-text">🔥 GitRoast</div>
    <div class="subtitle">AI Developer Intelligence</div>
    <div class="status-row">
      <div class="status-dot"></div>
      <span class="status-label">${statusLabel}</span>
    </div>
  </div>

  <!-- SECTION 1: Analyze Profile -->
  <div class="section">
    <label for="usernameInput">GitHub Username</label>
    <input
      type="text"
      id="usernameInput"
      placeholder="e.g. torvalds"
      autocomplete="off"
      spellcheck="false"
    />
  </div>

  <div class="section">
    <label for="personalitySelect">Personality Mode</label>
    <select id="personalitySelect">
      <option value="comedian">🎤 Stand-up Comedian</option>
      <option value="yc_founder">🚀 YC Co-Founder</option>
      <option value="senior_dev">😤 Senior Developer</option>
      <option value="zen_mentor">🧘 Zen Mentor</option>
      <option value="stranger">👻 Anonymous Stranger</option>
    </select>
  </div>

  <div class="section">
    <button class="btn btn-primary" id="roastBtn">🔥 Roast This Dev</button>
    <div class="shortcut-hint">Or use <kbd style="background:#2d2d2d;border:1px solid #444;border-radius:3px;padding:1px 4px;font-size:10px;">Ctrl+Shift+G</kbd> to analyze</div>
  </div>

  <hr class="divider" />

  <!-- SECTION 2: Code Quality -->
  <div class="section">
    <label for="reposInput">Code Quality — Repos to Analyze (1–5)</label>
    <input
      type="number"
      id="reposInput"
      min="1"
      max="5"
      value="3"
    />
  </div>

  <div class="section">
    <button class="btn btn-secondary" id="analyzeBtn">🔬 Analyze Code</button>
  </div>

  <hr class="divider" />

  <!-- SECTION 3: Session Controls -->
  <div class="section">
    <div class="btn-row">
      <button class="btn-small" id="chatBtn">💬 Open Chat</button>
      <button class="btn-small" id="clearBtn">🗑️ Clear Session</button>
    </div>
  </div>

  <!-- SECTION 4: Status Area -->
  <div class="status-area" id="statusArea">
    Ready to roast. Enter a username above.
  </div>
  <div class="last-action" id="lastAction"></div>

  <hr class="divider" />

  <!-- SECTION 5: Capabilities (collapsible) -->
  <div class="capabilities">
    <div class="capabilities-header" id="capHeader">
      <span>What Can GitRoast Do?</span>
      <span class="capabilities-toggle" id="capToggle">▼</span>
    </div>
    <div class="capabilities-list" id="capList">
      <div class="cap-item">
        <div class="cap-icon">🔍</div>
        <div class="cap-text">
          <div class="cap-name">Analyze GitHub Profile</div>
          <div class="cap-desc">Full roast with real commits, PRs &amp; issue data</div>
        </div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">🔬</div>
        <div class="cap-text">
          <div class="cap-name">Code Quality Analysis</div>
          <div class="cap-desc">pylint + radon complexity + AST secret detection</div>
        </div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">🧠</div>
        <div class="cap-text">
          <div class="cap-name">Stress Test An Idea</div>
          <div class="cap-desc">3-agent debate: Believer vs Destroyer vs Judge</div>
        </div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">🏗️</div>
        <div class="cap-text">
          <div class="cap-name">Scaffold A Project</div>
          <div class="cap-desc">Full folder structure + tech stack + 4-week roadmap</div>
        </div>
      </div>
      <div class="cap-item">
        <div class="cap-icon">🕵️</div>
        <div class="cap-text">
          <div class="cap-name">Research Competitors</div>
          <div class="cap-desc">GitHub search intelligence + differentiation wedge</div>
        </div>
      </div>
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    GitRoast v0.4.0 &nbsp;•&nbsp; Free Forever &nbsp;•&nbsp; MCP Powered
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    let isLoading = false;

    function getUsername() {
      return document.getElementById('usernameInput').value.trim();
    }

    function setStatus(text, extraClass) {
      const el = document.getElementById('statusArea');
      el.innerHTML = text;
      el.className = 'status-area' + (extraClass ? ' ' + extraClass : '');
    }

    function setLastAction(text) {
      document.getElementById('lastAction').textContent = text;
    }

    function setButtonsDisabled(disabled) {
      isLoading = disabled;
      ['roastBtn', 'analyzeBtn', 'chatBtn', 'clearBtn'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = disabled;
      });
    }

    document.getElementById('roastBtn').addEventListener('click', () => {
      const username = getUsername();
      if (!username) {
        setStatus('<span class="highlight">⚠️ Please enter a GitHub username first.</span>');
        return;
      }
      const personality = document.getElementById('personalitySelect').value;
      setStatus(\`⏳ <span class="highlight">Roasting \${username}</span> as <span class="highlight">\${personality}</span><span class="loading-dots"></span>\`, 'loading');
      setButtonsDisabled(true);
      vscode.postMessage({ command: 'roast', username, personality });
    });

    document.getElementById('analyzeBtn').addEventListener('click', () => {
      const username = getUsername();
      if (!username) {
        setStatus('<span class="highlight">⚠️ Please enter a GitHub username first.</span>');
        return;
      }
      const maxRepos = document.getElementById('reposInput').value;
      setStatus(\`⏳ Analyzing code quality for <span class="highlight">\${username}</span> (\${maxRepos} repos)<span class="loading-dots"></span>\`, 'loading');
      setButtonsDisabled(true);
      vscode.postMessage({ command: 'analyze', username, maxRepos });
    });

    document.getElementById('chatBtn').addEventListener('click', () => {
      vscode.postMessage({ command: 'openChat' });
    });

    document.getElementById('clearBtn').addEventListener('click', () => {
      vscode.postMessage({ command: 'clearSession' });
    });

    document.getElementById('usernameInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !isLoading) document.getElementById('roastBtn').click();
    });

    // Capabilities toggle
    document.getElementById('capHeader').addEventListener('click', () => {
      const list = document.getElementById('capList');
      const toggle = document.getElementById('capToggle');
      list.classList.toggle('open');
      toggle.classList.toggle('open');
    });

    // Handle messages from extension host
    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg.type === 'status') {
        setStatus(msg.text);
        setButtonsDisabled(false);
      } else if (msg.type === 'loadingStart') {
        setStatus(\`⏳ \${msg.text}<span class="loading-dots"></span>\`, 'loading');
        setButtonsDisabled(true);
      } else if (msg.type === 'loadingDone') {
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
