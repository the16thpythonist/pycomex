"""
PyComex CLI package.

This package provides the command-line interface for PyComex. It was refactored
from a monolithic 2,656-line cli.py file into a modular package structure for
better maintainability, code organization, and easier navigation.

Quick Start for AI Agents
==========================

If you're looking for specific CLI functionality:

- **Main CLI logic**: See ``main.py`` for CLI and ExperimentCLI base classes
- **Command implementations**: See ``commands/`` subpackage (run, template, archive)
- **Display/formatting**: See ``display.py`` for Rich output components
- **Helper functions**: See ``utils.py`` for section/subsection helpers

Package Organization
====================

This package uses a **mixin pattern** to organize commands::

    pycomex/cli/
    ├── __init__.py              # This file: public API exports
    ├── main.py                  # CLI and ExperimentCLI classes + utilities
    ├── display.py               # Rich display components
    ├── utils.py                 # Helper functions
    └── commands/
        ├── __init__.py         # Mixin exports
        ├── run.py              # RunCommandsMixin
        ├── template.py         # TemplateCommandsMixin
        └── archive.py          # ArchiveCommandsMixin

Command Groups
==============

**Run Commands** (commands/run.py):
    - ``pycomex run <file>`` - Execute experiments
    - ``pycomex reproduce <archive>`` - Reproduce from archive
    - ``pycomex inspect <path>`` - Inspect experiment

**Template Commands** (commands/template.py):
    - ``pycomex template experiment`` - Create new experiment
    - ``pycomex template extend`` - Extend existing experiment
    - ``pycomex template config`` - Create config file
    - ``pycomex template validate`` - Validate config
    - ``pycomex template analysis`` - Create analysis notebook

**Archive Commands** (commands/archive.py):
    - ``pycomex archive list`` - List experiments
    - ``pycomex archive overview`` - Show statistics
    - ``pycomex archive tail`` - Show recent experiments
    - ``pycomex archive delete`` - Delete experiments
    - ``pycomex archive compress`` - Create ZIP archive
    - ``pycomex archive info`` - Detailed statistics
    - ``pycomex archive modify`` - Modify parameters/metadata

Architecture Details
====================

The main ``CLI`` class in ``main.py`` combines all command mixins::

    class CLI(RunCommandsMixin, TemplateCommandsMixin, ArchiveCommandsMixin, click.RichGroup):
        def __init__(self, *args, **kwargs):
            # Registers all commands from mixins
            ...

Each mixin provides methods decorated with ``@click.command()`` or ``@click.group()``.
The CLI class's ``__init__`` method registers these as commands.

Utility methods (like ``collect_experiment_archive_paths()``) are also in the
``CLI`` class and are shared by multiple command mixins.

Backward Compatibility
======================

This refactoring maintains **full backward compatibility**. All previous imports
continue to work::

    from pycomex.cli import ExperimentCLI  # ✓ Works
    from pycomex.cli import CLI            # ✓ Works
    from pycomex.cli import cli            # ✓ Works (entry point function)

The entry points in ``pyproject.toml`` also continue to work::

    [project.scripts]
    pycomex = "pycomex.cli:cli"
    pycx = "pycomex.cli:cli"

These resolve to the ``cli()`` function defined at the bottom of ``main.py``,
which is re-exported here.

Design Rationale
================

The refactoring addresses several issues with the original monolithic file:

1. **Size**: 2,656 lines made navigation and maintenance difficult
2. **Coupling**: All functionality tightly coupled in one file
3. **Discoverability**: Hard to find specific command implementations
4. **Testing**: Difficult to test commands in isolation

The new structure provides:

- **Modularity**: Related commands grouped in logical modules
- **Clarity**: Clear separation of concerns (commands, display, utils)
- **Maintainability**: Easier to update individual command groups
- **Extensibility**: Simple to add new commands or command groups

For Implementation Details
===========================

See the comprehensive docstring in ``main.py`` for:
- Detailed mixin architecture explanation
- Complete list of all commands in each mixin
- Information about utility methods
- Display component details
"""

from pycomex.cli.main import ExperimentCLI, CLI, cli

__all__ = [
    "ExperimentCLI",
    "CLI",
    "cli",
]
