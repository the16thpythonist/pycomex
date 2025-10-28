# Writing Plugins

The pycomex library is designed to be extensible through a plugin system. Plugins can be used to add new functionality, modify existing behavior, or integrate with external systems. This document provides guidelines for writing and integrating plugins into the pycomex library.

## The Hook System

Plugins are implemented using a *hook system*. During various stages of the experiment lifetime of the computational experiment, the pycomex library will call specific *"hook"* functions. These hook functions are primarily *placeholders* associated with a known and unique string identifier. Each new plugin has the option to register custom function implementations to these hooks such that this custom code will be executed at various stages of the experiment lifecycle.

Depending on the specific hook, these functions may receive various arguments or may be required to return specific values. These arguments and return values can then usually be used to modify the behavior of the pycomex library itself to achieve the intended functionality of the plugin.

As an example, one can imagine a very simple plugin that prints a simple "Hello World" message before the start of each experiment. For such a use case, it would make most sense to register a custom function to the `before_experiment` hook. This hook is called right before the experiment starts.

To implement an intended plugin functionality, one necessary step is therefore to familiarize oneself with the available hooks that are provided by the pycomex library.

## Plugin Discovery

The discovery of plugins is done as one of the very first steps of the pycomex library. The discovery is basically split into an *internal* and an *external* discovery step.

**Internal Plugins.** These are the plugins which are shipped together with the pycomex library itself. These plugins are the default plugins that come with the library and are located in the `pycomex/plugins` directory. Each folder in this plugins directory is assumed to be its own plugin.

**External Plugins.** These are the plugins which can be installed by the user. During the plugin discovery stage, the library will assume every Python package that is installed in the current environment starting with the string `pycomex_` to be its own plugin.

## Creating a Plugin

Based on the previous section, the primary method of creating a new plugin is to create a new Python package whose name starts with the prefix `pycomex_`. This package can then contain any number of Python modules, which can implement the intended functionality of the plugin, but it *must* contain a `main.py` module which acts as the entry point for the plugin managment system.

The `main.py` module should implement a subclass of the `pycomex.plugins.Plugin` class. This subclass is where the plugin's functionality is defined, and it should register the necessary hooks that the plugin will use. This class may have any name, so long as it inherits from the `pycomex.plugins.Plugin` class.

**Example.** As an example, we'll consider a simple plugin that adds additional messages at the beginning and end of each experiment. The plugin will be called `pycomex_hello_world`.

```python title="pycomex_hello_world/main.py"
from pycomex.plugins import Plugin, hook

class HelloWorldPlugin(Plugin):

    @hook('before_experiment', priority=0)
    def before_experiment(self, *args, **kwargs):
        print('Hello World! The experiment is about to start.')

    @hook('after_experiment', priority=0)
    def after_experiment(self, *args, **kwargs):
        print('Goodbye World! The experiment has finished.')
```

To complete the plugin, you'll need to ensure that the package is installed in your Python environment. This can be done by creating an appropriate `pyproject.toml` or `setup.py` file.

!!! info "Plugin Initialization"

    Do not use the default python `__init__` constructor of your custom plugin class, as the actual plugin object instance will be automatically created by the plugin system internally. Instead use the `init` hook to perform any necessary setup operations which would usually be done in the constructor. This hook will be called right after the plugin object instance is created. 

**Summary.** To summarize a plugin can be created by the following steps:

1. Create a new Python package with the name starting with `pycomex_`.
2. Create a `main.py` module inside this package.
3. Implement a subclass that inherits from the `pycomex.plugins.Plugin` class inside the `main.py` module.
4. Register the necessary hooks inside of this subclass.

## Adding CLI Commands

Plugins can extend the PyComex CLI by registering custom commands using the `cli_register_commands` hook. This allows plugins to add their own subcommands to the `pycomex` command-line interface.

### Basic Example

Here's a simple example of a plugin that adds a custom CLI command:

```python title="pycomex_mycli/main.py"
import rich_click as click
from pycomex.plugin import Plugin, hook

class MyCliPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register custom CLI commands."""

        # Define the command using the closure pattern
        # This allows access to both 'self' (plugin) and 'cli_instance' (CLI object)
        @click.command("hello", short_help="Say hello from the plugin")
        @click.option("--name", default="World", help="Name to greet")
        @click.pass_obj
        def hello_command(cli_instance, name):
            """
            A simple hello command added by the plugin.

            This command demonstrates how plugins can add custom CLI functionality.
            """
            # Access CLI utilities like the Rich console
            cli_instance.cons.print(f"[bold green]Hello, {name}![/bold green]")
            cli_instance.cons.print("This message comes from a plugin command!")

        # Register the command with the CLI
        cli.add_command(hello_command)
```

After installing this plugin, users can run:

```bash
$ pycomex hello --name Alice
Hello, Alice!
This message comes from a plugin command!
```

The command will also appear in the help output under "Plugin Commands":

```bash
$ pycomex --help
...
╭─ Plugin Commands ────────────────────────────────────────────────────────╮
│ hello                Say hello from the plugin                           │
╰──────────────────────────────────────────────────────────────────────────╯
```

### Command Groups

For more complex functionality, plugins can register command groups with multiple subcommands:

```python title="pycomex_analysis/main.py"
import rich_click as click
from pycomex.plugin import Plugin, hook

class AnalysisPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register analysis command group."""

        # Create a command group
        @click.group("analyze", short_help="Analysis tools from plugin")
        @click.pass_obj
        def analyze_group(cli_instance):
            """Analysis commands provided by the plugin."""
            pass

        # Add subcommands to the group
        @click.command("stats", short_help="Show statistics")
        @click.option("--select", help="Filter experiments")
        @click.pass_obj
        def stats_command(cli_instance, select):
            """Display statistics about experiments."""
            archives = cli_instance.collect_experiment_archive_paths(
                config['archive_path']
            )

            if select:
                archives = cli_instance.filter_experiment_archives_by_select(
                    archives, select
                )

            cli_instance.cons.print(f"[bold]Found {len(archives)} experiments[/bold]")
            # Plugin-specific analysis logic here...

        @click.command("export", short_help="Export results")
        @click.argument("output", type=click.Path())
        @click.pass_obj
        def export_command(cli_instance, output):
            """Export analysis results to a file."""
            cli_instance.cons.print(f"Exporting to {output}...")
            # Plugin-specific export logic here...

        # Register subcommands to group
        analyze_group.add_command(stats_command)
        analyze_group.add_command(export_command)

        # Register group to CLI
        cli.add_command(analyze_group)
```

Usage:

```bash
$ pycomex analyze stats --select "p.accuracy > 0.9"
$ pycomex analyze export results.json
```

The command group appears expanded in the help output, showing all subcommands:

```bash
$ pycomex --help
...
╭─ Plugin Commands ────────────────────────────────────────────────────────╮
│ analyze stats        Show statistics                                     │
│ analyze export       Export results                                      │
╰──────────────────────────────────────────────────────────────────────────╯
```

### Key Points

- **Closure Pattern**: Commands are defined inside the hook method to capture `self` (plugin instance) via closure
- **CLI Access**: Use `@click.pass_obj` to receive the CLI instance, which provides access to:
    - `cli_instance.cons` - Rich Console for formatted output
    - `cli_instance.collect_experiment_archive_paths()` - Collect experiment archives
    - `cli_instance.filter_experiment_archives_by_select()` - Filter archives with Python expressions
- **Integration**: Plugin commands automatically appear in the help output under "Plugin Commands"

For more details about available hooks, see the [Plugin Hooks](advanced_hooks.md#cli_register_commands) documentation.

