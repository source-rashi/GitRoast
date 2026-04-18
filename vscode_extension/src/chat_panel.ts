/** TypeScript stub for the GitRoast Chat Panel — Phase 5 */

import * as vscode from 'vscode';

export class ChatPanel {
    public static currentPanel: ChatPanel | undefined;

    public static createOrShow(extensionUri: vscode.Uri): void {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'gitroastChat',
            'GitRoast Chat',
            column || vscode.ViewColumn.One,
            { enableScripts: true }
        );

        panel.webview.html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #1e1e1e;
      color: #ccc;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      text-align: center;
    }
    .container { max-width: 400px; }
    .emoji { font-size: 48px; margin-bottom: 16px; }
    h2 { color: #ff6b35; margin-bottom: 8px; }
    p { color: #888; font-size: 14px; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="container">
    <div class="emoji">💬</div>
    <h2>GitRoast Chat</h2>
    <p>Full chat panel coming in Phase 5.<br/>
    Use the MCP tools in your AI agent, or the sidebar, for now!</p>
  </div>
</body>
</html>`;

        ChatPanel.currentPanel = new ChatPanel(panel);
    }

    private constructor(private readonly _panel: vscode.WebviewPanel) {
        _panel.onDidDispose(() => {
            ChatPanel.currentPanel = undefined;
        });
    }
}
