# VSCode Extension

PyComex provides an official Visual Studio Code extension that streamlines experiment development by integrating experiment execution and archive visualization directly into your editor workflow.

## Motivation

When developing computational experiments, you typically work with two key elements: **experiment configuration files** that define parameters and inheritance, and **archive directories** that store experimental results. The PyComex VSCode extension enhances your development experience by making these elements immediately recognizable and actionable within your editor.

Rather than switching between your editor and terminal to run experiments, or hunting through directories to identify which folders contain archived results, the extension brings these capabilities directly into the VSCode interface. This integration reduces friction in the experimental workflow, allowing you to focus on the science rather than the mechanics.

## Installation

### From VSCode Marketplace

Open the Extensions view in VSCode (`Ctrl+Shift+X` or `Cmd+Shift+X`), search for "PyComex", and click Install.

### From VSIX Package

If you have a `.vsix` file:

```bash
code --install-extension pycomex-vscode-0.1.0.vsix
```

## Features

### 🧪 Experiment Archive Visualization

The extension adds distinctive beaker badges (🗃️) and dark teal coloring to PyComex archive directories, making experiment results immediately identifiable in your workspace. Folders named `results` or `archive` automatically display with these visual indicators alongside your existing icon theme, eliminating the need to mentally track which directories contain experimental outputs.

**Note:** Visual indicators appear automatically - no configuration needed. Works with any VSCode icon theme.

### ▶️ Quick Experiment Execution

When you open a PyComex experiment configuration YAML file (identified by the presence of `extend:` and `parameters:` fields), a green **Run** button appears in the top-right corner of the editor—identical to the interface Python users expect. Clicking this button executes your experiment directly without leaving VSCode.

**Example configuration file:**
```yaml
extend: base_experiment.py
parameters:
  LEARNING_RATE: 0.01
  EPOCHS: 100
```

The extension intelligently handles your Python environment by automatically detecting and activating virtual environments (`.venv`, `venv`, or `env`) before executing the experiment. This ensures that PyComex and your dependencies are properly loaded without manual intervention.

**Execution flow:**
1. Opens a new terminal in the config file's directory
2. Activates the detected virtual environment (if present)
3. Runs `pycomex run <config-file.yml>`
4. Displays execution output in the integrated terminal

## Configuration Detection

The extension continuously monitors your active files and automatically enables the run button when it detects valid PyComex configuration files. Detection occurs dynamically as you edit, so the button appears immediately when you add the required `extend:` and `parameters:` fields to a YAML file.

For virtual environment detection, the extension searches your workspace in this order:
1. `.venv` (PyComex's default convention)
2. `venv`
3. `env`
4. VSCode's configured Python interpreter path

If no virtual environment is found, the extension runs `pycomex run` directly, assuming PyComex is available in your system PATH.

## Next Steps

- Explore the [Introduction](introduction.md) to learn about PyComex experiment structure
- Review [Experiment Inheritance](basics_hooks.md) to understand configuration file extension
- Visit the [PyComex GitHub repository](https://github.com/the16thpythonist/pycomex) for the latest updates
- Check the [extension source code](https://github.com/the16thpythonist/pycomex/tree/main/vscode_extension) to contribute or report issues
