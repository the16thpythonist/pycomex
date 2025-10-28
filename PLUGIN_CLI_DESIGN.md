# Plugin CLI Command Extension - Design Proposal

## Executive Summary

This document proposes a clean, extensible mechanism for PyComex plugins to register custom CLI commands. The design leverages the existing plugin hook system and Click's command architecture while maintaining backward compatibility and code clarity.

---

## Current Architecture Analysis

### Plugin System
- **Location**: `pycomex/plugin.py`, `pycomex/plugins/`
- **Pattern**: Hook-based architecture with decorator syntax (`@hook`)
- **Manager**: `PluginManager` maintains hook registry and executes callbacks in priority order
- **Discovery**: Automatic loading of native plugins (`pycomex/plugins/`) and external plugins (`pycomex_*` packages)

### CLI System
- **Location**: `pycomex/cli/main.py`, `pycomex/cli/commands/`
- **Pattern**: Mixin-based architecture using multiple inheritance
- **Structure**:
  - `CLI` class inherits from mixins: `RunCommandsMixin`, `TemplateCommandsMixin`, `ArchiveCommandsMixin`
  - Commands are Click-decorated methods registered in `CLI.__init__()`
  - Custom help formatting organizes commands into themed panels

### Current Limitation
**Plugins cannot add CLI commands** - no hook exists for command registration.

---

## Proposed Solution

### Overview
Add a new hook point `cli_register_commands` that fires at the end of `CLI.__init__()`, allowing plugins to register custom Click commands dynamically.

### Design Principles
1. **Minimal Core Changes**: Single hook addition in `CLI.__init__()`
2. **Pythonic**: Use closures for natural plugin method access
3. **Flexible**: Support both direct commands and command groups
4. **Organized**: Plugin commands appear in dedicated help panel
5. **Compatible**: Works with existing Click infrastructure

---

## Implementation Plan

### 1. Add Hook Point in CLI Class

**File**: `pycomex/cli/main.py`

**Location**: End of `CLI.__init__()` method (after line 357)

```python
def __init__(self, *args, **kwargs):
    click.RichGroup.__init__(self, *args, invoke_without_command=True, **kwargs)
    self.cons = Console()

    # ~ adding the default commands
    self.add_command(self.run_command)
    self.add_command(self.reproduce_command)
    self.add_command(self.inspect_command)

    # ... template and archive commands ...

    # NEW: Allow plugins to register CLI commands
    # Track plugin-registered commands for help formatting
    self.plugin_commands = []  # List of (name, plugin_name) tuples

    # Import config here to avoid circular dependency
    from pycomex.config import Config
    config = Config()

    # Fire hook for plugin command registration
    config.pm.apply_hook(
        "cli_register_commands",
        cli=self
    )
```

**Key Points**:
- Hook fires after all built-in commands are registered
- Passes `cli=self` to give plugins access to the CLI instance
- `self.plugin_commands` tracks which commands came from plugins (for help formatting)

---

### 2. Extend Help Formatting

**File**: `pycomex/cli/main.py`

**Location**: `format_help()` method (around line 516, after archive panels)

```python
def format_help(self, ctx, formatter) -> None:
    """
    This method overrides the default "format_help" function of the click.Group class.
    """
    rich.print(RichLogo())
    rich.print(RichHelp())

    # ... existing command panel logic ...

    # NEW: Plugin Commands panel
    plugin_commands_dict = {}

    for cmd_name, cmd in self.commands.items():
        # Check if this is a plugin-registered command
        if cmd_name not in ['run', 'reproduce', 'inspect', 'template', 'archive']:
            if isinstance(cmd, click.Group):
                # Plugin group - show as "groupname"
                plugin_commands_dict[cmd_name] = cmd.short_help or ""
            else:
                # Plugin direct command
                plugin_commands_dict[cmd_name] = cmd.short_help or ""

    # Display plugin commands panel
    if plugin_commands_dict:
        plugin_table = Table(
            show_header=False,
            box=None,
            padding=(0, 1),
            expand=True,
        )
        plugin_table.add_column("Command", style="cyan", min_width=20, max_width=20, no_wrap=True)
        plugin_table.add_column("Description", style="white", ratio=1)

        for name, help_text in sorted(plugin_commands_dict.items()):
            plugin_table.add_row(name, help_text)

        panel = rich.panel.Panel(
            plugin_table,
            title="Plugin Commands",
            title_align="left",
            border_style="bright_black"
        )
        self.cons.print(panel)

    # ... rest of help formatting ...
```

