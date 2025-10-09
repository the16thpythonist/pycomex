import * as vscode from 'vscode';

/**
 * CodeLens provider for PyComex experiment config YAML files.
 *
 * This provider detects YAML files that contain PyComex experiment configurations
 * (identified by the presence of "extend:" and "parameters:" fields) and provides
 * a "Run Experiment" CodeLens button at the top of the file.
 */
export class PyComexConfigCodeLensProvider implements vscode.CodeLensProvider {

    /**
     * Provides CodeLenses for a given document.
     *
     * @param document The document in which the command was invoked.
     * @returns An array of CodeLens objects or a thenable that resolves to such.
     */
    async provideCodeLenses(
        document: vscode.TextDocument
    ): Promise<vscode.CodeLens[]> {

        // Only process YAML files
        if (document.languageId !== 'yaml') {
            return [];
        }

        const text = document.getText();

        // Check if this is a PyComex experiment config file
        // by looking for required fields: "extend:" and "parameters:"
        const hasExtend = /^extend:/m.test(text);
        const hasParameters = /^parameters:/m.test(text);

        if (hasExtend && hasParameters) {
            // Create a CodeLens at the top of the file (line 0, column 0)
            const range = new vscode.Range(0, 0, 0, 0);

            const command: vscode.Command = {
                title: "▶ Run Experiment",
                command: "pycomex.runConfig",
                arguments: [document.uri]
            };

            return [new vscode.CodeLens(range, command)];
        }

        return [];
    }
}
