# Getting Started with PyComex VSCode Extension

This guide will walk you through the steps to set up, build, and test the PyComex VSCode extension.

## Prerequisites

Make sure you have the following installed:

1. **Node.js** (v18 or higher)
   ```bash
   node --version  # Should be v18.x or higher
   ```

2. **npm** (comes with Node.js)
   ```bash
   npm --version
   ```

3. **Visual Studio Code** (v1.74.0 or higher)

## Step 1: Install Dependencies

Navigate to the extension directory and install all required npm packages:

```bash
cd vscode_extension
npm install
```

This will install:
- TypeScript compiler
- VSCode extension API types
- ESLint for code linting
- YAML parser (js-yaml)

## Step 2: Compile the Extension

Compile the TypeScript source code to JavaScript:

```bash
npm run compile
```

This creates the `out/` directory with compiled JavaScript files.

Alternatively, you can run in watch mode (automatically recompiles on file changes):

```bash
npm run watch
```

## Step 3: Test the Extension

### Option A: Using F5 (Recommended for Development)

1. Open the `vscode_extension` folder in VS Code:
   ```bash
   code .
   ```

2. Press `F5` to launch the Extension Development Host
   - This opens a new VS Code window with the extension loaded
   - The original window becomes the debugger

3. In the Extension Development Host window:
   - Open a PyComex project (or navigate to the pycomex examples folder)
   - Check if `results` folders show the custom beaker icon
   - Open `pycomex/examples/09_experiment_config.yml`
   - You should see a green **▶ Run** button in the top-right corner
   - Click it to test running the experiment

### Option B: Install as VSIX Package

If you want to install the extension permanently in your VS Code:

1. Install the VSCE packaging tool:
   ```bash
   npm install -g vsce
   ```

2. Package the extension:
   ```bash
   vsce package
   ```
   This creates `pycomex-vscode-0.1.0.vsix`

3. Install the extension:
   ```bash
   code --install-extension pycomex-vscode-0.1.0.vsix
   ```

4. Restart VS Code

5. Enable the PyComex icon theme:
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
   - Type "File Icon Theme"
   - Select "PyComex Icons"

## Step 4: Verify Features

### Feature 1: Custom Results Folder Icons

1. Open any folder that contains a `results` or `archive` subdirectory
2. The folder should display with a blue beaker icon instead of the default folder icon

### Feature 2: Run Experiment Button

1. Open or create a PyComex experiment config YAML file with this structure:
   ```yaml
   extend: 02_basic.py
   parameters:
     NUM_WORDS: 500
     REPETITIONS: 5
   ```

2. You should see a green **▶ Run** button appear in the top-right corner of the editor
3. Click the button to execute the experiment
4. A terminal will open and run: `pycomex run <config-file.yml>`

## Development Workflow

### Making Changes

1. Edit TypeScript files in `src/`
2. If running `npm run watch`, changes auto-compile
3. Press `Ctrl+R` (or `Cmd+R`) in the Extension Development Host to reload
4. Test your changes

### Debugging

- Set breakpoints in TypeScript files
- Press `F5` to start debugging
- Breakpoints will be hit when the extension code executes
- Use the Debug Console in the main VS Code window

### Linting

Check code quality:

```bash
npm run lint
```

## Project Structure Quick Reference

```
vscode_extension/
├── src/
│   ├── extension.ts              # Entry point (activate/deactivate)
│   ├── codelens/
│   │   └── configRunProvider.ts  # Detects YAML configs, adds run button
│   └── commands/
│       └── runExperiment.ts      # Executes pycomex run command
├── icons/
│   ├── results-folder.svg        # Closed folder icon
│   └── results-folder-open.svg   # Open folder icon
├── .vscode/
│   ├── launch.json               # Debug configuration
│   └── tasks.json                # Build tasks
├── out/                          # Compiled JavaScript (generated)
├── node_modules/                 # Dependencies (generated)
├── package.json                  # Extension manifest
├── tsconfig.json                 # TypeScript configuration
└── README.md                     # User documentation
```

## Troubleshooting

### "Cannot find module 'vscode'"

Run `npm install` to install all dependencies.

### Extension doesn't activate

Check that `activationEvents` in `package.json` includes `"onLanguage:yaml"`.

### Run button doesn't appear

1. Make sure the YAML file contains both `extend:` and `parameters:` fields
2. Check the Output panel → "Extension Host" for errors
3. Verify the file language is set to "YAML" (bottom right corner)
4. The button only appears for files that are detected as PyComex configs
5. Try saving the file or typing to trigger the detection

### Icons don't show

1. Enable the PyComex icon theme: `Ctrl+Shift+P` → "File Icon Theme" → "PyComex Icons"
2. Check that the folder is named exactly `results` or `archive` (case-sensitive)

## Next Steps

- Test the extension with real PyComex projects
- Report any bugs or suggestions
- Consider adding more features (see README for ideas)
- Publish to the VS Code Marketplace (requires publisher account)

## Publishing to Marketplace (Optional)

1. Create a publisher account at https://marketplace.visualstudio.com/
2. Get a Personal Access Token from Azure DevOps
3. Login with vsce:
   ```bash
   vsce login <publisher-name>
   ```
4. Publish:
   ```bash
   vsce publish
   ```

---

**Happy coding with PyComex!**