**Alternative Approach**: Track plugin commands explicitly using `self.plugin_commands` list populated by plugins during registration.

---

### 3. Plugin Command Registration Pattern

Plugins register commands using the closure pattern to maintain access to plugin instance (`self`).

#### Pattern A: Direct Command

```python
from pycomex.plugin import Plugin, hook
import click

class MyPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register custom CLI commands."""

        # Define command using closure to capture 'self'
        @click.command("myplugin", short_help="Execute my plugin command")
        @click.option("--foo", default="bar", help="Example option")
        @click.pass_obj
        def myplugin_command(cli_instance, foo):
            # 'self' is the plugin instance (captured from closure)
            # 'cli_instance' is the CLI object (passed by Click)

            cli_instance.cons.print(f"[bold]Running MyPlugin command![/bold]")
            cli_instance.cons.print(f"Option foo={foo}")

            # Access plugin state
            cli_instance.cons.print(f"Plugin config: {self.config}")

            # Access CLI utilities
            archives = cli_instance.collect_experiment_archive_paths(
                self.config['archive_path']
            )
            cli_instance.cons.print(f"Found {len(archives)} archives")

        # Register the command
        cli.add_command(myplugin_command)
```

**Usage**: `pycomex myplugin --foo=baz`

#### Pattern B: Command Group with Subcommands

```python
class MyAdvancedPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register a command group with subcommands."""

        # Create command group
        @click.group("myplugin", short_help="My plugin commands")
        @click.pass_obj
        def myplugin_group(cli_instance):
            """Container for my plugin commands."""
            pass

        # Subcommand 1
        @click.command("analyze", short_help="Analyze experiments")
        @click.option("--select", help="Filter expression")
        @click.pass_obj
        def analyze_command(cli_instance, select):
            cli_instance.cons.print(f"[bold]Analyzing experiments[/bold]")

            # Use CLI utilities
            archives = cli_instance.collect_experiment_archive_paths(
                self.config['archive_path']
            )

            if select:
                archives = cli_instance.filter_experiment_archives_by_select(
                    archives, select
                )

            # Plugin-specific analysis logic
            self.perform_analysis(archives, cli_instance.cons)

        # Subcommand 2
        @click.command("export", short_help="Export plugin data")
        @click.argument("output_path", type=click.Path())
        @click.pass_obj
        def export_command(cli_instance, output_path):
            cli_instance.cons.print(f"Exporting to {output_path}")
            self.export_data(output_path)

        # Register subcommands to group
        myplugin_group.add_command(analyze_command)
        myplugin_group.add_command(export_command)

        # Register group to CLI
        cli.add_command(myplugin_group)

    def perform_analysis(self, archives, console):
        """Plugin-specific analysis logic."""
        console.print(f"Analyzed {len(archives)} experiments")

    def export_data(self, output_path):
        """Plugin-specific export logic."""
        # Implementation
        pass
```

**Usage**:
- `pycomex myplugin analyze --select "p.num_epochs > 100"`
- `pycomex myplugin export /tmp/output.json`

#### Pattern C: Extending Existing Command Groups

Plugins can also add subcommands to existing groups (e.g., `template`, `archive`):

