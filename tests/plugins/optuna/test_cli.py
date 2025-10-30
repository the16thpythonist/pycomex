"""
Unit tests for Optuna plugin CLI commands.

Tests the command-line interface functionality of the Optuna plugin including
the run, list, info, and delete commands.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pycomex.config import Config
from pycomex.cli.main import CLI

# Try to import optuna and plugin
try:
    import optuna
    from pycomex.plugins.optuna import OptunaPlugin, StudyManager
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    OptunaPlugin = None
    StudyManager = None


@unittest.skipIf(not OPTUNA_AVAILABLE, "Optuna not available")
class TestOptunaCLICommands(unittest.TestCase):
    """Test cases for Optuna CLI commands."""

    def setUp(self):
        """Set up test fixtures."""
        Config().reset_state()
        self.config = Config()

        # Create temporary directory for tests
        self.test_dir = tempfile.mkdtemp()

        # Create CLI instance with Optuna plugin
        self.cli = CLI()
        self.plugin = OptunaPlugin(self.config)
        self.plugin.register()

        # Register plugin commands with CLI (they get registered during CLI.__init__ via hooks)
        # but we need to do it manually here since we're creating CLI after plugin registration
        self.plugin.register_cli_commands(self.config, self.cli)

        # Create Click test runner
        self.runner = CliRunner()

        # Create study manager for test setup
        self.study_manager = StudyManager(self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def test_list_command_empty(self):
        """Test 'list' command when no studies exist."""
        # Change to test directory
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'list'],
                obj=self.cli
            )

            self.assertEqual(result.exit_code, 0)
            # Should show message about no studies
            self.assertIn("No Optuna studies found", result.output)

    def test_list_command_with_studies(self):
        """Test 'list' command with existing studies."""
        # Create some test studies
        study1 = self.study_manager.get_or_create_study("test_study_1", direction="maximize")
        study2 = self.study_manager.get_or_create_study("test_study_2", direction="minimize")

        # Add trials to studies
        trial1 = study1.ask()
        study1.tell(trial1, 0.8)

        trial2 = study2.ask()
        study2.tell(trial2, 0.6)

        # Run list command
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'list'],
                obj=self.cli
            )

            self.assertEqual(result.exit_code, 0)
            # Should show both studies
            self.assertIn("test_study_1", result.output)
            self.assertIn("test_study_2", result.output)

    def test_info_command_existing_study(self):
        """Test 'info' command for an existing study."""
        # Create a study with trials
        study = self.study_manager.get_or_create_study("test_study", direction="maximize")

        # Add multiple trials
        for i in range(3):
            trial = study.ask()
            study.tell(trial, float(i) * 0.1)

        # Run info command
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'info', 'test_study'],
                obj=self.cli
            )

            self.assertEqual(result.exit_code, 0)
            # Should show study information
            self.assertIn("test_study", result.output)
            self.assertIn("3", result.output)  # 3 trials

    def test_info_command_nonexistent_study(self):
        """Test 'info' command for a nonexistent study."""
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'info', 'nonexistent_study'],
                obj=self.cli
            )

            # Should show error message
            self.assertIn("Error", result.output)
            self.assertIn("not found", result.output.lower())

    def test_delete_command_specific_study_with_confirmation(self):
        """Test 'delete' command for a specific study with confirmation."""
        # Create a study
        self.study_manager.get_or_create_study("test_study")

        # Verify database exists
        db_path = Path(self.test_dir) / '.optuna' / 'test_study.db'
        self.assertTrue(db_path.exists())

        # Run delete command with --yes flag (skip confirmation)
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'delete', 'test_study', '--yes'],
                obj=self.cli
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("deleted successfully", result.output.lower())
            # Verify database was deleted
            self.assertFalse(db_path.exists())

    def test_delete_command_nonexistent_study(self):
        """Test 'delete' command for a nonexistent study."""
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'delete', 'nonexistent_study', '--yes'],
                obj=self.cli
            )

            # Should show error message
            self.assertIn("Error", result.output)
            self.assertIn("not found", result.output.lower())

    def test_delete_all_studies(self):
        """Test 'delete' command with --all flag."""
        # Create multiple studies
        self.study_manager.get_or_create_study("study1")
        self.study_manager.get_or_create_study("study2")
        self.study_manager.get_or_create_study("study3")

        # Verify databases exist
        for name in ["study1", "study2", "study3"]:
            db_path = Path(self.test_dir) / '.optuna' / f'{name}.db'
            self.assertTrue(db_path.exists())

        # Run delete command with --all and --yes flags
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'delete', '--all', '--yes'],
                obj=self.cli
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Deleted 3 studies", result.output)

            # Verify all databases were deleted
            for name in ["study1", "study2", "study3"]:
                db_path = Path(self.test_dir) / '.optuna' / f'{name}.db'
                self.assertFalse(db_path.exists())

    def test_delete_command_without_study_name_or_all(self):
        """Test 'delete' command without providing study name or --all flag."""
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'delete'],
                obj=self.cli
            )

            # Should show error message
            self.assertIn("Error", result.output)

    def test_run_command_with_experiment_file(self):
        """Test 'run' command with a Python experiment file."""
        # Create a simple test experiment
        experiment_code = """
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

