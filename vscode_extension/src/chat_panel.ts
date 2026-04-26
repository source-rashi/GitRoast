import * as vscode from 'vscode';
import { GitRoastMCPClient } from './extension';

export class ChatPanel {
    public static currentPanel: ChatPanel | undefined;
    private static readonly viewType = 'gitroastChat';

    private readonly _panel: vscode.WebviewPanel;
    private readonly _client: GitRoastMCPClient;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(
        extensionUri: vscode.Uri,
        mcpClient: GitRoastMCPClient
    ): void {
        const column = vscode.window.activeTextEditor?.viewColumn ?? vscode.ViewColumn.One;

        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            ChatPanel.viewType,
            'GitRoast Chat',
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
            }
        );

        ChatPanel.currentPanel = new ChatPanel(panel, mcpClient);
    }

    private constructor(panel: vscode.WebviewPanel, client: GitRoastMCPClient) {
        this._panel = panel;
        this._client = client;

        this._panel.webview.html = this._getHtmlContent();

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.command) {
                    case 'sendMessage': {
                        const userMsg: string = message.text;
                        if (!userMsg.trim()) { return; }

                        // Show typing indicator
                        this._panel.webview.postMessage({ type: 'typing', show: true });

                        try {
                            const response = await this._client.callTool('ask_followup', {
                                question: userMsg,
                            });
                            this._panel.webview.postMessage({
                                type: 'response',
                                text: response,
                            });
                        } catch (err: unknown) {
                            const msg = err instanceof Error ? err.message : String(err);
                            this._panel.webview.postMessage({
                                type: 'error',
                                text: `Error: ${msg}`,
                            });
                        } finally {
                            this._panel.webview.postMessage({ type: 'typing', show: false });
                        }
                        break;
                    }
                }
            },
            null,
            this._disposables
        );
    }

    private _getHtmlContent(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GitRoast Chat</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: var(--vscode-editor-background, #1e1e2e);
      --bg-alt: var(--vscode-sideBar-background, #181825);
      --fg: var(--vscode-editor-foreground, #cdd6f4);
      --fg-dim: var(--vscode-descriptionForeground, #6c7086);
      --border: var(--vscode-panel-border, #313244);
      --input-bg: var(--vscode-input-background, #181825);
      --input-fg: var(--vscode-input-foreground, #cdd6f4);
      --input-border: var(--vscode-input-border, #45475a);
      --accent: #f97316;
      --accent2: #facc15;
    }

    html, body {
      height: 100%;
      font-family: var(--vscode-font-family, system-ui, -apple-system, sans-serif);
      font-size: var(--vscode-font-size, 13px);
      background: var(--bg);
      color: var(--fg);
    }

    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }

    /* ---- HEADER ---- */
    .chat-header {
      padding: 14px 20px;
      background: var(--bg-alt);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
      position: relative;
    }
    .chat-header::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 10%;
      right: 10%;
      height: 1px;
      background: linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent);
    }

    .header-icon {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      box-shadow: 0 2px 8px rgba(249,115,22,0.25);
      flex-shrink: 0;
    }

    .header-info { flex: 1; }
    .header-title {
      font-size: 15px;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .header-sub {
      font-size: 11px;
      color: var(--fg-dim);
      margin-top: 1px;
    }

    /* ---- MESSAGES ---- */
    #messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      scroll-behavior: smooth;
    }

    .msg {
      max-width: 82%;
      border-radius: 14px;
      padding: 12px 16px;
      line-height: 1.6;
      word-wrap: break-word;
      white-space: pre-wrap;
      font-size: 13px;
      animation: fadeIn 0.25s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .msg-user {
      align-self: flex-end;
      background: linear-gradient(135deg, var(--accent), #ea580c);
      color: #fff;
      border-bottom-right-radius: 4px;
      font-weight: 500;
      box-shadow: 0 2px 8px rgba(249,115,22,0.2);
    }

    .msg-bot-wrapper {
      align-self: flex-start;
      display: flex;
      flex-direction: column;
      gap: 4px;
      max-width: 82%;
    }

    .msg-bot-label {
      font-size: 10px;
      color: var(--fg-dim);
      font-weight: 600;
      letter-spacing: 0.5px;
      padding-left: 4px;
      text-transform: uppercase;
    }

    .msg-bot {
      background: var(--bg-alt);
      color: var(--fg);
      border-bottom-left-radius: 4px;
      border: 1px solid var(--border);
    }

    .msg-error {
      background: rgba(248,113,113,0.1);
      color: #f87171;
      border: 1px solid rgba(248,113,113,0.25);
    }

    /* ---- TYPING INDICATOR ---- */
    .typing {
      align-self: flex-start;
      background: var(--bg-alt);
      border: 1px solid var(--border);
      border-radius: 14px;
      border-bottom-left-radius: 4px;
      padding: 12px 16px;
      display: none;
    }
    .typing.visible { display: flex; align-items: center; gap: 5px; }

    .typing-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--accent);
      opacity: 0.5;
      animation: bounce 1.2s infinite;
    }
    .typing-dot:nth-child(2) { animation-delay: 0.15s; }
    .typing-dot:nth-child(3) { animation-delay: 0.3s; }

    @keyframes bounce {
      0%, 100% { transform: translateY(0); opacity: 0.5; }
      50% { transform: translateY(-5px); opacity: 1; }
    }

    /* ---- INPUT ---- */
    .input-area {
      display: flex;
      gap: 10px;
      padding: 14px 20px;
      background: var(--bg-alt);
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }

    #chatInput {
      flex: 1;
      padding: 10px 14px;
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 10px;
      color: var(--input-fg);
      font-size: 13px;
      outline: none;
      font-family: inherit;
      resize: none;
      transition: border-color 0.2s, box-shadow 0.2s;
      line-height: 1.4;
    }
    #chatInput:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(249,115,22,0.15);
    }
    #chatInput::placeholder {
      color: var(--fg-dim);
    }

    #sendBtn {
      padding: 10px 20px;
      background: linear-gradient(135deg, var(--accent), #ea580c);
      color: #fff;
      border: none;
      border-radius: 10px;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
      box-shadow: 0 2px 8px rgba(249,115,22,0.3);
    }
    #sendBtn:hover {
      box-shadow: 0 4px 16px rgba(249,115,22,0.4);
      transform: translateY(-1px);
    }
    #sendBtn:active { transform: translateY(0); }
    #sendBtn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
      transform: none !important;
      box-shadow: none !important;
    }
  </style>
