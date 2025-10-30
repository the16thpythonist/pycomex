"""
Tests for the "notify" pycomex plugin which is shipped by default already.
"""

import os
import sys

import pytest

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.testing import ConfigIsolation, ExperimentIsolation


@pytest.mark.localonly
def test_plugin_loading_works():
    """
    After simply calling config.load_plugins() the plugin manager should be populated with all the available
    plugins including the target weights and biases plugin.
    """
    with ConfigIsolation() as config:

        assert len(config.pm) == 0

        # This should properly load all the available plugins including the weights and biases
        # plugin to be tested.
        config.load_plugins()

        assert "notify" in config.plugins
        assert len(config.pm) != 0


@pytest.mark.localonly
def test_plugin_basically_works():
    """
    The plugin is enabled by the default value of the __NOTIFY__ flag and when the plugin is enabled
    the notification should pop up on the desktop.
    """
    parameters = {"__NOTIFY__": True}
    with (
        ConfigIsolation() as config,
        ExperimentIsolation(sys.argv, glob_mod=parameters) as iso,
    ):

        config.load_plugins()
        assert "notify" in config.plugins

        experiment = Experiment(
            base_path=iso.path,
            namespace="experiment",
            glob=iso.glob,
        )

        @experiment
        def run(*args, **kwargs):
            return

        experiment.run()

        assert "__NOTIFY__" in experiment.parameters
        assert experiment.__NOTIFY__ is True
        plugin = config.plugins["notify"]
        assert plugin.message is not None and isinstance(plugin.message, str)


@pytest.mark.localonly
def test_notifications_can_be_disabled():
    """
    When setting the __NOTIFY___ flag to False, the plugin should be inactive and not send
    any notifications.
    """
    parameters = {"__NOTIFY__": False}
    with (
        ConfigIsolation() as config,
        ExperimentIsolation(sys.argv, glob_mod=parameters) as iso,
    ):

        config.load_plugins()
        assert "notify" in config.plugins

        experiment = Experiment(
            base_path=iso.path,
            namespace="experiment",
            glob=iso.glob,
        )

        @experiment
        def run(*args, **kwargs):
            return

        experiment.run()
        assert "__NOTIFY__" in experiment.parameters
        assert experiment.__NOTIFY__ is False
        plugin = config.plugins["notify"]
        assert plugin.message is None
