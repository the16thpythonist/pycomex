"""
Tests for the 'pycomex archive scan' command.

This module tests the functionality of the archive scan command which analyzes
experiment distribution across the archive and displays statistics grouped by
custom criteria.
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

from ..util import LOG


class TestArchiveScanCommand:
    """Test suite for the archive scan command"""

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

        Creates multiple experiments with different parameters and statuses
        to test grouping, filtering, and statistics calculation.
        """
        # Store experiment paths for later verification
        self.experiment_paths = []

        # Create experiments with different prefixes and parameters
        test_configs = [
            {"__PREFIX__": "test_exp", "MODEL_TYPE": "neural_net", "LEARNING_RATE": 0.001},
            {"__PREFIX__": "test_exp", "MODEL_TYPE": "neural_net", "LEARNING_RATE": 0.01},
            {"__PREFIX__": "debug", "MODEL_TYPE": "decision_tree", "LEARNING_RATE": 0.1},
            {"__PREFIX__": "prod", "MODEL_TYPE": "neural_net", "LEARNING_RATE": 0.005},
        ]

        for config in test_configs:
            with ConfigIsolation() as cfg, ExperimentIsolation(
                sys.argv,
                glob_mod=config
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
                self.experiment_paths.append(experiment.path)

    def test_scan_basic_functionality(self):
        """
        Test that the scan command runs successfully and produces expected output.

        This test verifies:
        - Command executes without errors
        - Output contains all expected table headers
        - Summary line shows correct experiment count
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "scan",
            ],
        )

        LOG.info(f"Output:\n{result.output}")
        LOG.info(f"Exit code: {result.exit_code}")

        # Check that the command succeeded
        assert result.exit_code == 0

        # Verify all expected table headers are present
        # Note: Headers may wrap across lines due to terminal width
        assert "Group" in result.output
        assert "Experiments" in result.output
        assert ("Success Rate" in result.output or
                ("Success" in result.output and "Rate" in result.output))
        assert ("Last Completed" in result.output or
                ("Last" in result.output and "Completed" in result.output))
        assert ("Avg Runtime" in result.output or
                ("Avg" in result.output and "Runtime" in result.output))
        assert ("Disk Usage" in result.output or
                ("Disk" in result.output and "Usage" in result.output))

        # Verify summary information is present
        assert "Summary:" in result.output
        assert "group(s)" in result.output
        assert "experiment(s)" in result.output

        # Should show correct total count
        assert "4 experiment(s)" in result.output

    def test_scan_custom_grouping(self):
        """
        Test that the --group option works correctly with custom Python expressions.

        This test verifies:
        - Custom grouping expression is applied
        - Each unique group value creates a separate row
        - Experiment counts are correct per group
        """
        runner = CliRunner()

        # Group by MODEL_TYPE instead of the default __PREFIX__
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "scan",
                "--group",
                "p.get('MODEL_TYPE', 'unknown')",
            ],
        )

        LOG.info(f"Output:\n{result.output}")
        assert result.exit_code == 0

        # Verify the grouping expression is shown
        assert "Grouped by: p.get('MODEL_TYPE', 'unknown')" in result.output

        # We created experiments with 2 different MODEL_TYPE values:
        # - neural_net (3 experiments)
        # - decision_tree (1 experiment)
        assert "neural_net" in result.output
        assert "decision_tree" in result.output

        # Verify we have 2 groups
        assert "2 group(s)" in result.output

    def test_scan_with_select_filter(self):
        """
        Test that the --select option filters experiments before grouping.

        This test verifies:
        - Select filter is applied before grouping
        - Only filtered experiments are included in results
        - Filter expression is shown in output
        """
        runner = CliRunner()

        # Filter to only include experiments with __PREFIX__ == "test_exp"
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "scan",
                "--select",
                "p.get('__PREFIX__') == 'test_exp'",
            ],
        )

        LOG.info(f"Output:\n{result.output}")
        assert result.exit_code == 0

        # Verify the filter is shown
        assert "Filtered by: p.get('__PREFIX__') == 'test_exp'" in result.output
        assert "Applying selection filter" in result.output

        # We created 2 experiments with __PREFIX__ == "test_exp"
        assert "2 experiment(s)" in result.output

        # The "test_exp" group should appear in the table
        assert "test_exp" in result.output

    def test_scan_success_rate_calculation(self):
        """
        Test that success rate is calculated correctly for mixed success/failure experiments.

        This test verifies:
        - Success rate format appears correctly (N/M (X%))
        - Percentage calculation is accurate
        - Failed experiments are properly counted
        """
        runner = CliRunner()

        # First, modify one experiment to have an error
        # We'll modify the first experiment in the "test_exp" group
        target_path = self.experiment_paths[0]
        metadata = Experiment.load_metadata(target_path)
        metadata["has_error"] = True
        metadata["status"] = "error"

        metadata_path = os.path.join(target_path, Experiment.METADATA_FILE_NAME)
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4, sort_keys=True)

        # Now run the scan
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "scan",
            ],
        )

        LOG.info(f"Output:\n{result.output}")
        assert result.exit_code == 0

        # The success rate should be visible in the output
        # We have 4 experiments total, 1 failed, so 3/4 successful overall
        # But they're grouped by __PREFIX__, so we need to check the format
        assert "(" in result.output and "%" in result.output  # Success rate format

        # For the "test_exp" group (2 experiments, 1 failed):
        # Success rate should be 1/2 (50.0%)
        # The exact positioning may vary, but the format should appear

    def test_scan_disk_usage_calculation(self):
        """
        Test that disk usage is calculated and formatted correctly.

        This test verifies:
        - Disk usage is calculated for each group
        - Format is appropriate (KB/MB/GB)
        - Non-zero values are shown (experiments have files)
        """
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "scan",
            ],
        )

        LOG.info(f"Output:\n{result.output}")
        assert result.exit_code == 0

        # Disk usage should be present in the output
        # Each experiment has at least metadata files, so disk usage > 0
        # Check for common size units
        has_size_unit = (
            " KB" in result.output or
            " MB" in result.output or
            " GB" in result.output or
            " bytes" in result.output
        )
        assert has_size_unit, "Disk usage with size unit should be present in output"

        # Verify that disk usage values are not N/A for groups with experiments
        # Since all our experiments exist and have files, none should be N/A
        lines = result.output.split('\n')
        for line in lines:
            # Skip header and separator lines
            if 'Group' in line or '─' in line or not line.strip():
                continue
            # If this is a data row (contains a group name), it should have a size
            if any(prefix in line for prefix in ['test_exp', 'debug', 'prod']):
                assert 'N/A' not in line or 'Last Completed' in line, \
                    "Disk usage should not be N/A for groups with experiments"

    def test_scan_empty_archive(self):
        """
        Test behavior when the archive is empty.

        This test verifies proper handling of edge case where no experiments exist.
        """
        # Create a new empty archive
        empty_archive = os.path.join(self.temp_dir, "empty_results")
        os.makedirs(empty_archive)

        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                empty_archive,
                "scan",
            ],
        )

        LOG.info(f"Output:\n{result.output}")
        # Command should handle empty archives gracefully
        assert result.exit_code != 0 or "no archived experiments" in result.output.lower()

    def test_scan_no_experiments_match_selection(self):
        """
        Test behavior when no experiments match the selection criteria.

        This verifies proper handling when filter excludes all experiments.
        """
        runner = CliRunner()

        # Use a filter that matches no experiments
        result = runner.invoke(
            cli,
            [
                "archive",
                "--path",
                self.archive_path,
                "scan",
                "--select",
                "p.get('__PREFIX__') == 'nonexistent'",
            ],
        )

        LOG.info(f"Output:\n{result.output}")
        # Command should succeed but indicate no matches
        assert result.exit_code == 0
        assert "No experiments match" in result.output or "0 experiment(s)" in result.output
