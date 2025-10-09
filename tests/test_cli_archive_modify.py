"""
Tests for the 'pycomex archive modify' command.

This module tests the functionality of the archive modify command which allows users
to modify parameters and metadata of archived experiments in bulk.
"""

import json
import os
import shutil
import sys
import tempfile

from click.testing import CliRunner

from pycomex.cli import cli
from pycomex.functional.experiment import Experiment
from pycomex.testing import ConfigIsolation, ExperimentIsolation

from .util import LOG


class TestArchiveModifyCommand:
    """Test suite for the archive modify command"""

    def setup_method(self):
        """
        Set up test environment with temporary archive directory and sample experiments.
        """
        # Create a temporary directory for the archive
        self.temp_dir = tempfile.mkdtemp()
        self.archive_path = os.path.join(self.temp_dir, "results")
        os.makedirs(self.archive_path)

        # Create sample experiments for testing
        self._create_sample_experiments()

    def teardown_method(self):
        """Clean up temporary test directory"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_sample_experiments(self):
        """
        Create sample experiment archives for testing.

        Creates two experiments with different parameter values that can be used
        for testing selection and modification.
        """
        # Create two sample experiments with different parameters
        for i, learning_rate in enumerate([0.001, 0.01]):
            with ConfigIsolation() as config, ExperimentIsolation(
                sys.argv,
                glob_mod={
                    "LEARNING_RATE": learning_rate,
                    "BATCH_SIZE": 32,
                    "EPOCHS": 10,
                }
            ) as iso:
                experiment = Experiment(
                    base_path=self.archive_path,
                    namespace="test_experiments",
                    glob=iso.glob,
                )

                @experiment
                def run(e):
                    e["result"] = 42
                    e.log("Test experiment")

                # Run the experiment to create the archive
                experiment.run()

                # Store the path for later use
                if not hasattr(self, "experiment_paths"):
                    self.experiment_paths = []
                self.experiment_paths.append(experiment.path)

    def test_modify_parameters_with_select(self):
        """
        Test modifying parameters of selected experiments based on a selection criterion.
        """
        runner = CliRunner()

        # Modify the LEARNING_RATE for experiments where it's less than 0.01
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--select",
                "p['LEARNING_RATE'] < 0.01",
                "--modify-parameters",
                "p['LEARNING_RATE'] *= 10",
            ],
        )

        LOG.info(f"Output: {result.output}")
        LOG.info(f"Exit code: {result.exit_code}")

        # Check that the command succeeded
        assert result.exit_code == 0
        assert "Successfully modified" in result.output

        # Verify that only the selected experiment was modified
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            learning_rate = metadata["parameters"]["LEARNING_RATE"]["value"]

            # The experiment with original LR=0.001 should now be 0.01
            # The experiment with original LR=0.01 should remain unchanged
            if learning_rate == 0.01:
                # This could be either the modified one or the unchanged one
                # We need to check more carefully
                pass

        # More precise verification: reload and check
        modified_count = 0
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            lr = metadata["parameters"]["LEARNING_RATE"]["value"]
            if lr == 0.01:
                modified_count += 1

        # Both experiments should now have LR=0.01 (one was already 0.01, one was modified from 0.001)
        assert modified_count == 2

    def test_modify_all_experiments(self):
        """
        Test modifying all experiments using the --all flag.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['BATCH_SIZE'] = 64",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0
        assert "Successfully modified" in result.output

        # Verify all experiments were modified
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            batch_size = metadata["parameters"]["BATCH_SIZE"]["value"]
            assert batch_size == 64

    def test_modify_metadata(self):
        """
        Test modifying metadata fields of experiments.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-metadata",
                "m['custom_tag'] = 'processed'",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0

        # Verify metadata was modified
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            assert "custom_tag" in metadata
            assert metadata["custom_tag"] == "processed"

    def test_modify_both_parameters_and_metadata(self):
        """
        Test modifying both parameters and metadata in a single command.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['EPOCHS'] = 20",
                "--modify-metadata",
                "m['processed'] = True",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0

        # Verify both were modified
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            assert metadata["parameters"]["EPOCHS"]["value"] == 20
            assert metadata["processed"] is True

    def test_dry_run_mode(self):
        """
        Test that dry-run mode previews changes without actually modifying files.
        """
        runner = CliRunner()

        # Get original values
        original_values = []
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            original_values.append(metadata["parameters"]["BATCH_SIZE"]["value"])

        # Run in dry-run mode
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['BATCH_SIZE'] = 128",
                "--dry-run",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

        # Verify values were NOT actually modified
        for i, exp_path in enumerate(self.experiment_paths):
            metadata = Experiment.load_metadata(exp_path)
            assert metadata["parameters"]["BATCH_SIZE"]["value"] == original_values[i]

    def test_verbose_output(self):
        """
        Test that verbose mode shows detailed progress information.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['BATCH_SIZE'] = 256",
                "--verbose",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0
        assert "BATCH_SIZE" in result.output
        # Should show the change: 32 → 256
        assert "→" in result.output or "->" in result.output

    def test_error_handling_invalid_syntax(self):
        """
        Test that invalid Python syntax in modification code is detected.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['BATCH_SIZE'] = ",  # Invalid syntax
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code != 0
        assert "Syntax error" in result.output

    def test_error_without_modification_option(self):
        """
        Test that the command fails when neither --modify-parameters nor --modify-metadata is provided.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code != 0
        assert "at least one of" in result.output.lower()

    def test_error_without_selection_option(self):
        """
        Test that the command fails when neither --select nor --all is provided.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--modify-parameters",
                "p['BATCH_SIZE'] = 64",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code != 0
        assert "select" in result.output.lower() or "all" in result.output.lower()

    def test_no_experiments_match_selection(self):
        """
        Test behavior when no experiments match the selection criteria.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--select",
                "p['LEARNING_RATE'] > 1.0",  # No experiment has LR > 1.0
                "--modify-parameters",
                "p['BATCH_SIZE'] = 64",
            ],
        )

        LOG.info(f"Output: {result.output}")
        # Command should succeed but indicate no matches
        assert result.exit_code == 0
        assert "No experiments match" in result.output

    def test_complex_parameter_modification(self):
        """
        Test more complex parameter modifications using multiple operations.
        """
        runner = CliRunner()

        # Use newline-separated statements for complex modifications
        modification_code = "p['BATCH_SIZE'] = p['BATCH_SIZE'] * 2; p['EPOCHS'] = p['EPOCHS'] + 5"

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                modification_code,
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0

        # Verify modifications
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            assert metadata["parameters"]["BATCH_SIZE"]["value"] == 64  # 32 * 2
            assert metadata["parameters"]["EPOCHS"]["value"] == 15  # 10 + 5

    def test_modification_persists_to_file(self):
        """
        Test that modifications are actually persisted to the metadata JSON file.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['BATCH_SIZE'] = 512",
            ],
        )

        assert result.exit_code == 0

        # Read the file directly to verify persistence
        for exp_path in self.experiment_paths:
            metadata_path = os.path.join(exp_path, Experiment.METADATA_FILE_NAME)
            with open(metadata_path) as f:
                metadata = json.load(f)

            assert metadata["parameters"]["BATCH_SIZE"]["value"] == 512

    def test_metadata_access_in_parameter_modification(self):
        """
        Test that metadata (m) can be accessed when modifying parameters.
        """
        runner = CliRunner()

        # First add a custom metadata field
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            metadata["multiplier"] = 4
            metadata_path = os.path.join(exp_path, Experiment.METADATA_FILE_NAME)
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=4)

        # Now use that metadata field to modify parameters
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['BATCH_SIZE'] = p['BATCH_SIZE'] * m['multiplier']",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0

        # Verify modifications
        for exp_path in self.experiment_paths:
            metadata = Experiment.load_metadata(exp_path)
            assert metadata["parameters"]["BATCH_SIZE"]["value"] == 128  # 32 * 4

    def test_verbose_shows_no_changes_when_modification_has_no_effect(self):
        """
        Test that verbose mode indicates when no actual changes occurred.
        """
        runner = CliRunner()

        # Modify to the same value (no actual change)
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "modify",
                "--all",
                "--modify-parameters",
                "p['BATCH_SIZE'] = p['BATCH_SIZE']",  # No change
                "--verbose",
            ],
        )

        LOG.info(f"Output: {result.output}")
        assert result.exit_code == 0
        assert "No parameter changes" in result.output or "no changes" in result.output.lower()