PARAM_A: float = 1.0
PARAM_B: int = 10

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial):
    return {
        'PARAM_A': trial.suggest_float('PARAM_A', 0.0, 10.0),
        'PARAM_B': trial.suggest_int('PARAM_B', 1, 20)
    }

@experiment.hook('__optuna_objective__')
def extract_objective(e: Experiment) -> float:
    return e.PARAM_A + e.PARAM_B

@experiment
def run_experiment(e: Experiment):
    result = e.PARAM_A + e.PARAM_B
    e['result'] = result

__experiment__ = experiment
"""

        # Write experiment to file
        exp_path = os.path.join(self.test_dir, "test_experiment.py")
        with open(exp_path, "w") as f:
            f.write(experiment_code)

        # Run the command
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'run', exp_path],
                obj=self.cli
            )

            # Should complete successfully
            self.assertEqual(result.exit_code, 0, f"Command failed with output: {result.output}")
            self.assertIn("Running experiment with Optuna optimization", result.output)

            # Verify a study was created
            studies = self.study_manager.list_studies()
            self.assertGreater(len(studies), 0)

    def test_report_command_basic(self):
        """Test 'report' command generates HTML report."""
        # Create a study with trials
        study = self.study_manager.get_or_create_study("test_report_study", direction="maximize")

        for i in range(10):
            trial = study.ask()
            param_a = trial.suggest_float('param_a', 0.0, 10.0)
            param_b = trial.suggest_int('param_b', 1, 100)
            objective = -(param_a - 5.0)**2 - (param_b - 50)**2
            study.tell(trial, objective)

        # Run report command with explicit output directory
        output_dir = os.path.join(self.test_dir, 'test_report_study_report')
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'report', 'test_report_study', '--output', output_dir],
                obj=self.cli
            )

            self.assertEqual(result.exit_code, 0, f"Command failed: {result.output}")
            self.assertIn("Report generated successfully", result.output)

            # Verify report folder was created
            report_path = Path(output_dir)
            self.assertTrue(report_path.exists())
            self.assertTrue((report_path / 'index.html').exists())
            self.assertTrue((report_path / 'plots').exists())

    def test_report_command_custom_output(self):
        """Test 'report' command with custom output directory."""
        # Create a study
        study = self.study_manager.get_or_create_study("test_custom_report")

        for i in range(5):
            trial = study.ask()
            param = trial.suggest_float('param', 0.0, 10.0)
            study.tell(trial, param)

        # Run report command with custom output
        custom_output = os.path.join(self.test_dir, "custom_report_folder")

        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'report', 'test_custom_report', '--output', custom_output],
                obj=self.cli
            )

            self.assertEqual(result.exit_code, 0)
            # Verify custom folder was used
            self.assertTrue(Path(custom_output).exists())
            self.assertTrue((Path(custom_output) / 'index.html').exists())

    def test_report_command_nonexistent_study(self):
        """Test 'report' command for a nonexistent study."""
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                self.cli,
                ['optuna', 'report', 'nonexistent_study'],
                obj=self.cli
            )

            # Should show error message
            self.assertIn("Error", result.output)
            self.assertIn("not found", result.output.lower())


@unittest.skipIf(not OPTUNA_AVAILABLE, "Optuna not available")
class TestOptunaCLIIntegration(unittest.TestCase):
    """Integration tests for Optuna CLI with real experiment execution."""

    def setUp(self):
        """Set up test fixtures."""
        Config().reset_state()
        self.test_dir = tempfile.mkdtemp()
        self.runner = CliRunner()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def test_full_cli_workflow(self):
        """Test complete CLI workflow: run -> list -> info -> delete."""
        # Create a test experiment
        experiment_code = """
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

__DEBUG__ = True

PARAM_X: float = 1.0

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial):
    return {
        'PARAM_X': trial.suggest_float('PARAM_X', 0.0, 5.0),
    }

@experiment.hook('__optuna_objective__')
def extract_objective(e: Experiment) -> float:
    # Simple quadratic objective
    return -(e.PARAM_X - 2.5) ** 2

@experiment
def run_experiment(e: Experiment):
    e['objective'] = -(e.PARAM_X - 2.5) ** 2

__experiment__ = experiment
"""

        exp_path = os.path.join(self.test_dir, "workflow_test.py")
        with open(exp_path, "w") as f:
            f.write(experiment_code)

        # Create CLI instance
        config = Config()
        cli = CLI()
        plugin = OptunaPlugin(config)
        plugin.register()
        plugin.register_cli_commands(config, cli)

        # Step 1: Run experiment
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                cli,
                ['optuna', 'run', exp_path],
                obj=cli
            )
            self.assertEqual(result.exit_code, 0, f"Run failed: {result.output}")

        # Step 2: List studies
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                cli,
                ['optuna', 'list'],
                obj=cli
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("workflow_test", result.output)

        # Step 3: Show info
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                cli,
                ['optuna', 'info', 'workflow_test'],
                obj=cli
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("workflow_test", result.output)

        # Step 4: Delete study
        with patch('os.getcwd', return_value=self.test_dir):
            result = self.runner.invoke(
                cli,
                ['optuna', 'delete', 'workflow_test', '--yes'],
                obj=cli
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("deleted successfully", result.output.lower())


if __name__ == '__main__':
    unittest.main()
