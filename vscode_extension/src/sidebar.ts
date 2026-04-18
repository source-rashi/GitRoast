import * as vscode from 'vscode';

export class GitRoastSidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'gitroastView';

    constructor(private readonly _extensionUri: vscode.Uri) {}

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
                case 'analyze':
                    vscode.commands.executeCommand('gitroast.analyzeProfile');
                    break;
                case 'setPersonality':
                    vscode.commands.executeCommand('gitroast.setPersonality');
                    break;
            }
        });
    }

    private _getHtmlContent(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GitRoast</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--vscode-sideBar-background, #1e1e1e);
      color: var(--vscode-foreground, #cccccc);
      padding: 16px;
      min-height: 100vh;
    }

    .header {
      text-align: center;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--vscode-panel-border, #333);
    }

    .logo {
      font-size: 36px;
      display: block;
      margin-bottom: 4px;
    }

    .title {
      font-size: 16px;
      font-weight: 700;
      color: var(--vscode-textLink-foreground, #ff6b35);
      letter-spacing: 0.5px;
    }

    .subtitle {
      font-size: 11px;
      color: var(--vscode-descriptionForeground, #888);
      margin-top: 2px;
    }

    .section {
      margin-bottom: 16px;
    }

    label {
      display: block;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--vscode-descriptionForeground, #888);
      margin-bottom: 6px;
    }

    input[type="text"],
    select {
      width: 100%;
      padding: 8px 10px;
      background: var(--vscode-input-background, #3c3c3c);
      color: var(--vscode-input-foreground, #cccccc);
      border: 1px solid var(--vscode-input-border, #555);
      border-radius: 4px;
      font-size: 13px;
      outline: none;
      transition: border-color 0.15s;
    }

    input[type="text"]:focus,
    select:focus {
      border-color: var(--vscode-focusBorder, #ff6b35);
    }

    select option {
      background: var(--vscode-dropdown-background, #3c3c3c);
    }

    .btn-roast {
      width: 100%;
      padding: 10px;
      background: linear-gradient(135deg, #ff6b35 0%, #ff2d55 100%);
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      letter-spacing: 0.3px;
      transition: opacity 0.15s, transform 0.1s;
      margin-bottom: 8px;
    }

    .btn-roast:hover {
      opacity: 0.9;
      transform: translateY(-1px);
    }

    .btn-roast:active {
      transform: translateY(0);
    }

    .status {
      font-size: 11px;
      color: var(--vscode-descriptionForeground, #888);
      text-align: center;
      padding: 10px;
      background: var(--vscode-input-background, #3c3c3c);
      border-radius: 4px;
      border: 1px dashed var(--vscode-panel-border, #444);
      line-height: 1.5;
    }

    .status .dot {
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #888;
      margin-right: 5px;
      vertical-align: middle;
    }

    .personalities {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-top: 10px;
    }

    .personality-tag {
      font-size: 10px;
      padding: 4px 8px;
      border-radius: 12px;
      background: var(--vscode-badge-background, #333);
      color: var(--vscode-badge-foreground, #ccc);
      text-align: center;
      cursor: default;
    }
  </style>
</head>
<body>
  <div class="header">
    <span class="logo">🔥</span>
    <div class="title">GitRoast</div>
    <div class="subtitle">AI Developer Intelligence</div>
  </div>

  <div class="section">
    <label for="username">GitHub Username</label>
    <input
      type="text"
      id="username"
      placeholder="e.g. torvalds"
      autocomplete="off"
      spellcheck="false"
    />
  </div>

  <div class="section">
    <label for="personality">Roast Personality</label>
    <select id="personality">
      <option value="comedian">🎤 Stand-up Comedian</option>
      <option value="yc_founder">🚀 YC Co-Founder</option>
      <option value="senior_dev">😤 Senior Developer</option>
      <option value="zen_mentor">🧘 Zen Mentor</option>
      <option value="stranger">👻 Anonymous Stranger</option>
    </select>
  </div>

  <button class="btn-roast" id="analyzeBtn" onclick="handleAnalyze()">
    Analyze &amp; Roast 🔥
  </button>

  <div class="status">
    <span class="dot"></span>
    Connect GitRoast MCP server to get started.<br />
    Run <code>python -m mcp_server.server</code> in your terminal.
  </div>

  <script>
    const vscode = acquireVsCodeApi();

    function handleAnalyze() {
      const username = document.getElementById('username').value.trim();
      const personality = document.getElementById('personality').value;
      if (!username) {
        document.getElementById('username').focus();
        return;
      }
      vscode.postMessage({ command: 'analyze', username, personality });
    }

    document.getElementById('username').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleAnalyze();
    });
  </script>
</body>
</html>`;
    }
}
