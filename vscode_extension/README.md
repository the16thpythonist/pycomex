# PyComex VSCode Extension

A Visual Studio Code extension for [PyComex](https://github.com/the16thpythonist/pycomex) - Python Computational Experiments framework.

## Features

### 🧪 Custom Icons for Results Folders

Folders named `results` or `archive` in your PyComex projects will automatically display with a distinctive beaker icon, making it easy to identify experiment output directories.

### ▶️ Run Experiment from Config Files

When you open a PyComex experiment configuration YAML file (containing `extend:` and `parameters:` fields), a green **Run** button appears in the top-right corner of the editor - just like when you open a Python file. Click it to run the experiment directly from the editor!

The extension automatically detects and activates your Python virtual environment (`.venv`, `venv`, or `env`) before running the experiment.

## Requirements

- Visual Studio Code 1.74.0 or higher
- Python 3.8 or higher
- PyComex installed and available in your PATH (`pip install pycomex`)

## Installation

### From VSCode Marketplace

1. Open VS Code
2. Press `Ctrl+Shift+X` (or `Cmd+Shift+X` on Mac) to open Extensions
3. Search for "PyComex"
4. Click **Install**

### From VSIX File

If you have a `.vsix` file:

```bash
code --install-extension pycomex-vscode-0.1.0.vsix
```

## Usage

### Running Experiments

1. Open any PyComex experiment config YAML file
2. Look for the green **▶ Run** button in the top-right corner of the editor
3. Click the button to run the experiment in a new terminal

The extension will automatically:
- Detect your virtual environment (`.venv`, `venv`, or `env`)
- Activate the virtual environment
- Run the `pycomex run` command

**Example config file:**
```yaml
extend: 02_basic.py
parameters:
  NUM_WORDS: 500
  REPETITIONS: 5
```

**Note:** If no virtual environment is found, the command runs directly assuming PyComex is in your system PATH.

### Enabling Folder Icons

To enable the PyComex icon theme:

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "File Icon Theme"
3. Select "PyComex Icons"

Or via settings:
1. Open VS Code settings (`Ctrl+,` or `Cmd+,`)
2. Search for "File Icon Theme"
3. Select "PyComex Icons" from the dropdown

### Available Commands

Access these via Command Palette (`Ctrl+Shift+P`):

- **PyComex: Run Experiment Config** - Run the current PyComex experiment config file

## Known Issues

None currently. Please report issues on the [PyComex GitHub repository](https://github.com/the16thpythonist/pycomex/issues).

## Planned Features

Future releases may include:
- Code snippets for common PyComex patterns
- IntelliSense support for experiment decorators
- Sidebar panel for browsing experiments and archives
- Interactive parameter override UI
- Archive viewer with visualization support

## Contributing

Contributions are welcome! This extension is part of the PyComex project.

For development setup and technical documentation, see [USAGE.md](USAGE.md).

## Release Notes

### 0.1.0

Initial release with two core features:
- Custom folder icons for `results` and `archive` directories
- Green run button for PyComex experiment config YAML files

## License

MIT License - See the PyComex repository for details.

## Links

- [PyComex GitHub](https://github.com/the16thpythonist/pycomex)
- [PyComex Documentation](https://pycomex.readthedocs.io)
- [Report Issues](https://github.com/the16thpythonist/pycomex/issues)

---

**Enjoy using PyComex!** 🧪
