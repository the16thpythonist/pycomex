"""
Unittests for the weights and biases plugin "weights_biases".
"""

import os
import sys

import pytest

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.testing import ConfigIsolation, ExperimentIsolation

try:
    import wandb
except ImportError:
    pytest.skip(
        "wandb not available, skipping weights_biases plugin tests",
        allow_module_level=True,
    )

pytest.skip("not testing wandb", allow_module_level=True)


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

        assert "weights_biases" in config.plugins
        assert len(config.pm) != 0


@pytest.mark.localonly
def test_plugin_basically_works():
    """
    The weights and biases plugin should be able to be initialized and the experiment should be able to run
    without any issues.
    """
    parameters = {
        "WANDB_PROJECT": "test",
    }

    with (
        ConfigIsolation() as config,
        ExperimentIsolation(sys.argv, glob_mod=parameters) as iso,
    ):

        config.load_plugins()
        assert "weights_biases" in config.plugins

        experiment = Experiment(
            base_path=iso.path,
            namespace="experiment",
            glob=iso.glob,
            notify=False,
        )

        @experiment
        def run(*args, **kwargs):
            return

        experiment.run()

        # Since in this case we actually did supply a WANDB_PROJECT parameter, the experiment should have
        # the __wandb__ flag set to True which indicates that wandb was actually used for the experiment.
        assert "__wandb__" in experiment.metadata
        assert experiment.metadata["__wandb__"] is True
        # We should also be able to access the plugin object itself and get information
        # such as the project name.
        plugin = config.plugins["weights_biases"]
        assert plugin.project_name == "test"


def test_plugin_inactive_without_conditions():
    """
    If the necessary conditions are not met - aka there is no special WANDB_PROJECT parameter defined - then
    the plugin should also not be active! This means that the __wandb__ flag should be set to False.
    """
    with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:

        config.load_plugins()
        assert "weights_biases" in config.plugins

        experiment = Experiment(
            base_path=iso.path,
            namespace="experiment",
            glob=iso.glob,
            notify=False,
        )

        @experiment
        def run(*args, **kwargs):
            return

        experiment.run()

        # Since we did not supply a WANDB_PROJECT parameter, the experiment should not have
        # the __wandb__ flag set to True.
        assert "__wandb__" in experiment.metadata
        assert experiment.metadata["__wandb__"] is False


@pytest.mark.parametrize("name", ["", None, 123, "@my!project"])
def test_plugin_handles_invalid_project_name(name):
    """
    The weights and biases plugin should handle invalid project names gracefully without crashing.
    """
    parameters = {
        "WANDB_PROJECT": name,
    }

    with (
        ConfigIsolation() as config,
        ExperimentIsolation(sys.argv, glob_mod=parameters) as iso,
    ):

        config.load_plugins()
        assert "weights_biases" in config.plugins

        experiment = Experiment(
            base_path=iso.path,
            namespace="experiment",
            glob=iso.glob,
            notify=False,
        )

        @experiment
        def run(*args, **kwargs):
            return

        experiment.run()

        # The plugin should not be active due to invalid project name
        assert "__wandb__" in experiment.metadata
        assert experiment.metadata["__wandb__"] is False
