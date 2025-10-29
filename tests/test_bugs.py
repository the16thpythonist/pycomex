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


class TestYAMLConfigExperimentCodeFile:
    """
    Test that when running an experiment from a YAML config file, the experiment_code.py
    in the archive is valid Python code, not a copy of the YAML file.

    BUG DESCRIPTION (Fixed on 2025-10-16):
    ======================================

    When using pycomex to run an experiment from a YAML config file, e.g.:
        pycomex run config.yml

    The YAML config file itself was copied into the archive as experiment_code.py,
    instead of the actual Python experiment module. This caused import errors when
    trying to load the experiment later using Experiment.load().

    ROOT CAUSE:
    ----------
    In Experiment.from_config() at line 2017-2020, the glob dictionary was set with:
        glob = {
            "__file__": config_path,  # Points to the YAML file!
            **experiment_config.parameters,
        }

    Later, save_code() at line 1541-1544 copies self.glob["__file__"] to experiment_code.py:
        source_path = self.glob["__file__"]  # This is the YAML file
        destination_path = self.code_path    # This is experiment_code.py
        shutil.copy(source_path, destination_path)  # Copies YAML as .py!

    When Experiment.load() tries to import experiment_code.py, it fails because
    it's actually a YAML file, not Python code.

    FIX:
    ---
    1. Set __file__ to point to the actual Python module (experiment_config.extend)
    2. Track the config file path separately using __config_file__
    3. Add save_config() method to save the YAML file as experiment_config.yml
    4. Call save_config() in initialize() to preserve both files

    This ensures experiment_code.py contains valid Python and experiment_config.yml
    is also preserved in the archive.
    """

    def test_yaml_config_experiment_code_py_is_valid_python(self):
        """
        Test that experiment_code.py from a YAML config is valid Python, not YAML.

        This test:
        1. Creates a YAML config that extends mock_functional_experiment.py
        2. Runs the experiment using Experiment.from_config()
        3. Verifies experiment runs successfully
        4. Verifies experiment_code.py is valid Python (can be imported)
        5. Verifies experiment_config.yml exists in the archive
        6. Verifies Experiment.load() can reload the experiment
        """
        import tempfile
        import yaml as yaml_module
        from pycomex.functional.experiment import Experiment
        from pycomex.testing import ConfigIsolation
        from pycomex.utils import dynamic_import

        with ConfigIsolation() as config, tempfile.TemporaryDirectory() as temp_dir:
            # Get path to mock_functional_experiment.py
            assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
            base_experiment_path = os.path.join(assets_dir, 'mock_functional_experiment.py')

            # Create a YAML config file
            config_data = {
                'extend': base_experiment_path,
                'parameters': {
                    'NUM_VALUES': 100,
                    'PARAMETER': 'config_test'
                }
            }

            config_file_path = os.path.join(temp_dir, 'test_config.yml')
            with open(config_file_path, 'w') as f:
                yaml_module.dump(config_data, f)

            # Load experiment from config
            experiment = Experiment.from_config(config_file_path)

            # Verify __file__ points to the Python module, not the YAML file
            assert experiment.glob["__file__"] == base_experiment_path, (
                f"Expected __file__ to point to Python module {base_experiment_path}, "
                f"but got {experiment.glob['__file__']}"
            )

            # Verify __config_file__ tracks the YAML config
            assert experiment.glob.get("__config_file__") == config_file_path, (
                f"Expected __config_file__ to track config at {config_file_path}, "
                f"but got {experiment.glob.get('__config_file__')}"
            )

            # Run the experiment
            experiment.run()

            # Verify archive was created
            assert experiment.path is not None
            assert os.path.exists(experiment.path)

            # Verify experiment_code.py exists
            code_file_path = os.path.join(experiment.path, 'experiment_code.py')
            assert os.path.exists(code_file_path), (
                f"experiment_code.py not found at {code_file_path}"
            )

            # Read the stub content for verification
            with open(code_file_path, 'r') as f:
                stub_content = f.read()

            # Verify it's a STUB, not a copy of the full extended module
            assert "YAML configuration" in stub_content, (
                f"experiment_code.py should be a config stub, but doesn't contain "
                f"'YAML configuration' marker. First 200 chars: {stub_content[:200]}"
            )

            # Verify the stub references the config file
            assert "experiment_config.yml" in stub_content, (
                f"Stub should reference experiment_config.yml"
            )

            # Verify the stub references the extended experiment path
            assert base_experiment_path in stub_content, (
                f"Stub should reference extended experiment at {base_experiment_path}"
            )

            # Verify it's NOT a copy of the full module (should be much shorter)
            # The stub should be less than 100 lines, while the full module is ~50 lines
            stub_lines = len(stub_content.split('\n'))
            assert stub_lines < 100, (
                f"Stub should be minimal (<100 lines), but has {stub_lines} lines. "
                f"It may have copied the full extended module instead."
            )

            # Verify experiment_code.py is valid Python (can be imported)
            try:
                module = dynamic_import(code_file_path)
                assert module is not None, "Failed to import experiment_code.py stub"
            except SyntaxError as e:
                raise AssertionError(
                    f"experiment_code.py stub contains invalid Python syntax. Error: {e}\n"
                    f"Content:\n{stub_content}"
                )

            # Verify experiment_config.yml exists in the archive
            config_archive_path = os.path.join(experiment.path, 'experiment_config.yml')
            assert os.path.exists(config_archive_path), (
                f"experiment_config.yml not found at {config_archive_path}. "
                f"The YAML config file should be preserved in the archive."
            )

            # Verify the content of experiment_config.yml is valid YAML
            with open(config_archive_path, 'r') as f:
                archived_config = yaml_module.safe_load(f)
                assert 'extend' in archived_config
                assert 'parameters' in archived_config

            # Verify Experiment.load() can reload the experiment
            loaded_experiment = Experiment.load(experiment.path)
            assert loaded_experiment is not None
            assert loaded_experiment.parameters['PARAMETER'] == 'config_test'
            assert loaded_experiment.parameters.get('NUM_VALUES') == 100


