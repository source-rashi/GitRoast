import * as vscode from 'vscode';
import * as path from 'path';
import * as cp from 'child_process';
import * as readline from 'readline';
import { GitRoastSidebarProvider } from './sidebar';
import { ChatPanel } from './chat_panel';
import { InlineCommentManager, registerInlineCommentCommands } from './inline_comments';

// ---------------------------------------------------------------------------
// MCP Client — communicates with the Python MCP server via stdio
// ---------------------------------------------------------------------------

interface PendingRequest {
    resolve: (value: string) => void;
    reject: (reason: Error) => void;
    timer: NodeJS.Timeout;
}

export class GitRoastMCPClient {
    private process: cp.ChildProcess | null = null;
    private pendingRequests = new Map<number, PendingRequest>();
    private requestId = 1;
    private outputChannel: vscode.OutputChannel;
    private buffer = '';
    private initPromise: Promise<void> | null = null;

    constructor(outputChannel: vscode.OutputChannel) {
        this.outputChannel = outputChannel;
    }

    start(serverPath: string): void {
        this.outputChannel.appendLine(`[GitRoast] Starting MCP server at: ${serverPath}`);

        this.process = cp.spawn('python', ['-m', 'mcp_server.server'], {
            cwd: serverPath,
            stdio: ['pipe', 'pipe', 'pipe'],
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        });

        if (!this.process.stdout || !this.process.stdin || !this.process.stderr) {
            this.outputChannel.appendLine('[GitRoast] Failed to open stdio streams.');
            return;
        }

        // Read newline-delimited JSON from stdout
        const rl = readline.createInterface({ input: this.process.stdout });
        rl.on('line', (line: string) => {
            this.outputChannel.appendLine(`[MCP ←] ${line}`);
            try {
                const msg = JSON.parse(line);
                const id: number = msg.id;
                const pending = this.pendingRequests.get(id);
                if (pending) {
                    clearTimeout(pending.timer);
                    this.pendingRequests.delete(id);
                    if (msg.error) {
                        pending.reject(new Error(msg.error.message || 'MCP error'));
                    } else {
                        const content = msg.result?.content?.[0]?.text ?? JSON.stringify(msg.result);
                        pending.resolve(content);
                    }
                }
            } catch {
                // Not JSON — likely startup banner, ignore
            }
        });

        this.process.stderr?.on('data', (data: Buffer) => {
            this.outputChannel.appendLine(`[MCP stderr] ${data.toString().trim()}`);
        });

        this.process.on('exit', (code: number | null) => {
            this.outputChannel.appendLine(`[GitRoast] MCP server exited with code ${code}`);
            this.process = null;
            this.initPromise = null;
            // Reject all pending requests
            this.pendingRequests.forEach((pending) => {
                clearTimeout(pending.timer);
                pending.reject(new Error('MCP server process exited'));
            });
            this.pendingRequests.clear();
        });

        this.outputChannel.appendLine('[GitRoast] MCP server started.');
        this.initPromise = this._initializeMCP();
    }

