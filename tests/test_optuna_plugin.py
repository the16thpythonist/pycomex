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
        # Note: Need to prepare repetitions (unified multi-run architecture)
        plugin.prepare_trial_repetitions(1)
        plugin.before_experiment_initialize(config, experiment)

        # Verify __optuna__ flag is set
        self.assertTrue(experiment.metadata['__optuna__'])

        # Verify trial was created
        self.assertIsNotNone(plugin.current_trial)
        self.assertIsNotNone(plugin.current_study)

        # Store trial values
        trial_param_a = experiment.parameters['PARAM_A']
        trial_param_b = experiment.parameters['PARAM_B']

        # Verify parameter values are within expected ranges
        # (Don't use assertNotEqual because trial might randomly suggest the default value)
        self.assertGreaterEqual(trial_param_a, 0.0)
        self.assertLessEqual(trial_param_a, 10.0)
        self.assertGreaterEqual(trial_param_b, 1)
        self.assertLessEqual(trial_param_b, 10)

        # Verify parameters were updated in the experiment
        self.assertIn('PARAM_A', experiment.parameters)
        self.assertIn('PARAM_B', experiment.parameters)

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


@unittest.skipIf(not OPTUNA_AVAILABLE, "Optuna not available")
class TestOptunaMultiRunFeature(unittest.TestCase):
    """Test cases for the multi-run repetition feature."""

    def setUp(self):
        """Set up test fixtures."""
        Config().reset_state()
        self.config = Config()
        self.plugin = OptunaPlugin(self.config)
        self.plugin.register()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def test_repetition_state_initialization(self):
        """Test that repetition state is correctly initialized."""
        self.assertEqual(self.plugin.total_repetitions, 1)
        self.assertEqual(self.plugin.current_repetition_index, 0)
        self.assertEqual(self.plugin.collected_objectives, [])
        self.assertIsNone(self.plugin.trial_parameters)

    def test_prepare_trial_repetitions(self):
        """Test prepare_trial_repetitions method."""
        self.plugin.prepare_trial_repetitions(5)
        self.assertEqual(self.plugin.total_repetitions, 5)
        self.assertEqual(self.plugin.current_repetition_index, 0)
        self.assertEqual(self.plugin.collected_objectives, [])
        self.assertIsNone(self.plugin.trial_parameters)

    def test_is_first_repetition(self):
        """Test is_first_repetition method."""
        self.plugin.prepare_trial_repetitions(3)
        self.assertTrue(self.plugin.is_first_repetition())
        self.plugin.current_repetition_index = 1
        self.assertFalse(self.plugin.is_first_repetition())

    def test_is_last_repetition(self):
        """Test is_last_repetition method."""
        self.plugin.prepare_trial_repetitions(3)
        self.assertFalse(self.plugin.is_last_repetition())
        self.plugin.current_repetition_index = 2
        self.assertTrue(self.plugin.is_last_repetition())

    def test_advance_repetition(self):
        """Test advance_repetition method."""
        self.plugin.prepare_trial_repetitions(3)
        self.assertEqual(self.plugin.current_repetition_index, 0)
        self.plugin.advance_repetition()
        self.assertEqual(self.plugin.current_repetition_index, 1)
        self.plugin.advance_repetition()
        self.assertEqual(self.plugin.current_repetition_index, 2)

    def test_parameter_caching_across_repetitions(self):
        """Test that parameters are cached on first repetition and reused on subsequent ones."""
        # Create mock experiment for first repetition
        experiment = Mock(spec=Experiment)
        experiment.base_path = self.test_dir
        experiment.parameters = {
            '__OPTUNA__': True,
            '__OPTUNA_REPETITIONS__': 3,
            'PARAM_A': 1.0,
        }
        experiment.metadata = {'name': 'test_multi_run'}
        experiment.logger = Mock()
        experiment.hook_map = {
            '__optuna_parameters__': Mock(),
            '__optuna_objective__': Mock()
        }

        # Mock the apply_hook method for parameter suggestions
        def mock_apply_hook(hook_name, **kwargs):
            if hook_name == '__optuna_parameters__':
                return {'PARAM_A': 5.5}
            elif hook_name == '__optuna_sampler__':
                return None
            elif hook_name == '__optuna_direction__':
                return 'maximize'
            return None

        experiment.apply_hook = Mock(side_effect=mock_apply_hook)

        # Prepare for 3 repetitions
        self.plugin.prepare_trial_repetitions(3)

        # === FIRST REPETITION ===
        self.plugin.before_experiment_initialize(self.config, experiment)

        # Verify trial was created and parameters cached
        self.assertIsNotNone(self.plugin.current_trial)
        self.assertIsNotNone(self.plugin.trial_parameters)
        self.assertEqual(self.plugin.trial_parameters, {'PARAM_A': 5.5})
        self.assertEqual(experiment.parameters['PARAM_A'], 5.5)

        # === SECOND REPETITION ===
        self.plugin.advance_repetition()
        experiment.parameters['PARAM_A'] = 1.0  # Reset to default

        self.plugin.before_experiment_initialize(self.config, experiment)

        # Verify cached parameters were reused (no new trial created)
        self.assertEqual(experiment.parameters['PARAM_A'], 5.5)
        # Only one call to __optuna_parameters__ hook (from first repetition)
        self.assertEqual(experiment.apply_hook.call_count, 3)  # sampler, direction, parameters

    def test_objective_collection_across_repetitions(self):
        """Test that objectives are collected across all repetitions."""
        # Create mock experiment
        experiment = Mock(spec=Experiment)
        experiment.metadata = {'__optuna__': True}
        experiment.logger = Mock()

        # Setup plugin with study and trial
        self.plugin.current_study = Mock()
        self.plugin.current_trial = Mock()
        self.plugin.current_trial.number = 0
        self.plugin.current_study.trials = []
        self.plugin.prepare_trial_repetitions(3)

        # Mock the apply_hook to return different objectives
        objectives = [0.8, 0.85, 0.82]
        call_count = [0]

        def mock_objective_hook(hook_name):
            if hook_name == '__optuna_objective__':
                result = objectives[call_count[0]]
                call_count[0] += 1
                return result
            return None

        experiment.apply_hook = Mock(side_effect=mock_objective_hook)

        # === REPETITION 1 ===
        self.plugin.after_experiment_finalize(self.config, experiment)
        self.assertEqual(len(self.plugin.collected_objectives), 1)
        self.assertEqual(self.plugin.collected_objectives[0], 0.8)

        # === REPETITION 2 ===
        self.plugin.advance_repetition()
        self.plugin.after_experiment_finalize(self.config, experiment)
        self.assertEqual(len(self.plugin.collected_objectives), 2)
        self.assertEqual(self.plugin.collected_objectives[1], 0.85)

        # === REPETITION 3 (LAST) ===
        self.plugin.advance_repetition()
        self.plugin.after_experiment_finalize(self.config, experiment)
        self.assertEqual(len(self.plugin.collected_objectives), 3)
        self.assertEqual(self.plugin.collected_objectives[2], 0.82)

        # Verify averaged objective was reported to study
        expected_avg = (0.8 + 0.85 + 0.82) / 3
        self.plugin.current_study.tell.assert_called_once()
        call_args = self.plugin.current_study.tell.call_args
        self.assertEqual(call_args[0][0], self.plugin.current_trial)
        self.assertAlmostEqual(call_args[0][1], expected_avg, places=5)

    def test_single_repetition_behaves_normally(self):
        """Test that single repetition (default) behaves like original implementation."""
        # Create mock experiment
        experiment = Mock(spec=Experiment)
        experiment.base_path = self.test_dir
        experiment.parameters = {
            '__OPTUNA__': True,
            '__OPTUNA_REPETITIONS__': 1,
            'PARAM_A': 1.0,
        }
        experiment.metadata = {'name': 'test_single_run', '__optuna__': True}
        experiment.logger = Mock()
        experiment.hook_map = {
            '__optuna_parameters__': Mock(),
            '__optuna_objective__': Mock()
        }

        # Mock hooks
        def mock_apply_hook(hook_name, **kwargs):
            if hook_name == '__optuna_parameters__':
                return {'PARAM_A': 5.5}
            elif hook_name == '__optuna_sampler__':
                return None
            elif hook_name == '__optuna_direction__':
                return 'maximize'
            elif hook_name == '__optuna_objective__':
                return 0.9
            return None

        experiment.apply_hook = Mock(side_effect=mock_apply_hook)

        # Prepare for 1 repetition (default)
        self.plugin.prepare_trial_repetitions(1)

        # Test initialization
        self.plugin.before_experiment_initialize(self.config, experiment)
        self.assertTrue(self.plugin.is_first_repetition())
        self.assertTrue(self.plugin.is_last_repetition())

        # Setup study mock
        self.plugin.current_study = Mock()
        self.plugin.current_study.trials = []

        # Test finalization
        self.plugin.after_experiment_finalize(self.config, experiment)

        # Verify objective was reported (not averaged, just the single value)
        self.plugin.current_study.tell.assert_called_once()
        call_args = self.plugin.current_study.tell.call_args
        self.assertEqual(call_args[0][1], 0.9)


if __name__ == '__main__':
    unittest.main()