```python
class TemplateExtensionPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Add custom template to the template group."""

        # Access existing template group
        template_group = cli.commands.get('template')

        if template_group and isinstance(template_group, click.Group):

            @click.command("custom", short_help="Create custom template")
            @click.option("-n", "--name", required=True, help="Template name")
            @click.pass_obj
            def template_custom_command(cli_instance, name):
                cli_instance.cons.print(f"Creating custom template: {name}")
                # Plugin-specific template generation
                self.generate_custom_template(name)

            # Add to existing template group
            template_group.add_command(template_custom_command)
```

**Usage**: `pycomex template custom -n my_template`

---

### 4. Helper Utility (Optional Enhancement)

**File**: `pycomex/plugin.py`

To simplify plugin command registration, add a helper decorator:

```python
def cli_command(*args, **kwargs):
    """
    Decorator to mark plugin methods as CLI commands.

    This is a convenience wrapper around @click.command() that makes it
    clearer which plugin methods are intended as CLI commands.

    Usage:
        class MyPlugin(Plugin):
            @cli_command("mycommand", short_help="My command")
            @click.option("--foo", help="Foo option")
            def my_command_impl(self, cli, foo):
                cli.cons.print(f"Running with foo={foo}")
    """
    return click.command(*args, **kwargs)
```

This is purely cosmetic but makes plugin code more readable.

---

## Usage Examples

### Example 1: W&B Dashboard Command

```python
# pycomex/plugins/weights_biases/main.py

class WeightsAndBiasesPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register W&B CLI commands."""

        @click.command("wandb-dashboard", short_help="Open W&B dashboard")
        @click.argument("project", required=False)
        @click.pass_obj
        def wandb_dashboard_command(cli_instance, project):
            """Open Weights & Biases dashboard in browser."""
            import webbrowser

            if not project:
                # Try to infer from recent experiments
                cli_instance.cons.print("Scanning for recent W&B projects...")
                # Logic to find project
                project = self.find_recent_project()

            url = f"https://wandb.ai/{project}"
            cli_instance.cons.print(f"Opening {url}")
            webbrowser.open(url)

        cli.add_command(wandb_dashboard_command)
```

**Usage**: `pycomex wandb-dashboard myproject`

### Example 2: Plot Plugin Visualization Command

```python
# pycomex/plugins/plot_track/main.py

class PlotTrackedElementsPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register plotting CLI commands."""

        @click.group("plot", short_help="Plotting utilities")
        @click.pass_obj
        def plot_group(cli_instance):
            """Commands for visualizing experiment data."""
            pass

        @click.command("compare", short_help="Compare multiple experiments")
        @click.option("--select", help="Experiment filter")
        @click.option("--metric", required=True, help="Metric to compare")
        @click.pass_obj
        def compare_command(cli_instance, select, metric):
            """Compare a metric across multiple experiments."""
            archives = cli_instance.collect_experiment_archive_paths(
                config['archive_path']
            )

            if select:
                archives = cli_instance.filter_experiment_archives_by_select(
                    archives, select
                )

            cli_instance.cons.print(f"Comparing {metric} across {len(archives)} experiments")
            self.create_comparison_plot(archives, metric)

        plot_group.add_command(compare_command)
        cli.add_command(plot_group)
```

**Usage**: `pycomex plot compare --metric=accuracy --select "p.learning_rate > 0.001"`

### Example 3: Notification Plugin Settings

```python
# pycomex/plugins/notify/main.py

class NotifyPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register notification configuration commands."""

        @click.command("notify-config", short_help="Configure notifications")
        @click.option("--enable/--disable", default=True, help="Enable notifications")
        @click.option("--timeout", type=int, default=5, help="Notification timeout")
        @click.pass_obj
        def notify_config_command(cli_instance, enable, timeout):
            """Configure notification settings."""
            config['notify_enabled'] = enable
            config['notify_timeout'] = timeout

            cli_instance.cons.print(f"Notifications: {'enabled' if enable else 'disabled'}")
            cli_instance.cons.print(f"Timeout: {timeout}s")

        cli.add_command(notify_config_command)
```

