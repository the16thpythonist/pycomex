"""
Test that __DEBUG__ parameter override works correctly when using CLI run command.

BUG DESCRIPTION (Fixed on 2025-10-15):
=====================================

When using the CLI to run an experiment with parameter overrides, e.g.:
    pycomex run experiment.py --__DEBUG__=False

The __DEBUG__ parameter value was correctly updated in self.parameters['__DEBUG__']
and appeared correctly in the experiment_meta.json file. However, the actual debug
mode behavior was not affected - the experiment would still run in debug mode.

ROOT CAUSE:
----------
The CLI's run_command() method in pycomex/cli/commands/run.py would:
1. Call experiment.arg_parser.parse(experiment_parameters) to parse CLI args
   - This updated self.parameters['__DEBUG__']
2. Call experiment.run() to execute the experiment
   - This directly called execute() without syncing special parameters

The problem was that special parameters like __DEBUG__ have side effects:
- __DEBUG__ controls the self.debug attribute
- self.debug is checked in prepare_path() to determine the archive folder name

The update_parameters_special() method syncs self.parameters['__DEBUG__'] to self.debug,
but it was never called after CLI parameter parsing in the run_command() flow.

In contrast, run_if_main() (used when running experiments directly) correctly called
update_parameters_special() after arg_parser.parse() and before execute().

This test ensures that __DEBUG__ CLI overrides work correctly and that both the
parameter value AND the actual behavior (archive folder naming) are synchronized.
"""

import os
import sys
import tempfile

from pycomex.functional.experiment import Experiment
from pycomex.testing import ConfigIsolation, ExperimentIsolation


class TestDebugModeCLIOverride:
    """
    Test that __DEBUG__ parameter can be overridden via CLI and actually affects behavior.
    """

    def test_debug_mode_false_override_works(self):
        """
        When running an experiment with __DEBUG__=False via CLI override, the experiment
        should NOT run in debug mode, even if the experiment was initialized with debug=True.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            # Create an experiment that is initialized with debug=True
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_debug",
                glob=iso.glob,
                debug=True,  # Initially set to True
            )

            @experiment
            def run(e):
                e.log("Test experiment")

            # Simulate CLI override with __DEBUG__=False
            experiment.arg_parser.parse(["--__DEBUG__=False"])

            # This is the critical call that was missing in the CLI code!
            # Without this, self.debug doesn't get updated from self.parameters['__DEBUG__']
            experiment.update_parameters_special()

            # Verify that the parameter was updated
            assert experiment.parameters["__DEBUG__"] is False

            # Verify that self.debug was also updated (this is the bug fix)
            assert experiment.debug is False

            # Run the experiment
            experiment.run()

            # Verify that the archive folder is NOT named "debug"
            # (which would be the case if debug mode was still active)
            assert experiment.path is not None
            archive_folder_name = os.path.basename(experiment.path)
            assert archive_folder_name != "debug", (
                f"Expected non-debug folder name, but got '{archive_folder_name}'. "
                "This indicates that debug mode was still active despite __DEBUG__=False."
            )

            # Also verify in metadata
            assert experiment.metadata["parameters"]["__DEBUG__"]["value"] is False

    def test_debug_mode_true_override_works(self):
        """
        When running an experiment with __DEBUG__=True via CLI override, the experiment
        should run in debug mode, even if it was initialized with debug=False.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            # Create an experiment that is initialized with debug=False
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_debug",
                glob=iso.glob,
                debug=False,  # Initially set to False
            )

            @experiment
            def run(e):
                e.log("Test experiment")

            # Simulate CLI override with __DEBUG__=True
            experiment.arg_parser.parse(["--__DEBUG__=True"])

            # This is the critical call that was missing in the CLI code!
            experiment.update_parameters_special()

            # Verify that the parameter was updated
            assert experiment.parameters["__DEBUG__"] is True

            # Verify that self.debug was also updated
            assert experiment.debug is True

            # Run the experiment
            experiment.run()

            # Verify that the archive folder IS named "debug"
            assert experiment.path is not None
            archive_folder_name = os.path.basename(experiment.path)
            assert archive_folder_name == "debug", (
                f"Expected 'debug' folder name, but got '{archive_folder_name}'. "
                "This indicates that debug mode was not activated despite __DEBUG__=True."
            )

            # Also verify in metadata
            assert experiment.metadata["parameters"]["__DEBUG__"]["value"] is True

    def test_debug_mode_parameter_default_value(self):
        """
        When no CLI override is provided, the debug mode should match the __DEBUG__ parameter value.
        Note: The debug constructor parameter gets overwritten by parameter discovery.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod={"__DEBUG__": True}) as iso:
            # Create experiment with __DEBUG__ parameter set to True in glob
            experiment_debug = Experiment(
                base_path=iso.path,
                namespace="test_debug_default_true",
                glob=iso.glob,
            )

            @experiment_debug
            def run(e):
                e.log("Test experiment")

            # Don't parse any CLI args - use defaults from parameters
            experiment_debug.run()

            # Should be in debug mode (from __DEBUG__ parameter)
            assert experiment_debug.debug is True
            assert os.path.basename(experiment_debug.path) == "debug"

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod={"__DEBUG__": False}) as iso:
            # Create experiment with __DEBUG__ parameter set to False in glob
            experiment_no_debug = Experiment(
                base_path=iso.path,
                namespace="test_debug_default_false",
                glob=iso.glob,
            )

            @experiment_no_debug
            def run(e):
                e.log("Test experiment")

            # Don't parse any CLI args - use defaults from parameters
            experiment_no_debug.run()

            # Should NOT be in debug mode (from __DEBUG__ parameter)
            assert experiment_no_debug.debug is False
            assert os.path.basename(experiment_no_debug.path) != "debug"
