"""
Test plugin that registers CLI commands.

This plugin demonstrates how to add custom CLI commands through the plugin system.
It includes both a direct command and a command group with subcommands.
"""
import rich_click as click
from pycomex.config import Config
from pycomex.plugin import Plugin, hook


class TestCLIPlugin(Plugin):
    """
    Test plugin that registers custom CLI commands.

    This plugin demonstrates the cli_register_commands hook and shows how plugins
    can add both direct commands and command groups to the PyComex CLI.
    """

    def __init__(self, config: Config):
        super().__init__(config)
        # Track invocations for testing
        self.invocations = []

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config: Config, cli) -> None:
        """
        Register custom CLI commands using the closure pattern.

        This method is called during CLI initialization and allows the plugin
        to register custom commands that will appear in the PyComex CLI.
        """

        # Pattern 1: Direct Command
        # This creates a simple top-level command like "pycomex test-hello"
        @click.command("test-hello", short_help="Test plugin hello command")
        @click.option("--name", default="World", help="Name to greet")
        @click.option("--count", default=1, type=int, help="Number of greetings")
        @click.pass_obj
        def test_hello_command(cli_instance, name, count):
            """
            Say hello - a simple test command from the plugin.

            This demonstrates a direct command registered by a plugin.
            """
            # Access plugin state via closure (self)
            self.invocations.append(("test-hello", name, count))

            # Access CLI utilities via cli_instance
            for i in range(count):
                cli_instance.cons.print(f"[bold green]Hello from TestCLIPlugin:[/bold green] {name}!")

            # Store data in config for testing
            config.data["test_hello_called"] = True
            config.data["test_hello_name"] = name
            config.data["test_hello_count"] = count

        # Register the direct command
        cli.add_command(test_hello_command)

        # Pattern 2: Command Group with Subcommands
        # This creates a command group like "pycomex test-group analyze"
        @click.group("test-group", short_help="Test plugin command group")
        @click.pass_obj
        def test_group(cli_instance):
            """
            Test command group from plugin.

            This group contains multiple subcommands to demonstrate
            plugin command organization.
            """
            pass

        # Subcommand 1: Analyze
        @click.command("analyze", short_help="Analyze something")
        @click.option("--verbose", is_flag=True, help="Verbose output")
        @click.pass_obj
        def analyze_command(cli_instance, verbose):
            """
            Analyze command - demonstrates plugin subcommand.
            """
            self.invocations.append(("analyze", verbose))

            cli_instance.cons.print("[bold cyan]Running analysis...[/bold cyan]")
            if verbose:
                cli_instance.cons.print("Verbose mode enabled")
                cli_instance.cons.print(f"Config data: {config.data}")

            config.data["test_analyze_called"] = True
            config.data["test_analyze_verbose"] = verbose

        # Subcommand 2: Export
        @click.command("export", short_help="Export plugin data")
        @click.argument("output_path", type=click.Path())
        @click.option("--format", type=click.Choice(["json", "yaml"]), default="json")
        @click.pass_obj
        def export_command(cli_instance, output_path, format):
            """
            Export command - demonstrates plugin subcommand with arguments.
            """
            self.invocations.append(("export", output_path, format))

            cli_instance.cons.print(f"[bold magenta]Exporting to:[/bold magenta] {output_path}")
            cli_instance.cons.print(f"Format: {format}")

            config.data["test_export_called"] = True
            config.data["test_export_path"] = output_path
            config.data["test_export_format"] = format

        # Register subcommands to group
        test_group.add_command(analyze_command)
        test_group.add_command(export_command)

        # Register group to CLI
        cli.add_command(test_group)

        # Mark that CLI commands were registered (for testing)
        config.data["test_cli_plugin_registered"] = True
