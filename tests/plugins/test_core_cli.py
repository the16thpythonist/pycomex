"""
Tests for plugin CLI command registration functionality.

This module tests the ability of plugins to register custom CLI commands
through the cli_register_commands hook.
"""
import sys
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import rich_click as click
from click.testing import CliRunner

from pycomex.cli import CLI, cli
from pycomex.config import Config
from pycomex.plugin import Plugin
from pycomex.testing import MockConfig


def invoke_cli_with_plugin(runner, cli_instance, args):
    """
    Helper to invoke CLI commands with proper context object set.

    Click's @click.pass_obj expects ctx.obj to be set. The main CLI entry point
    sets ctx.obj = ctx.command (the CLI instance). We replicate that here.
    """
    return runner.invoke(cli_instance, args, obj=cli_instance)


class TestPluginCLICommands:
    """Test suite for plugin CLI command registration."""

    @pytest.fixture(autouse=True)
    def setup_test_plugin(self):
        """
        Setup fixture that ensures the test plugin is available.

        This adds the test assets directory to the Python path and manually
        loads the test plugin since it's not in the standard plugin directories.
        """
        # Add test assets to path
        test_assets_path = Path(__file__).parent / "assets"
        if str(test_assets_path) not in sys.path:
            sys.path.insert(0, str(test_assets_path))

        # Reset Config state to ensure clean slate
        Config().reset_state()

        # Manually load the test plugin
        config = Config()
        try:
            import test_plugin_cli.main as test_plugin_module
            config.load_plugin_from_module(
                name="test_plugin_cli",
                module=test_plugin_module
            )
        except Exception as e:
            pytest.skip(f"Could not load test plugin: {e}")

        yield

        # Cleanup: Reset Config singleton state after test
        Config().reset_state()

    def test_cli_register_commands_hook_exists(self):
        """
        Test that the cli_register_commands hook is fired during CLI initialization.
        """
        # Track if hook was called
        hook_called = False

        def mock_apply_hook(hook_name, **kwargs):
            nonlocal hook_called
            if hook_name == "cli_register_commands":
                hook_called = True
                assert "cli" in kwargs
                assert isinstance(kwargs["cli"], CLI)

        config = Config()

        # Patch the apply_hook method to track calls
        with patch.object(config.pm, "apply_hook", side_effect=mock_apply_hook):
            cli_instance = CLI()

        assert hook_called, "cli_register_commands hook was not fired"

    def test_plugin_can_register_direct_command(self):
        """
        Test that a plugin can register a direct command via the hook.
        """
        # Import test plugin dynamically
        from test_plugin_cli.main import TestCLIPlugin

        # Create CLI instance (this will trigger plugin command registration)
        cli_instance = CLI()

        # Verify test-hello command was registered
        assert "test-hello" in cli_instance.commands
        assert cli_instance.commands["test-hello"].name == "test-hello"

    def test_plugin_can_register_command_group(self):
        """
        Test that a plugin can register a command group with subcommands.
        """
        from test_plugin_cli.main import TestCLIPlugin

        cli_instance = CLI()

        # Verify test-group was registered
        assert "test-group" in cli_instance.commands

        # Verify it's a group
        import click
        assert isinstance(cli_instance.commands["test-group"], click.Group)

        # Verify subcommands exist
        test_group = cli_instance.commands["test-group"]
        assert "analyze" in test_group.commands
        assert "export" in test_group.commands

    def test_plugin_command_execution(self):
        """
        Test that plugin-registered commands can be executed successfully.
        """
        from test_plugin_cli.main import TestCLIPlugin

        config = Config()

        # Create a fresh CLI instance AFTER plugin is loaded
        # (the cli entry point is created at import time, before plugin load)
        cli_instance = CLI()

        # Create runner
        runner = CliRunner()

        # Test direct command execution
        result = invoke_cli_with_plugin(runner, cli_instance, ["test-hello", "--name", "TestUser", "--count", "2"])

        # Verify execution succeeded
        assert result.exit_code == 0

        # Verify command was executed (check config data set by plugin)
        assert config.data.get("test_hello_called") is True
        assert config.data.get("test_hello_name") == "TestUser"
        assert config.data.get("test_hello_count") == 2

        # Verify output
        assert "Hello from TestCLIPlugin" in result.output
        assert "TestUser" in result.output

    def test_plugin_group_command_execution(self):
        """
        Test that plugin group subcommands can be executed.
        """
        from test_plugin_cli.main import TestCLIPlugin

        config = Config()
        cli_instance = CLI()
        runner = CliRunner()

        # Test analyze subcommand
        result = invoke_cli_with_plugin(runner, cli_instance, ["test-group", "analyze", "--verbose"])
        assert result.exit_code == 0
        assert config.data.get("test_analyze_called") is True
        assert config.data.get("test_analyze_verbose") is True
        assert "Running analysis" in result.output

        # Reset config data
        config.data.clear()

        # Test export subcommand
        result = invoke_cli_with_plugin(runner, cli_instance, ["test-group", "export", "/tmp/output.json", "--format", "json"])
        assert result.exit_code == 0
        assert config.data.get("test_export_called") is True
        assert config.data.get("test_export_path") == "/tmp/output.json"
        assert config.data.get("test_export_format") == "json"
        assert "Exporting to" in result.output

    def test_plugin_commands_appear_in_help(self):
        """
        Test that plugin commands appear in the help output.
        """
        from test_plugin_cli.main import TestCLIPlugin

        cli_instance = CLI()
        runner = CliRunner()

        # Get help output
        result = runner.invoke(cli_instance, ["--help"])
        assert result.exit_code == 0

        # Verify plugin commands section exists
        assert "Plugin Commands" in result.output

        # Verify direct command is listed
        assert "test-hello" in result.output
        assert "Test plugin hello command" in result.output

        # Verify command group subcommands are expanded and listed
        # Should show "test-group analyze" and "test-group export" rather than just "test-group"
        assert "test-group analyze" in result.output
        assert "test-group export" in result.output

        # Verify subcommand short help texts are shown
        assert "Analyze something" in result.output
        assert "Export plugin data" in result.output

    def test_plugin_command_help(self):
        """
        Test that plugin commands have proper help text.
        """
        from test_plugin_cli.main import TestCLIPlugin

        cli_instance = CLI()
        runner = CliRunner()

        # Test direct command help
        result = runner.invoke(cli_instance, ["test-hello", "--help"])
        assert result.exit_code == 0
        assert "Say hello" in result.output
        assert "--name" in result.output
        assert "--count" in result.output

        # Test group help
        result = runner.invoke(cli_instance, ["test-group", "--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output
        assert "export" in result.output

        # Test subcommand help
        result = runner.invoke(cli_instance, ["test-group", "analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze command" in result.output
        assert "--verbose" in result.output

    def test_multiple_plugins_can_register_commands(self):
        """
        Test that multiple plugins can register commands without conflicts.
        """
        cli_instance = CLI()

        # Collect all non-builtin commands
        builtin_commands = ["run", "reproduce", "inspect", "template", "archive"]
        plugin_commands = [
            cmd_name for cmd_name in cli_instance.commands.keys()
            if cmd_name not in builtin_commands
        ]

        # With test_plugin_cli loaded, we should have at least test-hello and test-group
        assert len(plugin_commands) >= 2
        assert "test-hello" in plugin_commands
        assert "test-group" in plugin_commands

    def test_plugin_commands_list_tracking(self):
        """
        Test that CLI tracks plugin commands in self.plugin_commands list.
        """
        cli_instance = CLI()

        # Verify plugin_commands attribute exists
        assert hasattr(cli_instance, "plugin_commands")
        assert isinstance(cli_instance.plugin_commands, list)

    def test_plugin_closure_access(self):
        """
        Test that plugin commands can access plugin state via closure.
        """
        from test_plugin_cli.main import TestCLIPlugin

        config = Config()
        cli_instance = CLI()
        runner = CliRunner()

        # Get plugin instance
        plugin = config.plugins.get("test_plugin_cli")
        assert plugin is not None
        assert isinstance(plugin, TestCLIPlugin)

        # Execute command
        result = invoke_cli_with_plugin(runner, cli_instance, ["test-hello", "--name", "ClosureTest"])
        assert result.exit_code == 0

        # Verify plugin tracked the invocation via closure
        assert len(plugin.invocations) > 0
        assert plugin.invocations[-1] == ("test-hello", "ClosureTest", 1)

    def test_help_without_plugins(self):
        """
        Test that help works correctly when no plugin commands are registered.

        This test ensures backward compatibility - help should work fine
        even if plugins don't register any CLI commands.
        """
        # Create a config without loading test plugins
        # (In a real scenario, this would be a fresh config with no plugins)
        runner = CliRunner()

        # Even with plugins, help should work
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

        # Should show built-in commands
        assert "run" in result.output
        assert "template" in result.output
        assert "archive" in result.output