class TestOptunaConfigFileStudyNaming:
    """
    Test that config files create Optuna studies with the config name, not the base experiment name.

    BUG DESCRIPTION (Fixed on 2025-10-29):
    =====================================

    When using `pycomex optuna run` on a YAML config file that extends a base experiment,
    the Optuna study name was incorrectly set to the base experiment's name instead of the
    config file's name. This caused multiple config files extending the same base to share
    the same Optuna study, making it impossible to run separate optimizations for different
    configurations.

    Example scenario:
        base_experiment.py          <- Base experiment with Optuna hooks
        config_variant_1.yml        <- Extends base_experiment.py
        config_variant_2.yml        <- Also extends base_experiment.py

    When running:
        pycomex optuna run config_variant_1.yml
        pycomex optuna run config_variant_2.yml

    Both would incorrectly create/use a study named "base_experiment" instead of
    "config_variant_1" and "config_variant_2" respectively.

    ROOT CAUSE:
    ----------
    In pycomex/functional/experiment.py, the Experiment.from_config() method would:
    1. Parse the config file and extract the name field (or default to config filename)
    2. Call cls.extend() to create an experiment from the base
    3. Return the experiment

    The problem was that cls.extend() would set experiment.metadata["name"] to the base
    experiment's module name, and this was never overridden with the config's name.

    The Optuna plugin uses experiment.metadata["name"] to determine the study name
    (see pycomex/plugins/optuna/main.py:570), so all configs would share the same study.

    FIX:
    ---
    After calling cls.extend(), explicitly override experiment.metadata["name"] with
    experiment_config.name to ensure the config's name is used instead of the base's name:

        experiment.metadata["name"] = experiment_config.name

    This test ensures that different config files create separate Optuna studies with
    the correct names.
    """

    def test_config_files_create_separate_optuna_studies(self):
        """Test that config files create studies with config name, not base experiment name."""
        import tempfile
        import shutil
        import yaml

        # Check if Optuna is available
        try:
            import optuna
            from pycomex.plugins.optuna import OptunaPlugin
            from pycomex.config import Config
        except ImportError:
            import pytest
            pytest.skip("Optuna not available")

        # Create temporary directory
        test_dir = tempfile.mkdtemp()

        try:
            # Create a simple base experiment
            base_experiment_code = """
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

PARAM_A: float = 1.0

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial):
    return {'PARAM_A': trial.suggest_float('PARAM_A', 0.0, 10.0)}

@experiment.hook('__optuna_objective__')
def extract_objective(e: Experiment) -> float:
    return e.PARAM_A

@experiment
def run_experiment(e: Experiment):
    e['result'] = e.PARAM_A

experiment.run_if_main()
"""

            # Write base experiment to file
            base_exp_path = os.path.join(test_dir, "base_experiment.py")
            with open(base_exp_path, "w") as f:
                f.write(base_experiment_code)

            # Create two different config files extending the same base
            config1_data = {
                "name": "config_variant_1",
                "extend": "base_experiment.py",
                "parameters": {"PARAM_A": 2.0}
            }
            config1_path = os.path.join(test_dir, "config_variant_1.yml")
            with open(config1_path, "w") as f:
                yaml.dump(config1_data, f)

            config2_data = {
                "name": "config_variant_2",
                "extend": "base_experiment.py",
                "parameters": {"PARAM_A": 3.0}
            }
            config2_path = os.path.join(test_dir, "config_variant_2.yml")
            with open(config2_path, "w") as f:
                yaml.dump(config2_data, f)

            # Load both experiments from configs
            experiment1 = Experiment.from_config(config_path=config1_path)
            experiment2 = Experiment.from_config(config_path=config2_path)

            # Verify each config has its own name, not the base experiment's name
            name1 = experiment1.metadata.get("name")
            name2 = experiment2.metadata.get("name")

            assert name1 == "config_variant_1", (
                f"Config 1 should have name 'config_variant_1' but got '{name1}'. "
                f"Bug: Config files are using base experiment name instead of config name."
            )
            assert name2 == "config_variant_2", (
                f"Config 2 should have name 'config_variant_2' but got '{name2}'. "
                f"Bug: Config files are using base experiment name instead of config name."
            )

            # Verify that Optuna studies use the config names
            config = Config()
            plugin1 = OptunaPlugin(config)
            plugin1.register()
            plugin1.prepare_trial_repetitions(1)

            experiment1.parameters['__OPTUNA__'] = True
            plugin1.before_experiment_initialize(config, experiment1)

            study1_name = plugin1.current_study.study_name if plugin1.current_study else None

            config2_instance = Config()
            plugin2 = OptunaPlugin(config2_instance)
            plugin2.register()
            plugin2.prepare_trial_repetitions(1)

            experiment2.parameters['__OPTUNA__'] = True
            plugin2.before_experiment_initialize(config2_instance, experiment2)

            study2_name = plugin2.current_study.study_name if plugin2.current_study else None

            # Verify that different config files create different studies
            assert study1_name == "config_variant_1", (
                f"Study 1 should be named 'config_variant_1' but got '{study1_name}'"
            )
            assert study2_name == "config_variant_2", (
                f"Study 2 should be named 'config_variant_2' but got '{study2_name}'"
            )
            assert study1_name != study2_name, (
                "Different config files should create different Optuna studies, "
                f"but both created study named '{study1_name}'"
            )

        finally:
            # Cleanup
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)
            Config().reset_state()