    private async _initializeMCP(): Promise<void> {
        return new Promise((resolve, reject) => {
            if (!this.process || !this.process.stdin) {
                return reject(new Error('Process not running'));
            }
            const id = this.requestId++;
            const initMsg = JSON.stringify({
                jsonrpc: '2.0',
                id,
                method: 'initialize',
                params: {
                    protocolVersion: '2024-11-05',
                    capabilities: {},
                    clientInfo: { name: 'gitroast-vscode', version: '0.4.0' }
                }
            });

            this.outputChannel.appendLine(`[MCP →] ${initMsg}`);
            
            const timer = setTimeout(() => {
                this.pendingRequests.delete(id);
                reject(new Error('Init timeout after 60 seconds'));
            }, 60000);
            
            this.pendingRequests.set(id, {
                resolve: () => {
                    clearTimeout(timer);
                    const notif = JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'notifications/initialized'
                    });
                    this.outputChannel.appendLine(`[MCP →] ${notif}`);
                    this.process?.stdin?.write(notif + '\n');
                    resolve();
                },
                reject: (err) => {
                    clearTimeout(timer);
                    reject(err);
                },
                timer
            });

            this.process.stdin.write(initMsg + '\n');
        });
    }

    async callTool(toolName: string, args: Record<string, unknown>): Promise<string> {
        if (!this.process || !this.process.stdin) {
            throw new Error(
                'GitRoast MCP server is not running. Set gitroast.mcpServerPath in VS Code settings.'
            );
        }

        if (this.initPromise) {
            await this.initPromise;
        }

        const id = this.requestId++;
        const message = JSON.stringify({
            jsonrpc: '2.0',
            id,
            method: 'tools/call',
            params: { name: toolName, arguments: args },
        });

        this.outputChannel.appendLine(`[MCP →] ${message}`);
        this.process.stdin.write(message + '\n');

        return new Promise<string>((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pendingRequests.delete(id);
                reject(new Error(`Tool '${toolName}' timed out after 300 seconds.`));
            }, 300_000);
            this.pendingRequests.set(id, { resolve, reject, timer });
        });
    }

    stop(): void {
        if (this.process) {
            this.outputChannel.appendLine('[GitRoast] Stopping MCP server...');
            this.process.kill();
            this.process = null;
        }
    }

    get isRunning(): boolean {
        return this.process !== null;
    }
}

// ---------------------------------------------------------------------------
// Status bar item
// ---------------------------------------------------------------------------

let statusBarItem: vscode.StatusBarItem | null = null;

function createStatusBar(): vscode.StatusBarItem {
    const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    item.text = '$(flame) GitRoast';
    item.tooltip = 'GitRoast — Click to open sidebar';
    item.command = 'gitroast.openSidebar';
    item.color = new vscode.ThemeColor('statusBar.foreground');
    item.show();
    return item;
}

function setStatusBarActive(active: boolean): void {
    if (!statusBarItem) { return; }
    if (active) {
        statusBarItem.text = '$(flame) GitRoast: Analyzing...';
        statusBarItem.color = '#ff6b35';
    } else {
        statusBarItem.text = '$(flame) GitRoast';
        statusBarItem.color = undefined;
    }
}

// ---------------------------------------------------------------------------
// Welcome webview
// ---------------------------------------------------------------------------

function showWelcomeWebview(context: vscode.ExtensionContext): void {
    const panel = vscode.window.createWebviewPanel(
        'gitroastWelcome',
        '🔥 Welcome to GitRoast',
        vscode.ViewColumn.One,
        { enableScripts: false }
    );

    panel.webview.html = getWelcomeHtml();
}

function getWelcomeHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Welcome to GitRoast</title>
  <style>
    body {
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      background: #1e1e1e;
      color: #cccccc;
      max-width: 680px;
      margin: 0 auto;
      padding: 40px 24px;
      line-height: 1.6;
    }
    .logo { text-align: center; margin-bottom: 32px; }
    .logo-text {
      font-size: 48px;
      font-weight: 900;
      background: linear-gradient(135deg, #ff6b35, #f7c948);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .subtitle { font-size: 16px; color: #888; margin-top: 8px; letter-spacing: 1px; }
    h2 { color: #ff6b35; font-size: 18px; margin: 28px 0 12px; font-weight: 700; }
    .step {
      display: flex;
      gap: 16px;
      align-items: flex-start;
      padding: 14px 18px;
      background: #252525;
      border: 1px solid #333;
      border-radius: 8px;
      margin-bottom: 10px;
    }
    .step-num {
      background: linear-gradient(135deg, #ff6b35, #f7c948);
      color: #111;
      font-weight: 900;
      font-size: 14px;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .step-body strong { color: #ffffff; display: block; margin-bottom: 4px; }
    .step-body span { font-size: 12px; color: #888; }
    code {
      background: #2d2d2d;
      border: 1px solid #444;
      border-radius: 4px;
      padding: 2px 6px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 12px;
      color: #f7c948;
    }
    .tools {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .tool-card {
      background: #252525;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 12px 14px;
    }
    .tool-card .icon { font-size: 20px; margin-bottom: 6px; }
    .tool-card .name { font-size: 13px; font-weight: 700; color: #cc; }
    .tool-card .desc { font-size: 11px; color: #666; margin-top: 2px; }
    .api-section {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 10px;
    }
    .api-card {
      background: #252525;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 14px;
      text-align: center;
    }
    .api-card .api-name { font-size: 14px; font-weight: 700; color: #ff6b35; margin-bottom: 4px; }
    .api-card .api-url { font-size: 11px; color: #888; }
    .badge {
      display: inline-block;
      background: #4caf5020;
      border: 1px solid #4caf50;
      color: #4caf50;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 12px;
      margin-left: 8px;
      vertical-align: middle;
    }
  </style>
</head>
<body>
  <div class="logo">
    <div class="logo-text">🔥 GitRoast</div>
    <div class="subtitle">AI Developer Intelligence</div>
  </div>

  <h2>🚀 Quick Start (3 steps)</h2>

  <div class="step">
    <div class="step-num">1</div>
    <div class="step-body">
      <strong>Get your free API keys</strong>
      <span>Groq API key (console.groq.com) + GitHub token (github.com/settings/tokens)</span>
    </div>
  </div>

  <div class="step">
    <div class="step-num">2</div>
    <div class="step-body">
      <strong>Configure the MCP server path</strong>
      <span>Open VS Code Settings → search "gitroast" → set <code>mcpServerPath</code> to your GitRoast folder</span>
    </div>
  </div>

  <div class="step">
    <div class="step-num">3</div>
    <div class="step-body">
      <strong>Start roasting</strong>
      <span>Use the sidebar (🔥 icon) or press <code>Ctrl+Shift+G</code> to analyze any GitHub profile</span>
    </div>
  </div>

  <h2>🛠️ Available Commands</h2>

  <div class="tools">
    <div class="tool-card">
      <div class="icon">🔍</div>
      <div class="name">Analyze Profile</div>
      <div class="desc">Roast any GitHub user with real data · Ctrl+Shift+G</div>
    </div>
    <div class="tool-card">
      <div class="icon">🔬</div>
      <div class="name">Code Quality</div>
      <div class="desc">pylint + radon + AST analysis across repos</div>
    </div>
    <div class="tool-card">
      <div class="icon">🧠</div>
      <div class="name">Stress Test Idea</div>
      <div class="desc">3-agent debate: Believer/Destroyer/Judge</div>
    </div>
    <div class="tool-card">
      <div class="icon">🏗️</div>
      <div class="name">Scaffold Project</div>
      <div class="desc">Full folder structure + 4-week roadmap</div>
    </div>
    <div class="tool-card">
      <div class="icon">🕵️</div>
      <div class="name">Research Competitors</div>
      <div class="desc">GitHub search intelligence + your wedge</div>
    </div>
    <div class="tool-card">
      <div class="icon">💬</div>
      <div class="name">Inline Comments</div>
      <div class="desc">AI review comments in your editor · Ctrl+Shift+R</div>
    </div>
  </div>

  <h2>🔑 Get Your Free API Keys</h2>

  <div class="api-section">
    <div class="api-card">
      <div class="api-name">Groq API <span class="badge">FREE</span></div>
      <div class="api-url">console.groq.com</div>
      <div style="font-size:11px;color:#666;margin-top:8px;">~30 seconds · no credit card</div>
    </div>
    <div class="api-card">
      <div class="api-name">GitHub Token <span class="badge">FREE</span></div>
      <div class="api-url">github.com/settings/tokens</div>
      <div style="font-size:11px;color:#666;margin-top:8px;">read:user + public_repo scope</div>
    </div>
  </div>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Extension activate
// ---------------------------------------------------------------------------

let mcpClient: GitRoastMCPClient | null = null;

export function activate(context: vscode.ExtensionContext): void {
    console.log('GitRoast extension activated');

    const outputChannel = vscode.window.createOutputChannel('GitRoast');
    context.subscriptions.push(outputChannel);

    mcpClient = new GitRoastMCPClient(outputChannel);

    // Create status bar item
    statusBarItem = createStatusBar();
    context.subscriptions.push(statusBarItem);

    // Auto-detect server path:
    // 1. Use explicit user setting if set
    // 2. Fall back to the parent of the vscode_extension folder (the gitroast root)
    const config = vscode.workspace.getConfiguration('gitroast');
    const configuredPath: string = config.get('mcpServerPath', '');

    // The extension lives at: <gitroast_root>/vscode_extension
    // So its parent is the gitroast root which contains mcp_server/
    const extensionDir = context.extensionPath; // e.g. .../gitroast/vscode_extension
    const autoDetectedPath = path.dirname(extensionDir); // e.g. .../gitroast

    const serverPath = configuredPath || autoDetectedPath;
    outputChannel.appendLine(`[GitRoast] Using server path: ${serverPath}`);

    // Always start — serverPath is guaranteed to be set (either from settings or auto-detected)
    mcpClient.start(serverPath);

    // Register sidebar
    const sidebarProvider = new GitRoastSidebarProvider(context.extensionUri, mcpClient);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('gitroastView', sidebarProvider)
    );

    // Register inline comment manager
    const inlineCommentManager = new InlineCommentManager(context);
    registerInlineCommentCommands(context, inlineCommentManager);

    // ----------------------------------------------------------------
    // Command: Open Sidebar
    // ----------------------------------------------------------------
    const openSidebarCmd = vscode.commands.registerCommand(
        'gitroast.openSidebar',
        () => {
            vscode.commands.executeCommand('workbench.view.extension.gitroast-sidebar');
        }
    );

    // ----------------------------------------------------------------
    // Command: Show Welcome
    // ----------------------------------------------------------------
    const showWelcomeCmd = vscode.commands.registerCommand(
        'gitroast.showWelcome',
        () => {
            showWelcomeWebview(context);
        }
    );

    // ----------------------------------------------------------------
    // Command: Analyze GitHub Profile
    // ----------------------------------------------------------------
    const analyzeProfileCmd = vscode.commands.registerCommand(
        'gitroast.analyzeProfile',
        async (args?: { username?: string; personality?: string }) => {
            const client = mcpClient;
            if (!client) { return; }

            const username =
                args?.username ||
                (await vscode.window.showInputBox({
                    prompt: 'Enter a GitHub username to roast 🔥',
                    placeHolder: 'e.g. torvalds',
                }));
            if (!username) { return; }

            const personalityItems = [
                { label: '🎤 Stand-up Comedian', value: 'comedian', description: 'Brutal roast energy' },
                { label: '🚀 YC Co-Founder', value: 'yc_founder', description: 'Startup intensity' },
                { label: '😤 Senior Developer', value: 'senior_dev', description: 'Tired veteran energy' },
                { label: '🧘 Zen Mentor', value: 'zen_mentor', description: 'Tough love with patience' },
                { label: '👻 Anonymous Stranger', value: 'stranger', description: 'Unfiltered chaos' },
            ];
            const chosen = args?.personality
                ? personalityItems.find((p) => p.value === args.personality) ?? personalityItems[0]
                : await vscode.window.showQuickPick(personalityItems, {
                    placeHolder: 'Choose your roast personality',
                    matchOnDescription: true,
                });
            if (!chosen) { return; }
            const personality = typeof chosen === 'string' ? chosen : (chosen as { value: string }).value;

            setStatusBarActive(true);
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: `🔥 GitRoast is roasting ${username}...`,
                    cancellable: false,
                },
                async () => {
                    try {
                        const result = await client.callTool('analyze_developer', {
                            username,
                            personality,
                        });
                        await openInDocument(result, `GitRoast — ${username}.md`);
                    } catch (err: unknown) {
                        const msg = err instanceof Error ? err.message : String(err);
                        vscode.window.showErrorMessage(`GitRoast error: ${msg}`);
                    } finally {
                        setStatusBarActive(false);
                    }
                }
            );
        }
    );

    // ----------------------------------------------------------------
    // Command: Analyze Code Quality
    // ----------------------------------------------------------------
    const analyzeCodeCmd = vscode.commands.registerCommand(
        'gitroast.analyzeCodeQuality',
        async (args?: { username?: string; maxRepos?: number }) => {
            const client = mcpClient;
            if (!client) { return; }

            const username =
                args?.username ||
                (await vscode.window.showInputBox({
                    prompt: 'Enter a GitHub username for code quality analysis 🔬',
                    placeHolder: 'e.g. torvalds',
                }));
            if (!username) { return; }

            const maxRepos = args?.maxRepos ?? 3;

            setStatusBarActive(true);
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: `🔬 Analyzing code quality for ${username}...`,
                    cancellable: false,
                },
                async () => {
                    try {
                        const result = await client.callTool('analyze_code_quality', {
                            username,
                            max_repos: maxRepos,
                        });
                        await openInDocument(result, `GitRoast Code Quality — ${username}.md`);
                    } catch (err: unknown) {
                        const msg = err instanceof Error ? err.message : String(err);
                        vscode.window.showErrorMessage(`GitRoast error: ${msg}`);
                    } finally {
                        setStatusBarActive(false);
                    }
                }
            );
        }
    );

    // ----------------------------------------------------------------
    // Command: Set Personality
    // ----------------------------------------------------------------
    const setPersonalityCmd = vscode.commands.registerCommand(
        'gitroast.setPersonality',
        async () => {
            const client = mcpClient;
            if (!client) { return; }

            const options = [
                { label: '🎤 Stand-up Comedian', value: 'comedian' },
                { label: '🚀 YC Co-Founder', value: 'yc_founder' },
                { label: '😤 Senior Developer', value: 'senior_dev' },
                { label: '🧘 Zen Mentor', value: 'zen_mentor' },
                { label: '👻 Anonymous Stranger', value: 'stranger' },
            ];
            const selected = await vscode.window.showQuickPick(options, {
                placeHolder: 'Choose your roast personality mode',
            });
            if (!selected) { return; }
            try {
                const result = await client.callTool('set_personality', {
                    personality: selected.value,
                });
                vscode.window.showInformationMessage(`✅ ${result}`);
            } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : String(err);
                vscode.window.showErrorMessage(`GitRoast error: ${msg}`);
            }
        }
    );

    // ----------------------------------------------------------------
    // Command: Clear Session
    // ----------------------------------------------------------------
    const clearSessionCmd = vscode.commands.registerCommand(
        'gitroast.clearSession',
        async () => {
            const client = mcpClient;
            if (!client) { return; }
            try {
                await client.callTool('clear_session', {});
                vscode.window.showInformationMessage('🗑️ GitRoast session cleared. Fresh roast incoming!');
            } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : String(err);
                vscode.window.showErrorMessage(`GitRoast error: ${msg}`);
            }
        }
    );

    // ----------------------------------------------------------------
    // Command: Open Chat Panel
    // ----------------------------------------------------------------
    const openChatCmd = vscode.commands.registerCommand(
        'gitroast.openChat',
        () => {
            if (!mcpClient) { return; }
            ChatPanel.createOrShow(context.extensionUri, mcpClient);
        }
    );

    // ----------------------------------------------------------------
    // Command: Stress Test Idea
    // ----------------------------------------------------------------
    const stressTestIdeaCmd = vscode.commands.registerCommand(
        'gitroast.stressTestIdea',
        async (args?: { idea?: string; personality?: string }) => {
            const client = mcpClient;
            if (!client) { return; }

            const idea =
                args?.idea ||
                (await vscode.window.showInputBox({
                    prompt: 'Enter your startup/project idea to stress test ⚖️',
                    placeHolder: 'e.g. A VS Code extension that...',
                }));
            if (!idea) { return; }

            const personality = args?.personality || 'yc_founder';

            setStatusBarActive(true);
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: `⚖️ GitRoast is debating your idea...`,
                    cancellable: false,
                },
                async () => {
                    try {
                        const result = await client.callTool('stress_test_idea', {
                            idea,
                            personality,
                        });
                        await openInDocument(result, `GitRoast Debate — Idea.md`);
                    } catch (err: unknown) {
                        const msg = err instanceof Error ? err.message : String(err);
                        vscode.window.showErrorMessage(`GitRoast error: ${msg}`);
                    } finally {
                        setStatusBarActive(false);
                    }
                }
            );
        }
    );

    // ----------------------------------------------------------------
    // Command: Scaffold Project
    // ----------------------------------------------------------------
    const scaffoldProjectCmd = vscode.commands.registerCommand(
        'gitroast.scaffoldProject',
        async (args?: { idea?: string; personality?: string }) => {
            const client = mcpClient;
            if (!client) { return; }

            const idea =
                args?.idea ||
                (await vscode.window.showInputBox({
                    prompt: 'Enter your idea to scaffold 🏗️',
                    placeHolder: 'e.g. A VS Code extension that...',
                }));
            if (!idea) { return; }

            const personality = args?.personality || 'yc_founder';

            setStatusBarActive(true);
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: `🏗️ GitRoast is scaffolding your project...`,
                    cancellable: false,
                },
                async () => {
                    try {
                        const result = await client.callTool('scaffold_project', {
                            idea,
                            personality,
                            create_repo: false
                        });
                        await openInDocument(result, `GitRoast Scaffold — Idea.md`);
                    } catch (err: unknown) {
                        const msg = err instanceof Error ? err.message : String(err);
                        vscode.window.showErrorMessage(`GitRoast error: ${msg}`);
                    } finally {
                        setStatusBarActive(false);
                    }
                }
            );
        }
    );

    // ----------------------------------------------------------------
    // Command: Research Competitors
    // ----------------------------------------------------------------
    const researchCompetitorsCmd = vscode.commands.registerCommand(
        'gitroast.researchCompetitors',
        async (args?: { idea?: string; personality?: string }) => {
            const client = mcpClient;
            if (!client) { return; }

            const idea =
                args?.idea ||
                (await vscode.window.showInputBox({
                    prompt: 'Enter your idea to research competitors 🕵️',
                    placeHolder: 'e.g. A VS Code extension that...',
                }));
            if (!idea) { return; }

            const personality = args?.personality || 'yc_founder';

            setStatusBarActive(true);
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: `🕵️ GitRoast is researching competitors...`,
                    cancellable: false,
                },
                async () => {
                    try {
                        const result = await client.callTool('research_competitors', {
                            idea,
                            personality,
                        });
                        await openInDocument(result, `GitRoast Competitors — Idea.md`);
                    } catch (err: unknown) {
                        const msg = err instanceof Error ? err.message : String(err);
                        vscode.window.showErrorMessage(`GitRoast error: ${msg}`);
                    } finally {
                        setStatusBarActive(false);
                    }
                }
            );
        }
    );

    context.subscriptions.push(
        openSidebarCmd,
        showWelcomeCmd,
        analyzeProfileCmd,
        analyzeCodeCmd,
        setPersonalityCmd,
        clearSessionCmd,
        openChatCmd,
        stressTestIdeaCmd,
        scaffoldProjectCmd,
        researchCompetitorsCmd,
    );
}

// ---------------------------------------------------------------------------
// Helper: open text in a new untitled markdown document
// ---------------------------------------------------------------------------
async function openInDocument(content: string, _title: string): Promise<void> {
    const doc = await vscode.workspace.openTextDocument({
        content,
        language: 'markdown',
    });
    await vscode.window.showTextDocument(doc, { preview: false });
}

export function deactivate(): void {
    mcpClient?.stop();
    mcpClient = null;
    statusBarItem?.dispose();
    statusBarItem = null;
}
