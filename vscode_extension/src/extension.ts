import * as vscode from 'vscode';
import { PyComexConfigCodeLensProvider } from './codelens/configRunProvider';
import { runExperimentConfig, runExperimentFromActiveFile } from './commands/runExperiment';

/**
 * Checks if a document is a PyComex experiment config file.
 * A valid PyComex config YAML file must contain both "extend:" and "parameters:" fields.
 *
 * @param document The document to check
 * @returns true if the document is a PyComex config file
 */
function isPyComexConfigFile(document: vscode.TextDocument | undefined): boolean {
    if (!document || document.languageId !== 'yaml') {
        return false;
    }

    const text = document.getText();
    const hasExtend = /^extend:/m.test(text);
    const hasParameters = /^parameters:/m.test(text);

    return hasExtend && hasParameters;
}

/**
 * Updates the context key that indicates whether the active file is a PyComex config.
 * This controls the visibility of the run button in the editor title bar.
 *
 * @param editor The active text editor
 */
function updatePyComexContext(editor: vscode.TextEditor | undefined): void {
    const isConfig = isPyComexConfigFile(editor?.document);
    vscode.commands.executeCommand('setContext', 'pycomex.isConfigFile', isConfig);
}

/**
 * This method is called when the extension is activated.
 * The extension is activated the very first time a command is executed or
 * when a YAML file is opened (as defined in activationEvents in package.json).
 *
 * @param context The extension context provided by VS Code
 */
export function activate(context: vscode.ExtensionContext) {

    console.log('PyComex extension is now active!');

    // Set initial context based on the active editor
    updatePyComexContext(vscode.window.activeTextEditor);

    // Update context when the active editor changes
    const editorChangeListener = vscode.window.onDidChangeActiveTextEditor(editor => {
        updatePyComexContext(editor);
    });

    // Update context when the document content changes (user types)
    const documentChangeListener = vscode.workspace.onDidChangeTextDocument(event => {
        if (event.document === vscode.window.activeTextEditor?.document) {
            updatePyComexContext(vscode.window.activeTextEditor);
        }
    });

    // Register the CodeLens provider for YAML files
    const codeLensProvider = vscode.languages.registerCodeLensProvider(
        { language: 'yaml', scheme: 'file' },
        new PyComexConfigCodeLensProvider()
    );

    // Register the command to run an experiment config
    // This command now uses the active editor's document
    const runConfigCommand = vscode.commands.registerCommand(
        'pycomex.runConfig',
        (uri?: vscode.Uri) => {
            // If URI is provided (from CodeLens), use it
            // Otherwise, use the active editor's URI
            if (uri) {
                runExperimentConfig(uri);
            } else {
                runExperimentFromActiveFile();
            }
        }
    );

    // Register the command to run from active file (can be triggered from command palette)
    const runActiveFileCommand = vscode.commands.registerCommand(
        'pycomex.runActiveFile',
        runExperimentFromActiveFile
    );

    // Add all disposables to the context subscriptions
    // This ensures they are properly cleaned up when the extension is deactivated
    context.subscriptions.push(
        editorChangeListener,
        documentChangeListener,
        codeLensProvider,
        runConfigCommand,
        runActiveFileCommand
    );

    // Show a message when the extension is activated (optional, for debugging)
    // vscode.window.showInformationMessage('PyComex extension loaded!');
}

/**
 * This method is called when the extension is deactivated.
 * Use this to clean up any resources if necessary.
 */
export function deactivate() {
    console.log('PyComex extension is now deactivated');
}
