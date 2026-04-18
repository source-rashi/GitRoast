/**
 * GitRoast — Inline Code Comments
 * ==================================
 * After analyzing a repo, GitRoast drops comments directly into open files.
 * Like a code review from your chosen persona.
 *
 * Examples:
 *   // 🔥 GitRoast [Senior Dev]: complexity 14 — split this function NOW
 *   // 💀 GitRoast [Senior Dev]: bare except detected. What exactly are you catching?
 *   // ✅ GitRoast [Senior Dev]: clean error handling here. Don't ruin it.
 */

import * as vscode from 'vscode';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GitRoastComment {
    lineNumber: number;
    message: string;
    severity: 'error' | 'warning' | 'info' | 'praise';
    personality: string;
}

// ---------------------------------------------------------------------------
// InlineCommentManager
// ---------------------------------------------------------------------------

export class InlineCommentManager {
    private decorationTypes: Map<string, vscode.TextEditorDecorationType> = new Map();
    private activeComments: Map<string, GitRoastComment[]> = new Map();
    private diagnosticCollection: vscode.DiagnosticCollection;

    constructor(context: vscode.ExtensionContext) {
        // Create 4 decoration types with distinct colors
        const error = vscode.window.createTextEditorDecorationType({
            backgroundColor: 'rgba(255,0,0,0.08)',
            borderColor: '#ff4444',
            borderStyle: 'solid',
            borderWidth: '0 0 0 3px',
            after: {
                color: '#ff4444',
                margin: '0 0 0 12px',
            },
        });

        const warning = vscode.window.createTextEditorDecorationType({
            backgroundColor: 'rgba(255,165,0,0.08)',
            borderColor: '#ffaa00',
            borderStyle: 'solid',
            borderWidth: '0 0 0 3px',
            after: {
                color: '#ffaa00',
                margin: '0 0 0 12px',
            },
        });

        const info = vscode.window.createTextEditorDecorationType({
            backgroundColor: 'rgba(100,149,237,0.08)',
            borderColor: '#6495ed',
            borderStyle: 'solid',
            borderWidth: '0 0 0 3px',
            after: {
                color: '#6495ed',
                margin: '0 0 0 12px',
            },
        });

        const praise = vscode.window.createTextEditorDecorationType({
            backgroundColor: 'rgba(0,200,100,0.08)',
            borderColor: '#00c864',
            borderStyle: 'solid',
            borderWidth: '0 0 0 3px',
            after: {
                color: '#00c864',
                margin: '0 0 0 12px',
            },
        });

        this.decorationTypes.set('error', error);
        this.decorationTypes.set('warning', warning);
        this.decorationTypes.set('info', info);
        this.decorationTypes.set('praise', praise);

        // Register decoration types for cleanup
        context.subscriptions.push(error, warning, info, praise);

        // Create diagnostic collection (shows in the Problems panel)
        this.diagnosticCollection = vscode.languages.createDiagnosticCollection('GitRoast');
        context.subscriptions.push(this.diagnosticCollection);
    }

    /**
     * Add GitRoast inline comments to the given editor.
     */
    addComments(
        editor: vscode.TextEditor,
        comments: GitRoastComment[],
        personality: string,
    ): void {
        const filePath = editor.document.uri.fsPath;

        // Group decorations by severity
        const byType: Record<string, vscode.DecorationOptions[]> = {
            error: [],
            warning: [],
            info: [],
            praise: [],
        };

        const diagnostics: vscode.Diagnostic[] = [];

        for (const comment of comments) {
            // Guard: clamp line number to valid range
            const lineIndex = Math.max(0, Math.min(comment.lineNumber, editor.document.lineCount - 1));
            const line = editor.document.lineAt(lineIndex);
            const range = new vscode.Range(lineIndex, 0, lineIndex, line.text.length);

            // Choose emoji based on severity
            let prefix: string;
            if (comment.severity === 'error' || comment.severity === 'warning') {
                prefix = '🔥';
            } else if (comment.severity === 'info') {
                prefix = '💡';
            } else {
                prefix = '✅';
            }

            const afterContent = `  ${prefix} GitRoast [${personality}]: ${comment.message}`;

            byType[comment.severity].push({
                range,
                renderOptions: {
                    after: { contentText: afterContent },
                },
            });

            // Map to VS Code DiagnosticSeverity
            let diagSeverity: vscode.DiagnosticSeverity;
            if (comment.severity === 'error') {
                diagSeverity = vscode.DiagnosticSeverity.Error;
            } else if (comment.severity === 'warning') {
                diagSeverity = vscode.DiagnosticSeverity.Warning;
            } else {
                diagSeverity = vscode.DiagnosticSeverity.Information;
            }

            const diag = new vscode.Diagnostic(
                range,
                `${prefix} GitRoast [${personality}]: ${comment.message}`,
                diagSeverity,
            );
            diag.source = 'GitRoast';
            diagnostics.push(diag);
        }

        // Apply decoration types
        for (const [sev, decorationType] of this.decorationTypes) {
            editor.setDecorations(decorationType, byType[sev] || []);
        }

        // Update diagnostics for this file
        this.diagnosticCollection.set(editor.document.uri, diagnostics);

        // Store active comments
        this.activeComments.set(filePath, comments);
    }

