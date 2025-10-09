import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

/**
 * Finds the virtual environment directory in the workspace.
 *
 * Searches for common venv directory names in order of preference:
 * 1. .venv (PyComex default)
 * 2. venv
 * 3. env
 *
 * Also checks the Python interpreter path from VS Code settings.
 *
 * @param workspaceFolder The workspace folder to search in
 * @returns The path to the venv directory, or null if not found
 */
function findVirtualEnv(workspaceFolder: string): string | null {
    // Common venv directory names, in order of preference
    const venvNames = ['.venv', 'venv', 'env'];

    // Check common venv locations
    for (const venvName of venvNames) {
        const venvPath = path.join(workspaceFolder, venvName);
        if (fs.existsSync(venvPath)) {
            // Verify it's actually a venv by checking for activate script
            const isWindows = process.platform === 'win32';
            const activateScript = isWindows
                ? path.join(venvPath, 'Scripts', 'activate.bat')
                : path.join(venvPath, 'bin', 'activate');

            if (fs.existsSync(activateScript)) {
                return venvPath;
            }
        }
    }

    // Try to get Python interpreter path from VS Code settings
    const pythonConfig = vscode.workspace.getConfiguration('python');
    const pythonPath = pythonConfig.get<string>('defaultInterpreterPath');

    if (pythonPath) {
        // Check if the Python path is inside a venv
        // Typical venv structure: /path/to/venv/bin/python or /path/to/venv/Scripts/python.exe
        const pythonDir = path.dirname(pythonPath);
        const parentDir = path.dirname(pythonDir);

        // Check if parent directory looks like a venv
        const dirName = path.basename(pythonDir);
        if (dirName === 'bin' || dirName === 'Scripts') {
            const activateScript = process.platform === 'win32'
                ? path.join(pythonDir, 'activate.bat')
                : path.join(pythonDir, 'activate');

            if (fs.existsSync(activateScript)) {
                return parentDir;
            }
        }
    }

    return null;
}

/**
 * Gets the activation command for a virtual environment.
 *
 * Returns the appropriate activation command based on the platform and shell type.
 *
 * @param venvPath The path to the virtual environment directory
 * @returns The activation command string
 */
function getActivationCommand(venvPath: string): string {
    const isWindows = process.platform === 'win32';

    if (isWindows) {
        // Windows: Try PowerShell first, fall back to CMD
        // VS Code terminals on Windows typically use PowerShell
        const pwshScript = path.join(venvPath, 'Scripts', 'Activate.ps1');
        const cmdScript = path.join(venvPath, 'Scripts', 'activate.bat');

        if (fs.existsSync(pwshScript)) {
            // PowerShell activation
            return `& "${pwshScript}"`;
        } else if (fs.existsSync(cmdScript)) {
            // CMD activation
            return `"${cmdScript}"`;
        }
    } else {
        // Linux/macOS: Use source command
        const activateScript = path.join(venvPath, 'bin', 'activate');
        if (fs.existsSync(activateScript)) {
            return `source "${activateScript}"`;
        }

        // Check for Fish shell
        const fishScript = path.join(venvPath, 'bin', 'activate.fish');
        if (fs.existsSync(fishScript)) {
            return `source "${fishScript}"`;
        }
    }

    // Fallback: basic source command
    const relativePath = path.relative(process.cwd(), venvPath);
    return isWindows
        ? `"${path.join(relativePath, 'Scripts', 'activate.bat')}"`
        : `source "${path.join(relativePath, 'bin', 'activate')}"`;
}

/**
 * Runs a PyComex experiment configuration file.
 *
 * This function creates a new terminal, activates the virtual environment if found,
 * and executes the pycomex CLI command to run the experiment defined in the given
 * YAML configuration file.
 *
 * @param uri The URI of the experiment config YAML file to run.
 */
export function runExperimentConfig(uri: vscode.Uri): void {

    // Get the file path from the URI
    const filePath = uri.fsPath;
    const fileName = path.basename(filePath);
    const fileDir = path.dirname(filePath);

    // Find workspace folder
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(uri);
    const workspacePath = workspaceFolder?.uri.fsPath || fileDir;

    // Try to find virtual environment
    const venvPath = findVirtualEnv(workspacePath);

    // Create a terminal for running the experiment
    const terminal = vscode.window.createTerminal({
        name: `PyComex: ${fileName}`,
        cwd: fileDir
    });

    // Show the terminal
    terminal.show();

    // If venv found, activate it first
    if (venvPath) {
        const activateCmd = getActivationCommand(venvPath);
        terminal.sendText(activateCmd);

        // Show info about venv activation
        const venvName = path.basename(venvPath);
        vscode.window.showInformationMessage(
            `Activated virtual environment: ${venvName}`
        );
    }

    // Send the pycomex run command
    // Using quotes to handle file paths with spaces
    terminal.sendText(`pycomex run "${filePath}"`);

    // Show info message
    vscode.window.showInformationMessage(
        `Running PyComex experiment: ${fileName}`
    );
}

/**
 * Runs a PyComex experiment from the currently active YAML file.
 *
 * This is a convenience command that can be triggered from the command palette
 * when a PyComex config YAML file is open.
 */
export function runExperimentFromActiveFile(): void {

    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        vscode.window.showErrorMessage('No active file open');
        return;
    }

    const document = editor.document;

    // Verify it's a YAML file
    if (document.languageId !== 'yaml') {
        vscode.window.showErrorMessage('Active file is not a YAML file');
        return;
    }

    // Verify it's a PyComex config (has extend: and parameters:)
    const text = document.getText();
    const hasExtend = /^extend:/m.test(text);
    const hasParameters = /^parameters:/m.test(text);

    if (!hasExtend || !hasParameters) {
        vscode.window.showErrorMessage(
            'Active file does not appear to be a PyComex experiment config'
        );
        return;
    }

    // Run the experiment
    runExperimentConfig(document.uri);
}
