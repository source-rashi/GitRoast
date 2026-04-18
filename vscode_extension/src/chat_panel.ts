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
            'GitRoast Chat 🔥',
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

    html, body {
      height: 100%;
      font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
      background: #1e1e1e;
      color: #cccccc;
      font-size: 13px;
    }

    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }

    /* ---- HEADER ---- */
    .chat-header {
      padding: 12px 16px;
      background: #252526;
      border-bottom: 1px solid #333;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
    }

    .chat-header-title {
      font-size: 14px;
      font-weight: 700;
      background: linear-gradient(135deg, #ff6b35, #f7c948);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .chat-header-sub {
      font-size: 11px;
      color: #666;
    }

    /* ---- MESSAGES ---- */
    #messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }

    .msg {
      max-width: 85%;
      border-radius: 12px;
      padding: 10px 14px;
      line-height: 1.55;
      word-wrap: break-word;
      white-space: pre-wrap;
    }

    .msg-user {
      align-self: flex-end;
      background: #ff6b35;
      color: #111;
      border-bottom-right-radius: 3px;
      font-weight: 500;
    }

    .msg-bot-wrapper {
      align-self: flex-start;
      display: flex;
      flex-direction: column;
      gap: 4px;
      max-width: 85%;
    }

    .msg-bot-label {
      font-size: 10px;
      color: #888;
      font-weight: 600;
      letter-spacing: 0.5px;
      padding-left: 2px;
    }

    .msg-bot {
      background: #2d2d2d;
      color: #cccccc;
      border-bottom-left-radius: 3px;
      border: 1px solid #3a3a3a;
    }

    .msg-error {
      background: #4a1a1a;
      color: #ff6b6b;
      border: 1px solid #7a3a3a;
    }

    /* ---- TYPING INDICATOR ---- */
    .typing {
      align-self: flex-start;
      background: #2d2d2d;
      border: 1px solid #3a3a3a;
      border-radius: 12px;
      border-bottom-left-radius: 3px;
      padding: 10px 14px;
      display: none;
    }

    .typing.visible { display: flex; align-items: center; gap: 4px; }

    .typing-dot {
      width: 6px; height: 6px;
      border-radius: 50%;
      background: #888;
      animation: bounce 1.2s infinite;
    }

    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }

    @keyframes bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }

    /* ---- INPUT ---- */
    .input-row {
      display: flex;
      gap: 8px;
      padding: 12px 16px;
      background: #252526;
      border-top: 1px solid #333;
      flex-shrink: 0;
    }

    #chatInput {
      flex: 1;
      padding: 9px 12px;
      background: #2d2d2d;
      border: 1px solid #444;
      border-radius: 6px;
      color: #cccccc;
      font-size: 13px;
      outline: none;
      font-family: inherit;
      resize: none;
      transition: border-color 0.15s;
    }

    #chatInput:focus { border-color: #ff6b35; }

    #sendBtn {
      padding: 9px 16px;
      background: linear-gradient(135deg, #ff6b35, #f7c948);
      color: #111;
      border: none;
      border-radius: 6px;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      transition: opacity 0.15s;
      white-space: nowrap;
    }

    #sendBtn:hover { opacity: 0.88; }
    #sendBtn:disabled { opacity: 0.4; cursor: not-allowed; }
  </style>
</head>
<body>
<div class="chat-container">

  <div class="chat-header">
    <span style="font-size:20px;">🔥</span>
    <div>
      <div class="chat-header-title">GitRoast Chat</div>
      <div class="chat-header-sub">Ask questions about any analyzed developer</div>
    </div>
  </div>

  <div id="messages">
    <!-- Welcome message -->
    <div class="msg-bot-wrapper">
      <div class="msg-bot-label">🔥 GitRoast</div>
      <div class="msg msg-bot">👋 Hey! I'm GitRoast.

Analyze a developer from the sidebar first, then ask me anything about their profile — commits, PRs, worst repos, or just roast them harder.

Try: "Which repo is the worst?" or "What should they fix first?"</div>
    </div>
  </div>

  <div class="typing" id="typingIndicator">
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  </div>

  <div class="input-row">
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
      label.textContent = '🔥 GitRoast';
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
