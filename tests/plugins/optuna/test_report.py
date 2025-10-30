"""
Unit tests for Optuna plugin report generation.

Tests the OptunaReportGenerator class and its visualization capabilities.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pycomex.config import Config

# Try to import optuna and plugin
try:
    import optuna
    from pycomex.plugins.optuna import OptunaPlugin, StudyManager, OptunaReportGenerator
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    OptunaPlugin = None
    StudyManager = None
    OptunaReportGenerator = None


@unittest.skipIf(not OPTUNA_AVAILABLE, "Optuna not available")
class TestOptunaReportGenerator(unittest.TestCase):
    """Test cases for the OptunaReportGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        Config().reset_state()
        self.test_dir = tempfile.mkdtemp()
        self.study_manager = StudyManager(self.test_dir)
        self.report_generator = OptunaReportGenerator(self.study_manager)

        # Create artifacts directory for test outputs
        self.artifacts_dir = Path(__file__).parent / "artifacts" / "optuna_reports"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def create_mock_study_with_trials(self, study_name: str, n_trials: int = 10):
        """
        Helper to create a study with trials for testing.

        :param study_name: Name of the study to create
        :param n_trials: Number of trials to add
        :return: Created Optuna study
        """
        study = self.study_manager.get_or_create_study(study_name, direction="maximize")

        for i in range(n_trials):
            trial = study.ask()

            # Simulate a simple optimization problem
            param_a = trial.suggest_float('param_a', 0.0, 10.0)
            param_b = trial.suggest_int('param_b', 1, 100)
            param_c = trial.suggest_categorical('param_c', ['option1', 'option2', 'option3'])

            # Simple objective: maximize negative quadratic distance from optimal point
            optimal_a = 5.0
            optimal_b = 50
            objective = -(param_a - optimal_a)**2 - (param_b - optimal_b)**2

            # Add some noise based on categorical
            if param_c == 'option1':
                objective += 10
            elif param_c == 'option2':
                objective += 5

            study.tell(trial, objective)

        return study

    def test_init_report_generator(self):
        """Test initialization of OptunaReportGenerator."""
        self.assertIsNotNone(self.report_generator)
        self.assertEqual(self.report_generator.study_manager, self.study_manager)

    def test_generate_report_basic(self):
        """Test basic report generation with a mock study."""
        # Create a study with trials
        study_name = "test_basic_report"
        self.create_mock_study_with_trials(study_name, n_trials=10)

        # Generate report directly to artifacts directory
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Verify report directory was created
        self.assertTrue(report_path.exists())
        self.assertTrue(report_path.is_dir())

        # Verify HTML file exists
        html_file = report_path / "index.html"
        self.assertTrue(html_file.exists())

        # Verify plots directory exists
        plots_dir = report_path / "plots"
        self.assertTrue(plots_dir.exists())

        # Verify at least some plots were created
        plot_files = list(plots_dir.glob("*.png"))
        self.assertGreater(len(plot_files), 0, "No plot files were generated")

    def test_generate_report_custom_output_dir(self):
        """Test report generation with custom output directory."""
        # Create a study
        study_name = "test_custom_output"
        self.create_mock_study_with_trials(study_name, n_trials=5)

        # Generate report with custom output
        custom_output = os.path.join(self.test_dir, "custom_report_folder")
        report_path = self.report_generator.generate_report(study_name, output_dir=custom_output)

        # Verify custom path was used
        self.assertEqual(str(report_path), custom_output)
        self.assertTrue(report_path.exists())
        self.assertTrue((report_path / "index.html").exists())

    def test_generate_report_nonexistent_study(self):
        """Test error handling for nonexistent study."""
        with self.assertRaises(ValueError) as context:
            self.report_generator.generate_report("nonexistent_study")

        self.assertIn("not found", str(context.exception).lower())

    def test_generate_report_empty_study(self):
        """Test error handling for study with no trials."""
        # Create empty study
        study_name = "empty_study"
        self.study_manager.get_or_create_study(study_name)

        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.report_generator.generate_report(study_name)

        self.assertIn("no trials", str(context.exception).lower())

    def test_generate_report_single_trial(self):
        """Test report generation with only one trial."""
        # Create study with single trial
        study_name = "single_trial_study"
        self.create_mock_study_with_trials(study_name, n_trials=1)

        # Should still generate report (though some plots may be missing)
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        self.assertTrue(report_path.exists())
        self.assertTrue((report_path / "index.html").exists())

    def test_generate_report_many_trials(self):
        """Test report generation with many trials."""
        # Create study with many trials
        study_name = "many_trials_study"
        self.create_mock_study_with_trials(study_name, n_trials=50)

        # Generate report directly to artifacts directory
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        self.assertTrue(report_path.exists())
        self.assertTrue((report_path / "index.html").exists())

    def test_html_structure(self):
        """Test that generated HTML contains expected sections."""
        # Create a study
        study_name = "test_html_structure"
        self.create_mock_study_with_trials(study_name, n_trials=10)

        # Generate report to artifacts directory
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Read HTML content
        html_file = report_path / "index.html"
        html_content = html_file.read_text()

        # Verify key sections are present
        self.assertIn("<title>Optuna Study Report", html_content)
        self.assertIn("Study Summary", html_content)
        self.assertIn("Best Trial Results", html_content)
        self.assertIn("Visualizations", html_content)
        self.assertIn("All Trials", html_content)
        self.assertIn("Generated by PyComex", html_content)

        # Verify study name is in the report
        self.assertIn(study_name, html_content)

        # Verify parameter names are in the report
        self.assertIn("param_a", html_content)
        self.assertIn("param_b", html_content)
        self.assertIn("param_c", html_content)

    def test_plot_files_created(self):
        """Test that expected plot files are created."""
        # Create a study
        study_name = "test_plot_files"
        self.create_mock_study_with_trials(study_name, n_trials=15)

        # Generate report to artifacts directory
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        plots_dir = report_path / "plots"

        # Expected plots (some may not generate depending on data/dependencies)
        expected_plots = [
            "optimization_history.png",
            "parallel_coordinate.png",
            "slice.png",
            "edf.png",
            "timeline.png",
            "param_correlation.png",
            "param_distributions.png",
            "trial_states.png",
        ]

        # Check that at least some expected plots exist
        found_plots = []
        for plot_name in expected_plots:
            plot_path = plots_dir / plot_name
            if plot_path.exists():
                found_plots.append(plot_name)
                # Verify it's a valid file with content
                self.assertGreater(plot_path.stat().st_size, 0, f"{plot_name} is empty")

        # Should have at least a few plots
        self.assertGreaterEqual(len(found_plots), 3,
                                f"Expected at least 3 plots, found {len(found_plots)}: {found_plots}")

    def test_best_trial_highlighted_in_report(self):
        """Test that the best trial is properly highlighted in the report."""
        # Create a study
        study_name = "test_best_trial"
        study = self.create_mock_study_with_trials(study_name, n_trials=10)

        # Generate report to artifacts directory
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Read HTML content
        html_file = report_path / "index.html"
        html_content = html_file.read_text()

        # Verify best trial info is present
        best_trial = study.best_trial
        self.assertIn(f"Objective Value: {study.best_value:.6f}", html_content)

        # Verify best parameters are shown
        for param_name, param_value in study.best_params.items():
            self.assertIn(param_name, html_content)

    def test_report_handles_failed_plots_gracefully(self):
        """Test that report generation continues even if some plots fail."""
        # Create a study with minimal trials (some plots may fail)
        study_name = "test_graceful_failure"
        self.create_mock_study_with_trials(study_name, n_trials=2)

        # Should still complete without raising exceptions
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Report should still be generated
        self.assertTrue(report_path.exists())
        self.assertTrue((report_path / "index.html").exists())

    def test_multiple_studies_different_names(self):
        """Test generating reports for multiple different studies."""
        # Create multiple studies
        study_names = ["study_1", "study_2", "study_3"]

        for study_name in study_names:
            self.create_mock_study_with_trials(study_name, n_trials=8)
            output_dir = str(self.artifacts_dir / study_name)
            report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

            # Verify each has its own report
            self.assertTrue(report_path.exists())
            self.assertEqual(report_path.name, study_name)

    def test_report_with_different_parameter_types(self):
        """Test report handles different parameter types correctly."""
        study_name = "test_param_types"
        study = self.study_manager.get_or_create_study(study_name)

        # Add trials with various parameter types
        for i in range(10):
            trial = study.ask()

            # Different parameter types
            float_param = trial.suggest_float('float_param', 0.0, 1.0)
            int_param = trial.suggest_int('int_param', 1, 100)
            categorical_param = trial.suggest_categorical('cat_param', ['a', 'b', 'c'])
            log_param = trial.suggest_float('log_param', 1e-5, 1e-1, log=True)

            objective = float_param + int_param * 0.01
            study.tell(trial, objective)

        # Generate report to artifacts directory
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Read HTML and verify all parameter types are represented
        html_content = (report_path / "index.html").read_text()

        self.assertIn("float_param", html_content)
        self.assertIn("int_param", html_content)
        self.assertIn("cat_param", html_content)
        self.assertIn("log_param", html_content)

    def test_param_correlation_plot(self):
        """Test that parameter correlation heatmap is generated."""
        study_name = "test_param_correlation"
        self.create_mock_study_with_trials(study_name, n_trials=20)

        # Generate report
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Check that correlation plot exists
        correlation_plot = report_path / "plots" / "param_correlation.png"
        self.assertTrue(correlation_plot.exists(), "Correlation heatmap was not generated")
        self.assertGreater(correlation_plot.stat().st_size, 0, "Correlation plot is empty")

        # Verify HTML mentions correlation
        html_content = (report_path / "index.html").read_text()
        self.assertIn("Correlation", html_content)

    def test_param_distributions_plot(self):
        """Test that parameter distribution histograms are generated."""
        study_name = "test_param_distributions"
        self.create_mock_study_with_trials(study_name, n_trials=25)

        # Generate report
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Check that distributions plot exists
        distributions_plot = report_path / "plots" / "param_distributions.png"
        self.assertTrue(distributions_plot.exists(), "Parameter distributions were not generated")
        self.assertGreater(distributions_plot.stat().st_size, 0, "Distributions plot is empty")

        # Verify HTML mentions distributions
        html_content = (report_path / "index.html").read_text()
        self.assertIn("Distribution", html_content)

    def test_trial_states_plot(self):
        """Test that trial state distribution chart is generated."""
        study_name = "test_trial_states"
        study = self.study_manager.get_or_create_study(study_name)

        # Add trials with mixed states
        for i in range(15):
            trial = study.ask()
            param = trial.suggest_float('param', 0.0, 10.0)

            if i % 5 == 0:
                # Some failed trials
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
            elif i % 7 == 0:
                # Some pruned trials
                study.tell(trial, state=optuna.trial.TrialState.PRUNED)
            else:
                # Most successful
                study.tell(trial, param)

        # Generate report
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Check that trial states plot exists
        states_plot = report_path / "plots" / "trial_states.png"
        self.assertTrue(states_plot.exists(), "Trial states plot was not generated")
        self.assertGreater(states_plot.stat().st_size, 0, "Trial states plot is empty")

        # Verify HTML shows trial states
        html_content = (report_path / "index.html").read_text()
        self.assertIn("Trial State", html_content)
        self.assertIn("COMPLETE", html_content)


