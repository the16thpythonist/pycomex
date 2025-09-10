# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyComex (Python Computational Experiments) is a microframework for creating, executing, and managing computational experiments in Python. It provides automatic folder structure creation, metadata tracking, file artifact management, and boilerplate analysis code generation.

## Virtual Environment

This project uses a virtual environment which should be activated before running any command line tools or scripts.
To activate the virtual environment, run:

```bash
source .venv/bin/activate
```

## Development Guidelines

### Docstrings

Docstrings should use the ReStructuredText (reST) format. This is important for generating documentation and for consistency across the codebase. Docstrings should always start with a one-line summary followed by a more detailed paragraph - also including usage examples, for instance. If appropriate, docstrings should not only describe a method or function but also shed some light on the design rationale.

## Development Commands

### Testing
- `pytest` - Run all tests using pytest
- `make test` - Run tests via Makefile
- `nox -s test` - Run tests using Nox sessions

### Building and Publishing
- `nox -s build` - Build package using Nox (includes testing wheel)
- `uv build --python=3.10` - Build with uv
- `make dist` - Build source and wheel packages
- `twine upload dist/*` - Upload to PyPI
- `bump-my-version bump [patch|minor|major]` - Version bumping

### CLI Usage
- `pycomex` or `pycx` - Main CLI entry points
- `pycomex template experiment` - Create new experiment from template
- `pycomex archive` - Interact with experiment results

## Architecture

### Core Components

**Experiment Classes:**
- `functional.experiment.Experiment` - Modern functional-style experiment class (primary)

**CLI System:**
- `cli.py` - Rich-based command line interface with experiment management
- `ExperimentCLI` class handles experiment discovery and execution
- Supports parameter overrides, hook management, and archive inspection

**Configuration:**
- `config.py` - Global configuration management using Pydantic
- `functional.parameter.ActionableParameterType` - Parameter type annotations system

### Key Patterns

**Experiment Structure:**
- Experiments are Python modules with uppercase global variables as parameters
- Main function decorated with `@Experiment()` decorator
- `__DEBUG__ = True` creates reusable debug archives instead of timestamped ones

**File Organization:**
- `pycomex/` - Main package code
- `pycomex/functional/` - Modern functional experiment system
- `pycomex/plugins/` - Plugin system for notifications, W&B integration, etc.
- `pycomex/templates/` - Jinja2 templates for code generation
- `tests/` - Comprehensive test suite with assets and examples
- `docs/` - MkDocs documentation source

**Archive System:**
- Experiments create nested folder structures: `base_path/namespace/timestamp/`
- Auto-generated files: `experiment_meta.json`, `experiment_data.json`, `experiment_out.log`
- Analysis boilerplate automatically created as `analysis.py`

### Plugin System
- Located in `pycomex/plugins/`
- Supports notifications, Weights & Biases integration
- Plugin base class in `plugin.py`

### Template System
- Jinja2 templates in `pycomex/templates/`
- Used for generating experiment boilerplate and analysis code
- CLI `template` command group for creating new experiments