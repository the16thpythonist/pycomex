"""
Unit tests for the Optuna plugin.

Tests StudyManager functionality, plugin hooks, and CLI commands.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pycomex.config import Config
from pycomex.functional.experiment import Experiment

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
class TestStudyManager(unittest.TestCase):
    """Test cases for the StudyManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test databases
        self.test_dir = tempfile.mkdtemp()
        self.study_manager = StudyManager(self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def test_init_creates_optuna_directory(self):
        """Test that initialization creates .optuna directory."""
        optuna_dir = Path(self.test_dir) / '.optuna'
        self.assertTrue(optuna_dir.exists())
        self.assertTrue(optuna_dir.is_dir())

    def test_get_storage_url(self):
        """Test storage URL generation."""
        study_name = "test_study"
        url = self.study_manager._get_storage_url(study_name)
        expected_path = Path(self.test_dir) / '.optuna' / f"{study_name}.db"
        self.assertIn(str(expected_path), url)
        self.assertTrue(url.startswith("sqlite:///"))

    def test_get_or_create_study_creates_new_study(self):
        """Test creating a new study."""
        study_name = "test_study"
        study = self.study_manager.get_or_create_study(
            study_name=study_name,
            direction="maximize"
        )

        self.assertIsNotNone(study)
        self.assertEqual(study.study_name, study_name)
        self.assertEqual(len(study.trials), 0)

        # Check database file was created
        db_path = Path(self.test_dir) / '.optuna' / f"{study_name}.db"
        self.assertTrue(db_path.exists())

    def test_get_or_create_study_loads_existing_study(self):
        """Test loading an existing study."""
        study_name = "test_study"

        # Create study and add a trial
        study1 = self.study_manager.get_or_create_study(study_name)
        trial = study1.ask()
        study1.tell(trial, 0.5)

        # Load the same study
        study2 = self.study_manager.get_or_create_study(study_name)

        self.assertEqual(len(study2.trials), 1)
        self.assertEqual(study2.study_name, study_name)

    def test_list_studies_empty(self):
        """Test listing studies when none exist."""
        studies = self.study_manager.list_studies()
        self.assertEqual(len(studies), 0)

    def test_list_studies_with_studies(self):
        """Test listing studies with multiple studies."""
        # Create multiple studies
        study1 = self.study_manager.get_or_create_study("study1")
        study2 = self.study_manager.get_or_create_study("study2")

        # Add trials to studies
        trial1 = study1.ask()
        study1.tell(trial1, 0.8)

        trial2 = study2.ask()
        study2.tell(trial2, 0.6)

        # List studies
        studies = self.study_manager.list_studies()

        self.assertEqual(len(studies), 2)
        study_names = {s['name'] for s in studies}
        self.assertEqual(study_names, {'study1', 'study2'})

        # Check study info
        for study in studies:
            self.assertIn('n_trials', study)
            self.assertIn('best_value', study)
            self.assertIn('direction', study)
            self.assertEqual(study['n_trials'], 1)

    def test_get_study_info(self):
        """Test getting detailed study information."""
        study_name = "test_study"
        study = self.study_manager.get_or_create_study(study_name)

        # Add multiple trials
        for i in range(3):
            trial = study.ask()
            study.tell(trial, float(i) * 0.1)

        # Get study info
        info = self.study_manager.get_study_info(study_name)

        self.assertEqual(info['name'], study_name)
        self.assertEqual(info['n_trials'], 3)
        self.assertIsNotNone(info['best_value'])
        self.assertEqual(len(info['trials']), 3)

        # Check trial data
        trial_data = info['trials'][0]
        self.assertIn('number', trial_data)
        self.assertIn('state', trial_data)
        self.assertIn('value', trial_data)
        self.assertIn('params', trial_data)

    def test_get_study_info_nonexistent(self):
        """Test getting info for nonexistent study."""
        with self.assertRaises(ValueError):
            self.study_manager.get_study_info("nonexistent_study")

    def test_delete_study(self):
        """Test deleting a specific study."""
        study_name = "test_study"
        self.study_manager.get_or_create_study(study_name)

        # Verify database exists
        db_path = Path(self.test_dir) / '.optuna' / f"{study_name}.db"
        self.assertTrue(db_path.exists())

        # Delete study
        success = self.study_manager.delete_study(study_name)
        self.assertTrue(success)
        self.assertFalse(db_path.exists())

    def test_delete_study_nonexistent(self):
        """Test deleting a nonexistent study."""
        success = self.study_manager.delete_study("nonexistent_study")
        self.assertFalse(success)

    def test_delete_all_studies(self):
        """Test deleting all studies."""
        # Create multiple studies
        self.study_manager.get_or_create_study("study1")
        self.study_manager.get_or_create_study("study2")
        self.study_manager.get_or_create_study("study3")

        # Delete all
        count = self.study_manager.delete_all_studies()
        self.assertEqual(count, 3)

        # Verify all deleted
        studies = self.study_manager.list_studies()
        self.assertEqual(len(studies), 0)


@unittest.skipIf(not OPTUNA_AVAILABLE, "Optuna not available")
class TestOptunaPlugin(unittest.TestCase):
    """Test cases for the OptunaPlugin class."""

    def setUp(self):
        """Set up test fixtures."""
        Config().reset_state()
        self.config = Config()
        self.plugin = OptunaPlugin(self.config)
        self.plugin.register()

        # Create temporary directory for experiments
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def test_plugin_initialization(self):
        """Test plugin initialization."""
        self.assertIsNone(self.plugin.base_path)
        self.assertIsNone(self.plugin.study_manager)
        self.assertIsNone(self.plugin.current_study)
        self.assertIsNone(self.plugin.current_trial)

    def test_before_experiment_initialize_without_optuna_flag(self):
        """Test before_experiment_initialize hook when __OPTUNA__ is not set."""
        # Create mock experiment
        experiment = Mock(spec=Experiment)
        experiment.parameters = {'__OPTUNA__': False}
        experiment.metadata = {}
        experiment.base_path = self.test_dir
        experiment.logger = Mock()

        # Call hook
        self.plugin.before_experiment_initialize(self.config, experiment)

        # Verify __optuna__ flag is False
        self.assertFalse(experiment.metadata['__optuna__'])
        # Verify no study was created
        self.assertIsNone(self.plugin.current_study)
        self.assertIsNone(self.plugin.current_trial)

    def test_before_experiment_initialize_with_optuna_flag_no_hooks(self):
        """Test before_experiment_initialize when __OPTUNA__ is True but hooks are missing."""
        # Create mock experiment
        experiment = Mock(spec=Experiment)
        experiment.parameters = {'__OPTUNA__': True}
        experiment.metadata = {}
        experiment.base_path = self.test_dir
        experiment.logger = Mock()
        experiment.hook_map = {}  # No Optuna hooks defined

        # Call hook
        self.plugin.before_experiment_initialize(self.config, experiment)

        # Verify __optuna__ flag is set to False due to missing hooks
        # (The plugin detects missing hooks and disables Optuna mode)
        self.assertFalse(experiment.metadata['__optuna__'])
        # Verify no study was created (due to missing hooks)
        self.assertIsNone(self.plugin.current_study)
        self.assertIsNone(self.plugin.current_trial)

    def test_after_experiment_finalize_without_optuna_flag(self):
        """Test after_experiment_finalize when __optuna__ is False."""
        # Create mock experiment
        experiment = Mock(spec=Experiment)
        experiment.metadata = {'__optuna__': False}
        experiment.logger = Mock()

        # Call hook (should not raise error)
        self.plugin.after_experiment_finalize(self.config, experiment)

        # Verify nothing happened (no errors)
        self.assertIsNone(self.plugin.current_study)


@unittest.skipIf(not OPTUNA_AVAILABLE, "Optuna not available")
class TestOptunaPluginIntegration(unittest.TestCase):
    """Integration tests for Optuna plugin with real experiments."""

    def setUp(self):
        """Set up test fixtures."""
        Config().reset_state()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def test_full_optimization_workflow(self):
        """Test complete optimization workflow with plugin hooks."""
        # Create a simple test using StudyManager directly
        config = Config()
        plugin = OptunaPlugin(config)
        plugin.register()

        # Create mock experiment that simulates the real behavior
        experiment = Mock(spec=Experiment)
        experiment.base_path = self.test_dir
        experiment.parameters = {
            '__OPTUNA__': True,
            'PARAM_A': 1.0,
            'PARAM_B': 2.0
        }
        experiment.metadata = {'name': 'test_experiment'}
        experiment.logger = Mock()
        experiment.hook_map = {}

        # Define Optuna hooks
        def optuna_parameters_hook(e, trial):
            return {
                'PARAM_A': trial.suggest_float('PARAM_A', 0.0, 10.0),
                'PARAM_B': trial.suggest_int('PARAM_B', 1, 10)
            }

        def optuna_objective_hook(e):
            # Simple objective: minimize distance from (5.0, 5)
            a = e.parameters['PARAM_A']
            b = e.parameters['PARAM_B']
            return -((a - 5.0)**2 + (b - 5)**2)  # Negative for maximization

        # Register hooks
        experiment.hook_map['__optuna_parameters__'] = [optuna_parameters_hook]
        experiment.hook_map['__optuna_objective__'] = [optuna_objective_hook]

        # Mock apply_hook to call the appropriate hook function
        def mock_apply_hook(hook_name, default=None, **kwargs):
            if hook_name in experiment.hook_map:
                for func in experiment.hook_map[hook_name]:
                    return func(experiment, **kwargs)
            return default

        experiment.apply_hook = mock_apply_hook

        # Test before_experiment_initialize
        plugin.before_experiment_initialize(config, experiment)

        # Verify __optuna__ flag is set
        self.assertTrue(experiment.metadata['__optuna__'])

        # Verify trial was created
        self.assertIsNotNone(plugin.current_trial)
        self.assertIsNotNone(plugin.current_study)

        # Verify parameters were replaced
        self.assertNotEqual(experiment.parameters['PARAM_A'], 1.0)
        self.assertNotEqual(experiment.parameters['PARAM_B'], 2.0)

        # Store trial values
        trial_param_a = experiment.parameters['PARAM_A']
        trial_param_b = experiment.parameters['PARAM_B']

        # Verify parameter values are within expected ranges
        self.assertGreaterEqual(trial_param_a, 0.0)
        self.assertLessEqual(trial_param_a, 10.0)
        self.assertGreaterEqual(trial_param_b, 1)
        self.assertLessEqual(trial_param_b, 10)

        # Test after_experiment_finalize
        plugin.after_experiment_finalize(config, experiment)

        # Verify trial was completed
        self.assertEqual(len(plugin.current_study.trials), 1)
        trial = plugin.current_study.trials[0]
        self.assertEqual(trial.state, optuna.trial.TrialState.COMPLETE)
        self.assertIsNotNone(trial.value)

        # Verify parameters match
        self.assertEqual(trial.params['PARAM_A'], trial_param_a)
        self.assertEqual(trial.params['PARAM_B'], trial_param_b)


if __name__ == '__main__':
    unittest.main()