</head>
<body>
<div class="chat-container">

  <div class="chat-header">
    <div class="header-icon">&#x1f525;</div>
    <div class="header-info">
      <div class="header-title">GitRoast Chat</div>
      <div class="header-sub">Ask follow-up questions about any analyzed developer</div>
    </div>
  </div>

  <div id="messages">
    <div class="msg-bot-wrapper">
      <div class="msg-bot-label">GitRoast</div>
      <div class="msg msg-bot">Hey! I'm GitRoast.

Analyze a developer from the sidebar first, then ask me anything about their profile — commits, PRs, worst repos, or just roast them harder.

Try: "Which repo is the worst?" or "What should they fix first?"</div>
    </div>
  </div>

  <div class="typing" id="typingIndicator">
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  </div>

  <div class="input-area">
    <textarea
      id="chatInput"
      placeholder="Ask anything about the analyzed developer..."
      rows="1"
    ></textarea>
    <button id="sendBtn">Send</button>
  </div>

</div>

<script>
  const vscode = acquireVsCodeApi();
  const messagesEl = document.getElementById('messages');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  const typingEl = document.getElementById('typingIndicator');

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(text, role) {
    if (role === 'user') {
      const div = document.createElement('div');
      div.className = 'msg msg-user';
      div.textContent = text;
      messagesEl.appendChild(div);
    } else if (role === 'bot') {
      const wrapper = document.createElement('div');
      wrapper.className = 'msg-bot-wrapper';
      const label = document.createElement('div');
      label.className = 'msg-bot-label';
      label.textContent = 'GitRoast';
      const msg = document.createElement('div');
      msg.className = 'msg msg-bot';
      msg.textContent = text;
      wrapper.appendChild(label);
      wrapper.appendChild(msg);
      messagesEl.appendChild(wrapper);
    } else if (role === 'error') {
      const wrapper = document.createElement('div');
      wrapper.className = 'msg-bot-wrapper';
      const msg = document.createElement('div');
      msg.className = 'msg msg-error';
      msg.textContent = text;
      wrapper.appendChild(msg);
      messagesEl.appendChild(wrapper);
    }
    scrollToBottom();
  }

  function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) { return; }
    chatInput.value = '';
    chatInput.style.height = 'auto';
    addMessage(text, 'user');
    sendBtn.disabled = true;
    vscode.postMessage({ command: 'sendMessage', text });
  }

  sendBtn.addEventListener('click', sendMessage);

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize textarea
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  });

  // Handle messages from extension host
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (msg.type === 'typing') {
      typingEl.classList.toggle('visible', msg.show);
      sendBtn.disabled = msg.show;
      scrollToBottom();
    } else if (msg.type === 'response') {
      addMessage(msg.text, 'bot');
    } else if (msg.type === 'error') {
      addMessage(msg.text, 'error');
    }
  });
</script>
</body>
</html>`;
    }

    public dispose(): void {
        ChatPanel.currentPanel = undefined;
        this._panel.dispose();
        this._disposables.forEach((d) => d.dispose());
        this._disposables = [];
    }
}