    /**
     * Clear comments — all files or a specific file.
     */
    clearComments(filePath?: string): void {
        if (filePath) {
            // Clear for one file
            this.activeComments.delete(filePath);
            const uri = vscode.Uri.file(filePath);
            this.diagnosticCollection.delete(uri);

            // Clear decorations in any matching open editor
            for (const editor of vscode.window.visibleTextEditors) {
                if (editor.document.uri.fsPath === filePath) {
                    for (const decorationType of this.decorationTypes.values()) {
                        editor.setDecorations(decorationType, []);
                    }
                }
            }
        } else {
            // Clear everything
            this.activeComments.clear();
            this.diagnosticCollection.clear();

            for (const editor of vscode.window.visibleTextEditors) {
                for (const decorationType of this.decorationTypes.values()) {
                    editor.setDecorations(decorationType, []);
                }
            }
        }
    }

    /**
     * Convert CodeIssue objects (from the Python code analyzer) into GitRoastComments.
     */
    generateCommentsFromIssues(issues: any[], personality: string): GitRoastComment[] {
        return issues.map((issue): GitRoastComment => {
            const lineNumber = (issue.line_number ?? 1) - 1; // Convert 1-indexed to 0-indexed

            // Map issue type to severity
            let severity: GitRoastComment['severity'];
            switch (issue.issue_type) {
                case 'secret':
                    severity = 'error';
                    break;
                case 'complexity':
                case 'bare_except':
                case 'deep_nesting':
                    severity = 'warning';
                    break;
                default:
                    severity = 'info';
            }

            // Format message based on issue type
            let message: string;
            switch (issue.issue_type) {
                case 'secret':
                    message = 'Possible hardcoded secret — rotate this credential NOW';
                    break;
                case 'complexity':
                    message = 'High complexity — consider breaking this into smaller functions';
                    break;
                case 'bare_except':
                    message = 'Bare except — be specific about what you\'re catching';
                    break;
                case 'deep_nesting':
                    message = 'Deep nesting detected — extract this logic into a helper';
                    break;
                case 'no_docstring':
                    message = 'No docstring — future you will be very confused';
                    break;
                case 'unused_import':
                    message = 'Possibly unused import — clean up your imports';
                    break;
                case 'todo':
                    message = 'TODO comment — this is now a permanent feature, isn\'t it?';
                    break;
                default:
                    message = issue.message || `${issue.issue_type} detected`;
            }

            return {
                lineNumber: Math.max(0, lineNumber),
                message,
                severity,
                personality,
            };
        });
    }
}

// ---------------------------------------------------------------------------
// Command registration
// ---------------------------------------------------------------------------

export function registerInlineCommentCommands(
    context: vscode.ExtensionContext,
    manager: InlineCommentManager,
): void {
    // --- Command: Add inline comments ---
    const addCmd = vscode.commands.registerCommand(
        'gitroast.addInlineComments',
        async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('GitRoast: Open a file first');
                return;
            }

            const confirmed = await vscode.window.showInformationMessage(
                'GitRoast will add inline comments to the current file. Continue?',
                'Yes, roast it',
                'Cancel',
            );
            if (confirmed !== 'Yes, roast it') {
                return;
            }

            // Sample comments for demo (in production these come from the code analyzer)
            const demoComments: GitRoastComment[] = [
                {
                    lineNumber: 0,
                    message: 'This file is about to get a code review. Buckle up.',
                    severity: 'info',
                    personality: 'senior_dev',
                },
                {
                    lineNumber: Math.min(5, editor.document.lineCount - 1),
                    message: 'Complexity detected — consider breaking this into smaller functions',
                    severity: 'warning',
                    personality: 'senior_dev',
                },
                {
                    lineNumber: Math.min(10, editor.document.lineCount - 1),
                    message: 'Actually pretty clean here. Don\'t ruin it.',
                    severity: 'praise',
                    personality: 'senior_dev',
                },
            ];

            manager.addComments(editor, demoComments, 'senior_dev');
            vscode.window.showInformationMessage('GitRoast has reviewed your code 🔥');
        },
    );

    // --- Command: Clear inline comments ---
    const clearCmd = vscode.commands.registerCommand(
        'gitroast.clearInlineComments',
        () => {
            manager.clearComments();
            vscode.window.showInformationMessage('Inline comments cleared');
        },
    );

    context.subscriptions.push(addCmd, clearCmd);
}
