import * as vscode from 'vscode';
import { GitRoastMCPClient } from './extension';

export class GitRoastSidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'gitroastView';

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _client: GitRoastMCPClient | null
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ): void {
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };

        webviewView.webview.html = this._getHtmlContent();

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage((message) => {
            switch (message.command) {
                case 'roast':
                    vscode.commands.executeCommand('gitroast.analyzeProfile', {
                        username: message.username,
                        personality: message.personality,
                    });
                    break;
                case 'analyze':
                    vscode.commands.executeCommand('gitroast.analyzeCodeQuality', {
                        username: message.username,
                        maxRepos: Number(message.maxRepos) || 3,
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
                    });
                    break;
            }
        });
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
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      background: #1e1e1e;
      color: #cccccc;
      padding: 16px;
      font-size: 13px;
      min-height: 100vh;
    }

    /* ---- HEADER ---- */
    .header {
      text-align: center;
      padding-bottom: 14px;
      margin-bottom: 14px;
      border-bottom: 1px solid #333;
    }

    .logo-text {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #ff6b35, #f7c948);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .subtitle {
      font-size: 11px;
      color: #888;
      margin-top: 2px;
      letter-spacing: 0.5px;
    }

    .status-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      margin-top: 8px;
    }

    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: ${statusColor};
      box-shadow: 0 0 4px ${statusColor}88;
    }

    .status-label {
      font-size: 11px;
      color: ${statusColor};
    }

    /* ---- SECTIONS ---- */
    .section {
      margin-bottom: 14px;
    }

    label {
      display: block;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #888;
      margin-bottom: 5px;
    }

    input[type="text"],
    input[type="number"],
    select {
      width: 100%;
      padding: 7px 10px;
      background: #2d2d2d;
      color: #cccccc;
      border: 1px solid #444;
      border-radius: 5px;
      font-size: 12px;
      outline: none;
      transition: border-color 0.15s;
      -webkit-appearance: none;
    }

    input[type="text"]:focus,
    input[type="number"]:focus,
    select:focus {
      border-color: #ff6b35;
    }

    select option {
      background: #2d2d2d;
      color: #cccccc;
    }

    /* ---- BUTTONS ---- */
    .btn {
      width: 100%;
      padding: 9px 12px;
      border: none;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      transition: opacity 0.15s, transform 0.1s;
      letter-spacing: 0.2px;
    }

    .btn-primary {
      background: linear-gradient(135deg, #ff6b35 0%, #f7c948 100%);
      color: #111;
    }

    .btn-secondary {
      background: linear-gradient(135deg, #4a90e2 0%, #7b68ee 100%);
      color: #fff;
    }

    .btn:hover { opacity: 0.88; transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }

    /* ---- SESSION ROW ---- */
    .btn-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .btn-small {
      padding: 7px 10px;
      border-radius: 5px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid #444;
      background: #2d2d2d;
      color: #ccc;
      transition: background 0.15s, border-color 0.15s;
    }

    .btn-small:hover { background: #383838; border-color: #666; }

    /* ---- DIVIDER ---- */
    .divider {
      border: none;
      border-top: 1px solid #333;
      margin: 14px 0;
    }

    /* ---- STATUS AREA ---- */
    .status-area {
      background: #2d2d2d;
      border: 1px solid #3a3a3a;
      border-radius: 5px;
      padding: 10px 12px;
      font-size: 11px;
      color: #999;
      line-height: 1.6;
      min-height: 40px;
    }

    .status-area .highlight { color: #ff6b35; font-weight: 600; }
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

  <script>
    const vscode = acquireVsCodeApi();

    function getUsername() {
      return document.getElementById('usernameInput').value.trim();
    }

    function setStatus(text) {
      document.getElementById('statusArea').innerHTML = text;
    }

    document.getElementById('roastBtn').addEventListener('click', () => {
      const username = getUsername();
      if (!username) { setStatus('<span class="highlight">⚠️ Please enter a GitHub username first.</span>'); return; }
      const personality = document.getElementById('personalitySelect').value;
      setStatus(\`⏳ Roasting <span class="highlight">\${username}</span> as <span class="highlight">\${personality}</span>... This may take 30–60 seconds.\`);
      vscode.postMessage({ command: 'roast', username, personality });
    });

    document.getElementById('analyzeBtn').addEventListener('click', () => {
      const username = getUsername();
      if (!username) { setStatus('<span class="highlight">⚠️ Please enter a GitHub username first.</span>'); return; }
      const maxRepos = document.getElementById('reposInput').value;
      setStatus(\`⏳ Analyzing code quality for <span class="highlight">\${username}</span> (\${maxRepos} repos)...\`);
      vscode.postMessage({ command: 'analyze', username, maxRepos });
    });

    document.getElementById('chatBtn').addEventListener('click', () => {
      vscode.postMessage({ command: 'openChat' });
    });

    document.getElementById('clearBtn').addEventListener('click', () => {
      vscode.postMessage({ command: 'clearSession' });
    });

    document.getElementById('usernameInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') document.getElementById('roastBtn').click();
    });

    // Handle messages from extension host
    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg.type === 'status') {
        setStatus(msg.text);
      }
    });
  </script>
</body>
</html>`;
    }
}
