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

Documentation should also be *appropriate* in length. For simple functions, a brief docstring is sufficient. For more complex functions or classes, more detailed explanations and examples should be provided.

An example docstring may look like this:

```python

def multiply(a: int, b: int) -> int:
    """
    Multiply two integers `a` and `b`.

    This function takes two integers as input and returns their product.

    Example:
    
    ... code-block:: python

        result = multiply(3, 4)
        print(result)  # Output: 12

    :param a: The first integer to multiply.
    :param b: The second integer to multiply.

    :return: The product of the two integers.
    """
    return a * b

```

## Development Commands

### Testing
- `pytest` - Run all tests using pytest
- `make test` - Run tests via Makefile
- `nox -s test` - Run tests using Nox sessions

**Test Organization:**
- `tests/test_bugs.py` - Test-driven bug reproductions and regression tests. When fixing bugs, create a test case here that reproduces the issue, then verify the fix resolves it. This ensures previously fixed bugs remain fixed.
- `tests/test_functional_*.py` - Tests for functional experiment system components
- `tests/test_cli*.py` - Tests for CLI commands and functionality
- `tests/assets/` - Mock experiments and test fixtures
- `tests/artifacts/` - A folder where test executions can store persistant artifacts such as generated archives or plots

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

### Documentation
- `mkdocs serve` - Start local documentation server at http://127.0.0.1:8000
- `mkdocs build` - Build documentation to `site/` directory
- Documentation sources are in `docs/` with configuration in `mkdocs.yml`

## Architecture

### Core Components

**Experiment Classes:**
- `functional.experiment.Experiment` - Modern functional-style experiment class (primary)

**CLI System:**
- `cli/` package - Refactored modular CLI implementation
  - `cli/main.py` - CLI and ExperimentCLI base classes with utility methods
  - `cli/display.py` - Rich display classes for formatted output
  - `cli/utils.py` - Helper functions (section, subsection)
  - `cli/commands/` - Command implementations via mixins
    - `run.py` - RunCommandsMixin (run, reproduce, inspect commands)
    - `template.py` - TemplateCommandsMixin (template operations)
    - `archive.py` - ArchiveCommandsMixin (archive management)
- `ExperimentCLI` class handles experiment discovery and execution
- Supports parameter overrides, hook management, and archive inspection
- All functionality available via mixin inheritance pattern

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
- `pycomex/cli/` - Refactored CLI package structure
  - `main.py` - Base CLI classes (CLI, ExperimentCLI)
  - `display.py` - Rich display components
  - `utils.py` - Helper functions
  - `commands/` - Command mixin modules (run, template, archive)
- `pycomex/plugins/` - Plugin system for notifications, W&B integration, etc.
- `pycomex/templates/` - Jinja2 templates for code generation
- `tests/` - Comprehensive test suite with assets and examples
- `mkdocs.yml` - MkDocs configuration file (in project root)
- `docs/` - MkDocs documentation markdown files

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