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

    constructor(outputChannel: vscode.OutputChannel) {
        this.outputChannel = outputChannel;
    }

    start(serverPath: string): void {
        this.outputChannel.appendLine(`[GitRoast] Starting MCP server at: ${serverPath}`);

        this.process = cp.spawn('python', ['-m', 'mcp_server.server'], {
            cwd: serverPath,
            stdio: ['pipe', 'pipe', 'pipe'],
            env: { ...process.env },
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
            // Reject all pending requests
            this.pendingRequests.forEach((pending) => {
                clearTimeout(pending.timer);
                pending.reject(new Error('MCP server process exited'));
            });
            this.pendingRequests.clear();
        });

        this.outputChannel.appendLine('[GitRoast] MCP server started.');
    }

    async callTool(toolName: string, args: Record<string, unknown>): Promise<string> {
        if (!this.process || !this.process.stdin) {
            throw new Error(
                'GitRoast MCP server is not running. Set gitroast.mcpServerPath in VS Code settings.'
            );
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
                reject(new Error(`Tool '${toolName}' timed out after 60 seconds.`));
            }, 60_000);
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
// Extension activate
// ---------------------------------------------------------------------------

let mcpClient: GitRoastMCPClient | null = null;

export function activate(context: vscode.ExtensionContext): void {
    console.log('GitRoast extension activated');

    const outputChannel = vscode.window.createOutputChannel('GitRoast');
    context.subscriptions.push(outputChannel);

    mcpClient = new GitRoastMCPClient(outputChannel);

    // Auto-start if path is configured
    const config = vscode.workspace.getConfiguration('gitroast');
    const serverPath: string = config.get('mcpServerPath', '');
    if (serverPath) {
        mcpClient.start(serverPath);
    } else {
        vscode.window
            .showWarningMessage(
                'GitRoast: MCP server path not configured.',
                'Configure Path'
            )
            .then((choice) => {
                if (choice === 'Configure Path') {
                    vscode.commands.executeCommand(
                        'workbench.action.openSettings',
                        'gitroast.mcpServerPath'
                    );
                }
            });
    }

    // Register sidebar
    const sidebarProvider = new GitRoastSidebarProvider(context.extensionUri, mcpClient);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('gitroastView', sidebarProvider)
    );

    // Register inline comment manager
    const inlineCommentManager = new InlineCommentManager(context);
    registerInlineCommentCommands(context, inlineCommentManager);

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

    context.subscriptions.push(
        analyzeProfileCmd,
        analyzeCodeCmd,
        setPersonalityCmd,
        clearSessionCmd,
        openChatCmd,
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
}