**Usage**: `pycomex notify-config --enable --timeout=10`

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Add `cli_register_commands` hook in `CLI.__init__()` (`pycomex/cli/main.py:357`)
- [ ] Add `self.plugin_commands` tracking list
- [ ] Import `Config` in `CLI.__init__()` to access PluginManager
- [ ] Test hook fires correctly with mock plugin

### Phase 2: Help Formatting
- [ ] Extend `format_help()` to detect plugin commands
- [ ] Add "Plugin Commands" panel display logic
- [ ] Test help output with multiple plugin commands
- [ ] Test help output with no plugin commands (should not show panel)

### Phase 3: Documentation
- [ ] Add "Plugin CLI Commands" section to plugin development guide
- [ ] Document closure pattern with examples
- [ ] Add example plugin with CLI commands to `tests/assets/`
- [ ] Update existing plugin documentation to show CLI capabilities

### Phase 4: Testing
- [ ] Unit test: Plugin command registration
- [ ] Unit test: Plugin command execution
- [ ] Unit test: Multiple plugins registering commands
- [ ] Unit test: Plugin extending existing command groups
- [ ] Integration test: Full CLI workflow with plugin commands
- [ ] Test: Help formatting with plugin commands

### Phase 5: Example Plugins
- [ ] Add CLI commands to `WeightsAndBiasesPlugin` (dashboard, sync, etc.)
- [ ] Add CLI commands to `PlotTrackedElementsPlugin` (compare, export, etc.)
- [ ] Add CLI commands to `NotifyPlugin` (config, test-notification, etc.)

---

## Potential Enhancements

### 1. Plugin Metadata for Help Formatting

Allow plugins to provide metadata about their commands:

```python
@hook("cli_register_commands", priority=0)
def register_cli_commands(self, config, cli):
    # ... register commands ...

    # Optionally provide metadata for better help formatting
    cli.plugin_commands.append({
        'name': 'myplugin',
        'plugin': 'MyPlugin',
        'category': 'Analysis',  # Optional category for grouping
        'priority': 10  # Optional display priority
    })
```

### 2. Command Conflicts Detection

Add validation to prevent plugin commands from conflicting with built-in commands:

```python
def register_cli_commands(self, config, cli):
    reserved_names = ['run', 'reproduce', 'inspect', 'template', 'archive']

    cmd_name = 'run'  # hypothetical
    if cmd_name in reserved_names:
        raise ValueError(f"Command '{cmd_name}' conflicts with built-in command")

    cli.add_command(my_command)
```

### 3. Plugin Command Discovery Tool

Add a command to list all available plugin commands:

```bash
$ pycomex plugin list-commands

Available Plugin Commands:
  myplugin              [MyPlugin] Execute my plugin command
  wandb-dashboard       [WeightsAndBiasesPlugin] Open W&B dashboard
  plot compare          [PlotTrackedElementsPlugin] Compare experiments
```

---

## Migration Path for Existing Plugins

Existing plugins require **no changes** - they will continue to work without CLI commands.

Adding CLI commands is **opt-in**:

1. Add `@hook("cli_register_commands")` method
2. Define commands using closure pattern
3. Register via `cli.add_command()`

---

## Security Considerations

1. **Command Injection**: Plugin commands have same privileges as built-in commands
2. **Name Conflicts**: Plugins should check for existing commands before registering
3. **Validation**: Plugin commands should validate user input like built-in commands
4. **Documentation**: Clearly document that plugin commands execute with full privileges

---

## Conclusion

This design provides a clean, minimal extension point for plugins to add CLI commands while:
- Maintaining backward compatibility
- Following existing architectural patterns (hooks, Click, Rich)
- Requiring minimal changes to core code
- Providing flexibility for both simple and complex plugin commands

The closure-based pattern is Pythonic, type-safe, and allows natural access to both plugin state and CLI utilities.

**Next Steps**: Review this design, gather feedback, and proceed with implementation checklist.
