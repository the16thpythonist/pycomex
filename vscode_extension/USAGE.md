# PyComex VSCode Extension - Developer Documentation

This document provides technical information for developers who want to contribute to or understand the PyComex VSCode extension.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Building the Extension](#building-the-extension)
- [Testing and Debugging](#testing-and-debugging)
- [Architecture](#architecture)
- [Creating a Release](#creating-a-release)
- [Contributing](#contributing)

## Development Setup

### Prerequisites

- **Node.js** (v18 or higher) - [Download](https://nodejs.org/)
- **npm** (comes with Node.js)
- **Visual Studio Code** (v1.74.0 or higher)
- **Python 3.8+** with PyComex installed for testing

### Initial Setup

1. **Clone the repository and navigate to the extension directory:**
   ```bash
   cd vscode_extension
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

   This installs:
   - TypeScript compiler
   - VSCode extension API types
   - ESLint for linting
   - js-yaml for YAML parsing

3. **Compile the TypeScript code:**
   ```bash
   npm run compile
   ```

4. **Open the extension in VS Code:**
   ```bash
   code .
   ```

## Project Structure

```
vscode_extension/
├── src/                              # TypeScript source code
│   ├── extension.ts                  # Main entry point (activate/deactivate)
│   ├── codelens/
│   │   └── configRunProvider.ts      # CodeLens provider for YAML configs
│   └── commands/
│       └── runExperiment.ts          # Run experiment command handlers
├── icons/                            # Custom folder icons
│   ├── results-folder.svg            # Closed folder icon
│   └── results-folder-open.svg       # Open folder icon
├── .vscode/                          # VS Code workspace configuration
│   ├── launch.json                   # Debug launch configuration
│   └── tasks.json                    # Build task definitions
├── out/                              # Compiled JavaScript (generated)
│   └── (generated .js and .map files)
├── node_modules/                     # npm dependencies (generated)
├── package.json                      # Extension manifest
├── pycomex-icon-theme.json          # File icon theme definition
├── tsconfig.json                    # TypeScript compiler configuration
├── .eslintrc.json                   # ESLint configuration
├── .vscodeignore                    # Files to exclude from VSIX package
├── .gitignore                       # Git ignore rules
├── README.md                        # User-facing documentation
├── USAGE.md                         # This file
└── GETTING_STARTED.md               # Step-by-step setup guide
```

### Key Files Explained

#### `package.json`
The extension manifest defines:
- Extension metadata (name, version, description)
- VS Code engine compatibility
- Activation events (when the extension loads)
- Contributed features (commands, menus, icon themes)
- npm scripts for building and testing

#### `src/extension.ts`
The main entry point that:
- Implements `activate()` and `deactivate()` lifecycle hooks
- Registers commands and providers
- Manages context keys for conditional UI elements
- Listens for editor and document changes

#### `src/commands/runExperiment.ts`
Command handlers that:
- Detect and activate Python virtual environments (`.venv`, `venv`, `env`)
- Execute PyComex experiments via terminal
- Validate YAML config files
- Handle both CodeLens and menu invocations
- Support cross-platform activation scripts (Windows, Linux, macOS)

#### `src/codelens/configRunProvider.ts`
CodeLens provider that:
- Detects PyComex config YAML files
- Provides inline run buttons (optional feature)

## Building the Extension

### Available npm Scripts

```bash
# Compile TypeScript to JavaScript
npm run compile

# Watch mode - automatically recompile on file changes
npm run watch

# Lint TypeScript code
npm run lint

# Prepare for publishing (runs compile)
npm run vscode:prepublish
```

### TypeScript Configuration

The `tsconfig.json` is configured for:
- **Target**: ES2020
- **Module**: CommonJS (required for VS Code extensions)
- **Strict mode**: Enabled for better type safety
- **Source maps**: Enabled for debugging

### Compilation Output

Compiled files are written to the `out/` directory:
- `out/extension.js` - Main extension code
- `out/commands/*.js` - Command implementations
- `out/codelens/*.js` - Provider implementations
- `*.js.map` files - Source maps for debugging

## Testing and Debugging

### Running the Extension in Development

1. **Open the extension folder in VS Code:**
   ```bash
   code .
   ```

2. **Start the debugger:**
   - Press `F5` or select "Run > Start Debugging"
   - This launches a new VS Code window called "Extension Development Host"

3. **Test the extension:**
   - In the Extension Development Host window, open a PyComex project
   - Test folder icons (look for `results` or `archive` folders)
   - Open a PyComex YAML config file
   - Verify the green run button appears
   - Click the button to test execution

### Debugging Tips

- **Set breakpoints** in TypeScript files - they work with source maps
- **Use the Debug Console** in the main VS Code window to inspect variables
- **Check the Output panel** → "Extension Host" for console logs and errors
- **Reload the Extension Development Host** with `Ctrl+R` (or `Cmd+R`) after code changes

### Watch Mode for Rapid Development

```bash
npm run watch
```

This automatically recompiles TypeScript files when you save. After making changes:
1. Save the file
2. Press `Ctrl+R` (or `Cmd+R`) in the Extension Development Host
3. Test your changes

## Architecture

### How File Detection Works

The extension detects PyComex config files using a multi-layered approach:

1. **Language Check**: Verifies the file is YAML
2. **Content Analysis**: Searches for `extend:` and `parameters:` using regex:
   ```typescript
   const hasExtend = /^extend:/m.test(text);
   const hasParameters = /^parameters:/m.test(text);
   ```
3. **Context Key**: Sets `pycomex.isConfigFile` context for UI control

### Context System

The extension uses VS Code's context system to conditionally show the run button:

```typescript
// Set context when file is detected
vscode.commands.executeCommand('setContext', 'pycomex.isConfigFile', true);
```

```json
// package.json menu contribution
"when": "resourceLangId == yaml && pycomex.isConfigFile"
```

### Event Listeners

The extension listens for:
- **`onDidChangeActiveTextEditor`**: Updates context when switching files
- **`onDidChangeTextDocument`**: Updates context when editing (dynamic detection)

### Command Registration

Commands are registered in `activate()`:

```typescript
vscode.commands.registerCommand('pycomex.runConfig', (uri?) => {
    // Handle both menu button (no uri) and CodeLens (with uri)
    if (uri) {
        runExperimentConfig(uri);
    } else {
        runExperimentFromActiveFile();
    }
});
```

### Icon Theme System

The `pycomex-icon-theme.json` maps folder names to SVG icons:

```json
{
  "folderNames": {
    "results": "_pycomex_results"
  },
  "iconDefinitions": {
    "_pycomex_results": {
      "iconPath": "./icons/results-folder.svg"
    }
  }
}
```

### Virtual Environment Detection and Activation

The extension automatically detects and activates Python virtual environments before running experiments. This ensures PyComex and its dependencies are available.

#### Detection Strategy

The `findVirtualEnv()` function searches for virtual environments in this order:

1. **Common venv directories** in the workspace:
   - `.venv` (PyComex default, as specified in CLAUDE.md)
   - `venv`
   - `env`

2. **VS Code Python configuration**: Checks `python.defaultInterpreterPath` setting to see if it points to a venv

3. **Verification**: Each candidate is verified by checking for the existence of activation scripts:
   - Linux/macOS: `bin/activate`
   - Windows: `Scripts/activate.bat` or `Scripts/Activate.ps1`

#### Activation Commands by Platform

The `getActivationCommand()` function generates platform-specific activation commands:

**Windows:**
```typescript
// PowerShell (default on Windows)
& "C:\path\to\.venv\Scripts\Activate.ps1"

// Command Prompt (fallback)
"C:\path\to\.venv\Scripts\activate.bat"
```

**Linux/macOS:**
```typescript
// Bash/Zsh
source "/path/to/.venv/bin/activate"

// Fish shell (if detected)
source "/path/to/.venv/bin/activate.fish"
```

#### Execution Flow

When running an experiment:

1. Determine workspace folder from the config file's location
2. Search for virtual environment using `findVirtualEnv()`
3. If venv found:
   - Generate activation command with `getActivationCommand()`
   - Send activation command to terminal
   - Show notification: "Activated virtual environment: .venv"
4. Send `pycomex run` command
5. If no venv found, run `pycomex run` directly (assumes system PATH)

#### Example Terminal Commands

**With venv (Linux/macOS):**
```bash
source "/path/to/project/.venv/bin/activate"
pycomex run "/path/to/config.yml"
```

**With venv (Windows PowerShell):**
```powershell
& "C:\path\to\project\.venv\Scripts\Activate.ps1"
pycomex run "C:\path\to\config.yml"
```

**Without venv:**
```bash
pycomex run "/path/to/config.yml"
```

#### Implementation Notes

- The extension uses Node.js `fs.existsSync()` to check for venv directories and activation scripts
- Platform detection uses `process.platform === 'win32'` for Windows
- All file paths are properly quoted to handle spaces
- The activation and run commands are sent as separate terminal commands for reliability

## Creating a Release

### Packaging the Extension

1. **Install VSCE (Visual Studio Code Extension Manager):**
   ```bash
   npm install -g vsce
   ```

2. **Package the extension:**
   ```bash
   vsce package
   ```

   This creates `pycomex-vscode-0.1.0.vsix`

3. **Test the VSIX locally:**
   ```bash
   code --install-extension pycomex-vscode-0.1.0.vsix
   ```

### Publishing to the Marketplace

1. **Create a publisher account** at [Visual Studio Marketplace](https://marketplace.visualstudio.com/)

2. **Get a Personal Access Token** from [Azure DevOps](https://dev.azure.com/)

3. **Login with VSCE:**
   ```bash
   vsce login <publisher-name>
   ```

4. **Publish the extension:**
   ```bash
   vsce publish
   ```

### Version Bumping

Update the version in `package.json`:

```json
{
  "version": "0.2.0"
}
```

Or use npm:
```bash
npm version patch  # 0.1.0 -> 0.1.1
npm version minor  # 0.1.0 -> 0.2.0
npm version major  # 0.1.0 -> 1.0.0
```

## Contributing

### Code Style

- Follow TypeScript best practices
- Use ESLint for linting: `npm run lint`
- Add JSDoc comments for public functions
- Use meaningful variable and function names

### Pull Request Process

1. Fork the PyComex repository
2. Create a feature branch
3. Make your changes in the `vscode_extension/` directory
4. Test thoroughly using F5 debugging
5. Run `npm run lint` to check code style
6. Submit a pull request with a clear description

### Adding New Features

When adding features:
1. Update `package.json` with new commands/contributions
2. Implement the feature in `src/`
3. Update `README.md` with user-facing documentation
4. Update this `USAGE.md` with technical details
5. Add to the "Planned Features" → "Implemented Features" in README

### Testing Checklist

Before submitting changes:
- [ ] Extension compiles without errors (`npm run compile`)
- [ ] No linting errors (`npm run lint`)
- [ ] Tested in Extension Development Host (F5)
- [ ] Run button appears for valid PyComex configs
- [ ] Folder icons display correctly
- [ ] Terminal opens and runs pycomex command
- [ ] Works with both uppercase/lowercase folder names
- [ ] No errors in Extension Host output panel

## Troubleshooting Development Issues

### "Cannot find module 'vscode'"

**Solution**: Run `npm install` to install dependencies including `@types/vscode`.

### Extension doesn't activate in development

**Solution**: Check `activationEvents` in `package.json` - should include `"onLanguage:yaml"`.

### Changes not reflected after F5

**Solution**:
1. Run `npm run compile` to rebuild
2. Press `Ctrl+R` (or `Cmd+R`) in Extension Development Host to reload
3. Or use `npm run watch` for automatic rebuilding

### Breakpoints not working

**Solution**: Ensure source maps are enabled in `tsconfig.json`:
```json
{
  "compilerOptions": {
    "sourceMap": true
  }
}
```

### Run button doesn't appear

**Solution**:
1. Check that the YAML file has both `extend:` and `parameters:`
2. Verify context key is being set (check Debug Console)
3. Look for errors in Extension Host output panel

## Additional Resources

- [VS Code Extension API](https://code.visualstudio.com/api)
- [VS Code Extension Samples](https://github.com/microsoft/vscode-extension-samples)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [PyComex Documentation](https://pycomex.readthedocs.io)

---

For step-by-step setup instructions for new developers, see [GETTING_STARTED.md](GETTING_STARTED.md).
