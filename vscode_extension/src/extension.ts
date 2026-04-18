import * as vscode from 'vscode';
import { GitRoastSidebarProvider } from './sidebar';

export function activate(context: vscode.ExtensionContext): void {
    console.log('GitRoast extension activated');

    // Register sidebar webview provider
    const sidebarProvider = new GitRoastSidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('gitroastView', sidebarProvider)
    );

    // Command: Analyze GitHub Profile
    const analyzeProfileCmd = vscode.commands.registerCommand(
        'gitroast.analyzeProfile',
        async () => {
            const username = await vscode.window.showInputBox({
                prompt: 'Enter a GitHub username to roast',
                placeHolder: 'e.g. torvalds',
            });
            if (username) {
                vscode.window.showInformationMessage(
                    `🔥 GitRoast: Analyzing GitHub profile for "${username}"... ` +
                    'Connect the MCP server to get the full roast!'
                );
            }
        }
    );

    // Command: Switch Personality Mode
    const setPersonalityCmd = vscode.commands.registerCommand(
        'gitroast.setPersonality',
        async () => {
            const options = [
                { label: '🎤 Comedian', description: 'Brutal roast energy', value: 'comedian' },
                { label: '🚀 YC Founder', description: 'Startup intensity', value: 'yc_founder' },
                { label: '😤 Senior Dev', description: 'Tired veteran energy', value: 'senior_dev' },
                { label: '🧘 Zen Mentor', description: 'Tough love with patience', value: 'zen_mentor' },
                { label: '👻 Stranger', description: 'Unfiltered chaos', value: 'stranger' },
            ];
            const selected = await vscode.window.showQuickPick(options, {
                placeHolder: 'Choose your roast personality mode',
            });
            if (selected) {
                vscode.window.showInformationMessage(
                    `✅ GitRoast personality switched to ${selected.label} mode!`
                );
            }
        }
    );

    // Command: Clear Session
    const clearSessionCmd = vscode.commands.registerCommand(
        'gitroast.clearSession',
        () => {
            vscode.window.showInformationMessage(
                '🗑️ GitRoast: Session cleared. Fresh roast incoming!'
            );
        }
    );

    // Command: Open Chat Panel
    const openChatCmd = vscode.commands.registerCommand(
        'gitroast.openChat',
        () => {
            vscode.window.showInformationMessage(
                '💬 GitRoast Chat Panel coming in Phase 5. ' +
                'Use the sidebar or MCP tools in your AI agent for now!'
            );
        }
    );

    context.subscriptions.push(
        analyzeProfileCmd,
        setPersonalityCmd,
        clearSessionCmd,
        openChatCmd,
    );
}

export function deactivate(): void {
    // Cleanup handled by VS Code subscription disposal
}
