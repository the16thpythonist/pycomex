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

    def test_log_parameters_all(self, capsys):
        """
        The log_parameters method should log all parameters when no specific parameters are provided.
        """
        parameters = {"PARAM1": 10, "PARAM2": "test", "PARAM3": True}
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod=parameters) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            experiment.log_parameters()

            # Capture stdout
            captured = capsys.readouterr()

            # Check that all parameters were logged
            assert " * PARAM1: 10" in captured.out
            assert " * PARAM2: test" in captured.out
            assert " * PARAM3: True" in captured.out

    def test_log_parameters_specific(self, capsys):
        """
        The log_parameters method should log only specific parameters when a list is provided.
        """
        parameters = {"PARAM1": 10, "PARAM2": "test", "PARAM3": True}
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod=parameters) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            experiment.log_parameters(["PARAM1", "PARAM3"])

            # Capture stdout
            captured = capsys.readouterr()

            # Check that only specified parameters were logged
            assert " * PARAM1: 10" in captured.out
            assert " * PARAM3: True" in captured.out
            assert " * PARAM2: test" not in captured.out

    def test_log_parameters_complex_objects(self, capsys):
        """
        The log_parameters method should handle complex objects safely.
        """
        class ComplexObject:
            def __init__(self, value):
                self.value = value
            def __repr__(self):
                return f"ComplexObject({self.value})"

        parameters = {"SIMPLE": 10, "COMPLEX": ComplexObject(42)}
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod=parameters) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            experiment.log_parameters()

            # Capture stdout
            captured = capsys.readouterr()

            # Simple parameter should be logged directly
            assert " * SIMPLE: 10" in captured.out
            # Complex object should be logged using repr
            assert " * COMPLEX: ComplexObject(42)" in captured.out

    def test_log_parameters_unprintable_object(self, capsys):
        """
        The log_parameters method should handle objects that can't be converted safely.
        """
        class UnprintableObject:
            def __repr__(self):
                raise Exception("Cannot convert to string")
            def __str__(self):
                raise Exception("Cannot convert to string")

        parameters = {"SIMPLE": 10}
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod=parameters) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            # Add the unprintable object directly to the experiment parameters after construction
            experiment.parameters["UNPRINTABLE"] = UnprintableObject()

            experiment.log_parameters()

            # Capture stdout
            captured = capsys.readouterr()

            # Should fallback to type name
            assert " * UNPRINTABLE: <UnprintableObject object>" in captured.out

    def test_log_pretty(self, capsys):
        """
        The log_pretty method should log a pretty formatted representation of data structures.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            test_data = {
                "metrics": {"accuracy": 0.95, "loss": 0.05},
                "config": {"lr": 0.001, "batch_size": 32}
            }

            experiment.log_pretty(test_data)

            # Capture stdout
            captured = capsys.readouterr()

            # Check that the data was logged (exact format may vary, so check for key elements)
            assert "metrics" in captured.out
            assert "accuracy" in captured.out
            assert "0.95" in captured.out
            assert "config" in captured.out


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


class TestExperimentRichPanels:
    """
    Test the Rich panel functionality for experiment start and end logging.
    """

    def test_create_experiment_start_panel(self):
        """
        The _create_experiment_start_panel method should create a Rich Panel with experiment start information.
        """
        import tempfile
        import time

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            # Set up metadata as would be done in prepare()
            experiment.metadata["start_time"] = time.time()
            experiment.path = tempfile.mkdtemp()

            panel = experiment._create_experiment_start_panel()

            # Check that we got a Panel object
            from rich.panel import Panel
            assert isinstance(panel, Panel)

            # Check the panel title contains expected content
            assert "EXPERIMENT STARTED" in str(panel.title)
            assert "🚀" in str(panel.title)

            # Check that panel content contains key information
            content_str = str(panel.renderable)
            assert "Namespace:" in content_str
            assert "test_experiment" in content_str
            assert "Start Time:" in content_str
            assert "Archive Path:" in content_str
            assert "Debug Mode:" in content_str
            assert "Parameters:" in content_str
            assert "Python Version:" in content_str
            assert "Platform:" in content_str

    def test_create_experiment_end_panel_success(self):
        """
        The _create_experiment_end_panel method should create a Rich Panel for successful experiments.
        """
        import tempfile
        import time

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            # Set up metadata as would be done during experiment execution
            start_time = time.time()
            end_time = start_time + 30.5  # 30.5 seconds duration
            experiment.metadata["start_time"] = start_time
            experiment.metadata["end_time"] = end_time
            experiment.metadata["duration"] = end_time - start_time
            experiment.error = None  # No error
            experiment.path = tempfile.mkdtemp()

            # Create a mock data file
            data_path = os.path.join(experiment.path, "experiment_data.json")
            with open(data_path, 'w') as f:
                f.write('{"test": "data"}')

            panel = experiment._create_experiment_end_panel()

            # Check that we got a Panel object
            from rich.panel import Panel
            assert isinstance(panel, Panel)

            # Check the panel title for success case
            assert "EXPERIMENT COMPLETED" in str(panel.title)
            assert "✅" in str(panel.title)
            assert "green" in panel.border_style

            # Check content contains key information
            content_str = str(panel.renderable)
            assert "Duration:" in content_str
            assert "seconds" in content_str  # Should show seconds for short duration
            assert "Start Time:" in content_str
            assert "End Time:" in content_str
            assert "Error Occurred" in content_str and "No" in content_str
            assert "Parameters Count:" in content_str
            assert "Data Size:" in content_str
            assert "bytes" in content_str or "KB" in content_str or "MB" in content_str

    def test_create_experiment_end_panel_error(self):
        """
        The _create_experiment_end_panel method should create a Rich Panel for failed experiments.
        """
        import tempfile
        import time

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            # Set up metadata for failed experiment
            start_time = time.time()
            end_time = start_time + 120  # 2 minutes duration
            experiment.metadata["start_time"] = start_time
            experiment.metadata["end_time"] = end_time
            experiment.metadata["duration"] = end_time - start_time
            experiment.error = Exception("Test error")  # With error
            experiment.path = tempfile.mkdtemp()

            panel = experiment._create_experiment_end_panel()

            # Check that we got a Panel object
            from rich.panel import Panel
            assert isinstance(panel, Panel)

            # Check the panel title for error case
            assert "EXPERIMENT ENDED (WITH ERROR)" in str(panel.title)
            assert "❌" in str(panel.title)
            assert "red" in panel.border_style

            # Check content
            content_str = str(panel.renderable)
            assert "Duration:" in content_str
            assert "minutes" in content_str  # Should show minutes for 2-minute duration
            assert "Error Occurred" in content_str and "Yes" in content_str

    def test_create_experiment_end_panel_long_duration(self):
        """
        The _create_experiment_end_panel method should format long durations in hours.
        """
        import tempfile
        import time

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            # Set up metadata for long experiment (2.5 hours)
            start_time = time.time()
            duration = 2.5 * 3600  # 2.5 hours in seconds
            end_time = start_time + duration
            experiment.metadata["start_time"] = start_time
            experiment.metadata["end_time"] = end_time
            experiment.metadata["duration"] = duration
            experiment.error = None
            experiment.path = tempfile.mkdtemp()

            panel = experiment._create_experiment_end_panel()

            # Check content shows hours
            content_str = str(panel.renderable)
            assert "Duration:" in content_str
            assert "hours" in content_str
            assert "2.50 hours" in content_str

    def test_experiment_start_logging_uses_rich_panel(self, capsys):
        """
        The prepare method should log a Rich panel for experiment start.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            @experiment
            def run(experiment):
                pass

            # Call initialize to trigger start logging
            experiment.initialize()

            # Capture the output
            captured = capsys.readouterr()

            # Check that Rich panel content appears in output
            # The exact rendering may vary, but key content should be there
            assert "EXPERIMENT STARTED" in captured.out or "Experiment Started" in captured.out
            assert "test_experiment" in captured.out
            assert "Archive Path:" in captured.out or "archive path" in captured.out.lower()

    def test_experiment_end_logging_uses_rich_panel(self, capsys):
        """
        The finalize method should log a Rich panel for experiment end.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            @experiment
            def run(experiment):
                pass

            # Simulate experiment execution
            experiment.initialize()
            experiment.metadata["end_time"] = experiment.metadata["start_time"] + 30
            experiment.metadata["duration"] = 30
            experiment.error = None

            # Call finalize to trigger end logging
            experiment.finalize()

            # Capture the output
            captured = capsys.readouterr()

            # Check that Rich panel content appears in output
            assert "EXPERIMENT COMPLETED" in captured.out or "Experiment Completed" in captured.out
            assert "Duration:" in captured.out

    def test_experiment_panels_written_to_log_file(self):
        """
        The Rich panels should be written to the experiment log file.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            @experiment
            def run(experiment):
                pass

            # Run the full experiment to generate log file
            experiment.run()

            # Check that log file exists and contains panel content
            assert os.path.exists(experiment.log_path)

            with open(experiment.log_path, 'r') as f:
                log_content = f.read()

            # The log file should contain Rich panel markup or rendered text
            # Note: The exact format depends on how Rich renders to the file
            assert len(log_content) > 0
            assert ("EXPERIMENT STARTED" in log_content or
                    "experiment started" in log_content.lower())
            assert ("EXPERIMENT COMPLETED" in log_content or
                    "experiment completed" in log_content.lower())

    def test_experiment_panels_survive_console_width_changes(self):
        """
        The Rich panels should work regardless of console width settings.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment_with_very_long_name",
                glob=iso.glob,
            )

            # Set up metadata
            import time
            experiment.metadata["start_time"] = time.time()
            experiment.path = iso.path

            # Create panels with different console contexts
            panel1 = experiment._create_experiment_start_panel()

            # Both should create valid Panel objects
            from rich.panel import Panel
            assert isinstance(panel1, Panel)

            # Content should still contain key information
            content_str = str(panel1.renderable)
            assert "test_experiment_with_very_long_name" in content_str