@unittest.skipIf(not OPTUNA_AVAILABLE, "Optuna not available")
class TestOptunaReportGeneratorEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions for report generation."""

    def setUp(self):
        """Set up test fixtures."""
        Config().reset_state()
        self.test_dir = tempfile.mkdtemp()
        self.study_manager = StudyManager(self.test_dir)
        self.report_generator = OptunaReportGenerator(self.study_manager)

        # Create artifacts directory for test outputs
        self.artifacts_dir = Path(__file__).parent / "artifacts" / "optuna_reports"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config().reset_state()

    def test_report_with_failed_trials(self):
        """Test report generation with some failed trials."""
        study_name = "test_failed_trials"
        study = self.study_manager.get_or_create_study(study_name)

        # Add some successful and some failed trials
        for i in range(10):
            trial = study.ask()
            param = trial.suggest_float('param', 0.0, 10.0)

            if i % 3 == 0:
                # Mark trial as failed
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
            else:
                # Successful trial
                study.tell(trial, param)

        # Should still generate report
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        self.assertTrue(report_path.exists())
        self.assertTrue((report_path / "index.html").exists())

        # Verify HTML mentions failed trials
        html_content = (report_path / "index.html").read_text()
        self.assertIn("FAIL", html_content)

    def test_report_with_pruned_trials(self):
        """Test report generation with pruned trials."""
        study_name = "test_pruned_trials"
        study = self.study_manager.get_or_create_study(study_name)

        # Add trials with pruning
        for i in range(10):
            trial = study.ask()
            param = trial.suggest_float('param', 0.0, 10.0)

            if i % 4 == 0:
                # Prune trial
                study.tell(trial, state=optuna.trial.TrialState.PRUNED)
            else:
                study.tell(trial, param)

        # Should still generate report
        output_dir = str(self.artifacts_dir / study_name)
        report_path = self.report_generator.generate_report(study_name, output_dir=output_dir)

        self.assertTrue(report_path.exists())
        html_content = (report_path / "index.html").read_text()
        self.assertIn("PRUNED", html_content)

    def test_report_output_directory_exists(self):
        """Test that existing output directory is handled correctly."""
        study_name = "test_existing_dir"
        study = self.study_manager.get_or_create_study(study_name)

        # Add trials
        for i in range(5):
            trial = study.ask()
            param = trial.suggest_float('param', 0.0, 10.0)
            study.tell(trial, param)

        # Generate report first time
        output_dir = os.path.join(self.test_dir, "existing_report")
        report_path1 = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Generate again to same location (should overwrite)
        report_path2 = self.report_generator.generate_report(study_name, output_dir=output_dir)

        # Should complete successfully
        self.assertEqual(report_path1, report_path2)
        self.assertTrue(report_path2.exists())


if __name__ == '__main__':
    unittest.main()
