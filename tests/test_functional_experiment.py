import json
import os
import sys

import yaml

from pycomex.functional.experiment import Experiment, ExperimentConfig, run_experiment
from pycomex.testing import ConfigIsolation, ExperimentIsolation

from .util import ASSETS_PATH


def test_run_experiment_works():
    """
    The "run_experiment" utility function should be able to execute an experiment module from
    its absolute file path
    """
    experiment_path = os.path.join(ASSETS_PATH, "mock_functional_experiment.py")
    experiment: Experiment = run_experiment(experiment_path)

    assert experiment.error is None
    assert len(experiment.data) != 0


class TestExperimentArgumentParser:
    """
    ExperimentArgumentParser is a class that is used to parse command line arguments that are passed to the
    individual experiment modules.
    """

    def test_command_line_arguments_basically_work(self):
        """
        It should generally be possible to modify the behavior of an experiment object by specifiying
        command line arguments (sys.argv)
        """
        argv = ["test.py", "--__DEBUG__=True"]
        with ConfigIsolation() as config, ExperimentIsolation(argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )
            # We'll have to call this method explicitly because this operation would only be done in the
            # experiment.run_if_main() method usually.
            experiment.arg_parser.parse()

            assert "__DEBUG__" in experiment.parameters
            assert experiment.__DEBUG__ is True


class TestExperiment:

    def test_construction_basically_works(self):
        """
        It should be possible to construct the experiment object without any errors and after
        constructing it should have the parameters that were passed to it.
        """
        parameters = {"PARAMETER": 10}
        with (
            ConfigIsolation() as config,
            ExperimentIsolation(sys.argv, glob_mod=parameters) as iso,
        ):

            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            assert isinstance(experiment, Experiment)
            assert "PARAMETER" in experiment.parameters

    def test_prefix_parameter_works(self):
        """
        When using the special parameter __PREFIX__ that string should be added in front of the
        experiment name when the experiment archive folder is being created.
        """
        parameters = {"__PREFIX__": "custom"}
        with (
            ConfigIsolation() as config,
            ExperimentIsolation(sys.argv, glob_mod=parameters) as iso,
        ):

            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(*args, **kwargs):
                return

            experiment.run()
            assert "__PREFIX__" in experiment.parameters

            assert experiment.name.startswith("custom")
            assert "custom" in experiment.path

    def test_save_data_excludes_internal_data(self):
        """
        The save_data method should exclude any data entries that start with an underscore from being
        saved into the experiment_data.json file.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )
            experiment.path = iso.path  # Manually set the path for testing purposes
            experiment.data = {
                "public_data": 123,
                "_internal_data": 456,
            }
            experiment.save_data()

            # Read the JSON file and assert that 'internal_data' is not present
            with open(experiment.data_path) as f:
                data = json.load(f)
                assert "_internal_data" not in data
                assert "public_data" in data


class TestExperimentConfig:

    def test_experiment_config_basically_works(self):

        experiment_data = {
            "extend": "experiment.py",
            "parameters": {
                "PARAMETER": 10,
            },
        }

        experiment_config = ExperimentConfig(
            path="/tmp/sub_experiment.yml",
            **experiment_data,
        )

        isinstance(experiment_config, ExperimentConfig)
        assert experiment_config.path == "/tmp/sub_experiment.yml"
        assert experiment_config.extend == "experiment.py"

        # Computed properties
        assert experiment_config.name is not None
        assert experiment_config.name == "sub_experiment"

        assert experiment_config.base_path is not None
        assert experiment_config.base_path == "/tmp"

        assert experiment_config.namespace is not None
        assert experiment_config.namespace == "results/sub_experiment"

    def test_loading_experiment_config_yaml_works(self):

        config_path = os.path.join(ASSETS_PATH, "mock_config.yml")
        with open(config_path) as file:
            config_data = yaml.load(file, Loader=yaml.FullLoader)

        experiment_config = ExperimentConfig(
            path=config_path,
            **config_data,
        )

        assert experiment_config.path == config_path
        assert experiment_config.name == "mock_config"
        assert experiment_config.base_path is not None

    def test_experiment_from_config_works(self):
        """
        The Experiment.from_config method should work to construct an Experiment instance
        based on an experiment config file.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:

            config_path = os.path.join(ASSETS_PATH, "mock_config.yml")

            experiment = Experiment.from_config(
                config_path=config_path,
            )
            assert isinstance(experiment, Experiment)
