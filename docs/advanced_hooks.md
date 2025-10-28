# Plugin Hooks

This page aims to provide a (non-exhaustive) list of the available hooks in the pycomex library. Each hook is described with its name, a brief description, and the parameters it accepts.

### 🪝 `plugin_registered`

This hook is executed *right* after a plugin is registerd. The hook receives the name of the plugin that was registered as well as the plugin object itself. This hook can for example be used to hot-swap or replace certain plugins with newer or alternative versions.

| Parameter | Description                |
|-----------|----------------------------|
| `name` | The name of the plugin that was registered |
| `plugin` | The `Plugin` object instance that was registered |
| `config` | The `Config` instance that is used by the pycomex library |

Returns: None

---

### 🪝 `plugin_registered__{plugin_name}`

This hook is executed right after a plugin is registered. The name of the hook is dynamically derived from the name of the actual plugin. Therefore, only the plugin itself will likely be able to know the name of this hook and be able to register a function to it.

| Parameter | Description                |
|-----------|----------------------------|
| `plugin` | The `Plugin` object instance that was registered |
| `config` | The `Config` instance that is used by the pycomex library |


## `Experiment` Hooks

---

### 🪝 `before_experiment_parameters`

This hook is executed within the lifetime of an `Experiment` instance after its construction - right before the experiment parameters are processed. 

| Parameter | Description                |
|-----------|----------------------------|
| `experiment` | The `Experiment` instance itself |


### 🪝 `experiment_constructed`

This hook is executed at the end of the `Experiment` constructor. It can be used
to perform additional setup steps once the experiment object exists.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance that was created |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `after_experiment_initialize`

Executed after the `Experiment.initialize` method completed. At this point the
archive folder has been created and the experiment is ready to run.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `after_experiment_finalize`

Executed after the `Experiment.finalize` method completed. This allows for
additional cleanup or post-processing once the experiment is finished.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_commit_fig`

Called at the end of `Experiment.commit_fig` after the figure has been saved to
the archive folder.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | The name of the saved figure file |
| `figure` | The `matplotlib` figure instance |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_commit_json`

Called at the end of `Experiment.commit_json` once the JSON file has been
written.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | The name of the saved JSON file |
| `data` | The original data structure that was saved |
| `content` | The string representation that was written to the file |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_commit_raw`

Called at the end of `Experiment.commit_raw` after the text file has been
created.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | The name of the saved file |
| `content` | The text content that was written |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_track`

Called at the end of `Experiment.track`. It receives the tracked name and value
so that the tracking information can be forwarded to external services.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | Name under which the value was tracked |
| `value` | The tracked value or figure |
| `config` | The `Config` instance that is used by the pycomex library |


---

## `Config` Hooks

---

### 🪝 `after_plugins_loaded`

This hook is executed right after the plugins are loaded and before the configuration is finalized. This is one of the earliest possible entry points for any plugin and could for example be used for some early initialization tasks.

| Parameter | Description                |
|-----------|----------------------------|
| `config` | The `Config` instance itself     |
| `plugins` | A dictionary where the string keys are the plugin names and the values are the corresponding `Plugin` object instances |

---

### 🪝 `cli_register_commands`

This hook is executed during CLI initialization, right after all built-in commands have been registered. It allows plugins to register custom CLI commands that will appear in the PyComex command-line interface. Plugin commands have full access to CLI utilities including the Rich console, archive collection helpers, and filtering functions.

Plugins should define Click commands using the closure pattern to maintain access to both the plugin instance (`self`) and the CLI instance (`cli_instance` via `@click.pass_obj`).

| Parameter | Description                |
|-----------|----------------------------|
| `cli` | The `CLI` instance that is being initialized. Plugins can call `cli.add_command()` to register commands. |
| `config` | The `Config` instance that is used by the pycomex library |

**Example Usage:**

```python
import rich_click as click
from pycomex.plugin import Plugin, hook

class MyPlugin(Plugin):

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register custom CLI commands."""

        # Define command using closure pattern
        @click.command("my-command", short_help="My plugin command")
        @click.option("--name", help="Name parameter")
        @click.pass_obj
        def my_command(cli_instance, name):
            # Access CLI utilities
            cli_instance.cons.print(f"[bold]Hello {name}![/bold]")

            # Access plugin state via closure
            self.process(name)

        # Register the command
        cli.add_command(my_command)
```

**Supported Command Patterns:**

1. **Direct Command**: Registers a top-level command like `pycomex my-command`
2. **Command Group**: Registers a group with subcommands like `pycomex my-group subcommand`
3. **Extend Existing Group**: Adds subcommands to existing groups like `template` or `archive`

**Help Output:**

Plugin commands appear in a dedicated "Plugin Commands" section in the help output. Command groups are automatically expanded to show all their subcommands:

```
╭─ Plugin Commands ─────────────────────────────────────────────╮
│  my-command            My plugin command                      │
│  my-group analyze      Analyze data                           │
│  my-group export       Export results                         │
╰───────────────────────────────────────────────────────────────╯
```

