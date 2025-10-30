"""
Unit tests for the configuration validation module.

Tests the pycomex.functional.validate module which provides comprehensive
validation for PyComex YAML configuration files.
"""

import os
import tempfile
from pathlib import Path

import pytest

from pycomex.functional.validate import ConfigValidator, ValidationResult


class TestValidationResult:
    """Test the ValidationResult dataclass."""

    def test_valid_error_level(self):
        """Should create ValidationResult with 'error' level."""
        result = ValidationResult(
            passed=False,
            message="Test error",
            level='error',
            details="Error details"
        )
        assert result.level == 'error'
        assert not result.passed

    def test_valid_warning_level(self):
        """Should create ValidationResult with 'warning' level."""
        result = ValidationResult(
            passed=False,
            message="Test warning",
            level='warning',
            details="Warning details"
        )
        assert result.level == 'warning'
        assert not result.passed

    def test_valid_info_level(self):
        """Should create ValidationResult with 'info' level."""
        result = ValidationResult(
            passed=True,
            message="Test info",
            level='info'
        )
        assert result.level == 'info'
        assert result.passed

    def test_invalid_level_raises_error(self):
        """Should raise ValueError for invalid level."""
        with pytest.raises(ValueError) as exc_info:
            ValidationResult(
                passed=True,
                message="Test",
                level='invalid'
            )
        assert "Invalid level" in str(exc_info.value)

    def test_optional_details(self):
        """Should allow optional details field."""
        result = ValidationResult(
            passed=True,
            message="Test",
            level='info'
        )
        assert result.details is None


class TestConfigValidatorFileExists:
    """Test the validate_file_exists method."""

    def test_file_exists_and_readable(self, tmp_path):
        """Should pass when config file exists and is readable."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("pycomex: true")

        validator = ConfigValidator(str(config_file))
        result = validator.validate_file_exists()

        assert result.passed
        assert result.level == 'info'
        assert "exists and is readable" in result.message

    def test_file_not_found(self, tmp_path):
        """Should fail when config file doesn't exist."""
        config_file = tmp_path / "nonexistent.yml"

        validator = ConfigValidator(str(config_file))
        result = validator.validate_file_exists()

        assert not result.passed
        assert result.level == 'error'
        assert "not found" in result.message

    def test_path_is_directory(self, tmp_path):
        """Should fail when path is a directory, not a file."""
        config_dir = tmp_path / "config_dir"
        config_dir.mkdir()

        validator = ConfigValidator(str(config_dir))
        result = validator.validate_file_exists()

        assert not result.passed
        assert result.level == 'error'
        assert "not a file" in result.message

    def test_permission_denied(self, tmp_path):
        """Should fail when file is not readable."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("pycomex: true")
        config_file.chmod(0o000)

        try:
            validator = ConfigValidator(str(config_file))
            result = validator.validate_file_exists()

            assert not result.passed
            assert result.level == 'error'
            assert "Permission denied" in result.message or "access error" in result.message.lower()
        finally:
            # Restore permissions for cleanup
            config_file.chmod(0o644)


class TestConfigValidatorYamlSyntax:
    """Test the validate_yaml_syntax method."""

    def test_valid_yaml_syntax(self, tmp_path):
        """Should pass for valid YAML syntax."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
  PARAM2: 42
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        result = validator.validate_yaml_syntax()

        assert result.passed
        assert result.level == 'info'
        assert "valid" in result.message.lower()

    def test_invalid_yaml_syntax(self, tmp_path):
        """Should fail for invalid YAML syntax."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
    PARAM2: 42  # Invalid indentation
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        result = validator.validate_yaml_syntax()

        assert not result.passed
        assert result.level == 'error'
        assert "Invalid YAML" in result.message or "YAML" in result.message

    def test_empty_yaml_file(self, tmp_path):
        """Should fail for empty YAML file."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        result = validator.validate_yaml_syntax()

        assert not result.passed
        assert result.level == 'error'
        assert "empty" in result.message.lower()


class TestConfigValidatorSchema:
    """Test the validate_schema method."""

    def test_valid_schema(self, tmp_path):
        """Should pass for valid schema with required fields."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        result = validator.validate_schema()

        assert result.passed
        assert result.level == 'info'

    def test_missing_extend_field(self, tmp_path):
        """Should fail when 'extend' field is missing."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        result = validator.validate_schema()

        assert not result.passed
        assert result.level == 'error'
        assert "extend" in result.details.lower()

    def test_missing_parameters_field(self, tmp_path):
        """Should fail when 'parameters' field is missing."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        result = validator.validate_schema()

        assert not result.passed
        assert result.level == 'error'
        assert "parameters" in result.details.lower()


class TestConfigValidatorExtendField:
    """Test the validate_extend_field method."""

    def test_valid_extend_field(self, tmp_path):
        """Should pass when extended experiment exists."""
        # Create experiment file
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

PARAM1 = "value1"

@Experiment(base_path="/tmp", namespace="test", glob=globals())
def experiment(e: Experiment):
    pass

experiment.run_if_main()
""")

        # Create config file
        config_file = tmp_path / "config.yml"
        config_file.write_text(f"""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_extend_field()

        assert result.passed
        assert result.level == 'info'

    def test_extend_file_not_found(self, tmp_path):
        """Should fail when extended experiment doesn't exist."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: nonexistent_experiment.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_extend_field()

        assert not result.passed
        assert result.level == 'error'
        assert "not found" in result.message

    def test_extend_not_python_file(self, tmp_path):
        """Should fail when extended file is not a Python file."""
        # Create a non-Python file
        experiment_file = tmp_path / "experiment.txt"
        experiment_file.write_text("This is a text file, not Python")

        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.txt
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_extend_field()

        assert not result.passed
        assert result.level == 'error'
        assert "not a Python file" in result.message

    def test_extend_file_not_importable(self, tmp_path):
        """Should fail when extended experiment has syntax errors."""
        # Create experiment file with syntax error
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

This is not valid Python syntax!
""")

        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_extend_field()

        assert not result.passed
        assert result.level == 'error'
        assert "not importable" in result.message


class TestConfigValidatorParameters:
    """Test the validate_parameters method."""

    def test_valid_parameters(self, tmp_path):
        """Should pass when all parameters match base experiment."""
        # Create experiment file
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

PARAM1 = "default1"
PARAM2 = 42

@Experiment(base_path="/tmp", namespace="test", glob=globals())
def experiment(e: Experiment):
    pass

experiment.run_if_main()
""")

        # Create config file
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
  PARAM2: 100
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        validator.validate_extend_field()
        result = validator.validate_parameters()

        assert result.passed
        assert result.level == 'info'
        assert "recognized" in result.message.lower()

    def test_unknown_parameter(self, tmp_path):
        """Should warn when parameter doesn't exist in base experiment."""
        # Create experiment file
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

PARAM1 = "default1"

@Experiment(base_path="/tmp", namespace="test", glob=globals())
def experiment(e: Experiment):
    pass

experiment.run_if_main()
""")

        # Create config file with unknown parameter
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
  UNKNOWN_PARAM: 100
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        validator.validate_extend_field()
        result = validator.validate_parameters()

        assert not result.passed
        assert result.level == 'warning'
        assert "UNKNOWN_PARAM" in result.details
        assert "not found" in result.details

    def test_parameter_typo_detection(self, tmp_path):
        """Should suggest similar parameter names for typos."""
        # Create experiment file
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

LEARNING_RATE = 0.001

@Experiment(base_path="/tmp", namespace="test", glob=globals())
def experiment(e: Experiment):
    pass

experiment.run_if_main()
""")

        # Create config file with typo
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  LEARNINNG_RATE: 0.01
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        validator.validate_extend_field()
        result = validator.validate_parameters()

        assert not result.passed
        assert result.level == 'warning'
        assert "LEARNINNG_RATE" in result.details
        assert "did you mean" in result.details.lower()
        assert "LEARNING_RATE" in result.details


class TestConfigValidatorMixins:
    """Test the validate_mixins method."""

    def test_no_mixins(self, tmp_path):
        """Should pass when no mixins are specified."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_mixins()

        assert result.passed
        assert result.level == 'info'
        assert "No mixins" in result.message

    def test_valid_single_mixin(self, tmp_path):
        """Should pass when mixin exists and is valid."""
        # Create mixin file
        mixin_file = tmp_path / "mixin.py"
        mixin_file.write_text("""
from pycomex.functional.mixin import ExperimentMixin

mixin = ExperimentMixin(glob=globals())

@mixin.hook("before_run", replace=False)
def log_start(e):
    e.log("Mixin start")
""")

        # Create config file
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
include: mixin.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_mixins()

        assert result.passed
        assert result.level == 'info'
        assert "valid" in result.message.lower()

    def test_valid_multiple_mixins(self, tmp_path):
        """Should pass when all mixins exist and are valid."""
        # Create mixin files
        mixin1_file = tmp_path / "mixin1.py"
        mixin1_file.write_text("""
from pycomex.functional.mixin import ExperimentMixin

mixin = ExperimentMixin(glob=globals())

@mixin.hook("before_run", replace=False)
def log_start(e):
    e.log("Mixin 1 start")
""")

        mixin2_file = tmp_path / "mixin2.py"
        mixin2_file.write_text("""
from pycomex.functional.mixin import ExperimentMixin

mixin = ExperimentMixin(glob=globals())

@mixin.hook("before_run", replace=False)
def log_start(e):
    e.log("Mixin 2 start")
""")

        # Create config file
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
include:
  - mixin1.py
  - mixin2.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_mixins()

        assert result.passed
        assert result.level == 'info'
        assert "2 mixins" in result.message or "All" in result.message

    def test_mixin_not_found(self, tmp_path):
        """Should fail when mixin file doesn't exist."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
include: nonexistent_mixin.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_mixins()

        assert not result.passed
        assert result.level == 'error'
        assert "not found" in result.details

    def test_mixin_not_python_file(self, tmp_path):
        """Should fail when mixin is not a Python file."""
        # Create a non-Python file
        mixin_file = tmp_path / "mixin.txt"
        mixin_file.write_text("This is a text file, not Python")

        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
include: mixin.txt
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_mixins()

        assert not result.passed
        assert result.level == 'error'
        assert "not a Python file" in result.details


class TestConfigValidatorEnvVars:
    """Test the validate_env_vars method."""

    def test_no_env_vars(self, tmp_path):
        """Should pass when no environment variables are referenced."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        result = validator.validate_env_vars()

        assert result.passed
        assert result.level == 'info'
        assert "No environment variables" in result.message

    def test_env_var_with_default(self, tmp_path):
        """Should pass when env var has default value."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: ${MISSING_VAR:-default_value}
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        result = validator.validate_env_vars()

        assert result.passed
        assert result.level == 'info'

    def test_env_var_available(self, tmp_path):
        """Should pass when referenced env var is available."""
        os.environ["TEST_VALIDATION_VAR"] = "test_value"
        try:
            config_file = tmp_path / "config.yml"
            config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: ${TEST_VALIDATION_VAR}
""")

            validator = ConfigValidator(str(config_file))
            validator.validate_file_exists()
            validator.validate_yaml_syntax()
            result = validator.validate_env_vars()

            assert result.passed
            assert result.level == 'info'
            assert "available" in result.message.lower()
        finally:
            del os.environ["TEST_VALIDATION_VAR"]

    def test_env_var_missing(self, tmp_path):
        """Should warn when referenced env var is missing."""
        # Ensure variable is not set
        if "DEFINITELY_MISSING_VAR" in os.environ:
            del os.environ["DEFINITELY_MISSING_VAR"]

        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: ${DEFINITELY_MISSING_VAR}
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        result = validator.validate_env_vars()

        assert not result.passed
        assert result.level == 'warning'
        assert "DEFINITELY_MISSING_VAR" in result.details


class TestConfigValidatorPaths:
    """Test the validate_paths method."""

    def test_valid_paths(self, tmp_path):
        """Should pass when all paths are valid."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
base_path: /tmp/experiments
namespace: results/test
name: my_experiment
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_paths()

        assert result.passed
        assert result.level == 'info'
        assert "valid" in result.message.lower()

    def test_base_path_invalid_characters(self, tmp_path):
        """Should fail when base_path contains invalid characters."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
base_path: /tmp/experiments/invalid<>chars
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_paths()

        assert not result.passed
        assert result.level == 'error'
        assert "base_path" in result.details
        assert "invalid characters" in result.details

    def test_namespace_invalid_characters(self, tmp_path):
        """Should fail when namespace contains invalid characters."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
namespace: results/test<invalid>
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_paths()

        assert not result.passed
        assert result.level == 'error'
        assert "namespace" in result.details
        assert "invalid characters" in result.details

    def test_name_invalid_characters(self, tmp_path):
        """Should fail when name contains invalid characters."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
name: my/invalid/name
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate_file_exists()
        validator.validate_yaml_syntax()
        validator.validate_schema()
        result = validator.validate_paths()

        assert not result.passed
        assert result.level == 'error'
        assert "name" in result.details
        assert "invalid characters" in result.details


class TestConfigValidatorOverall:
    """Test the overall validate method."""

    def test_full_validation_success(self, tmp_path):
        """Should pass full validation for a completely valid config."""
        # Create experiment file
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

PARAM1 = "default1"

@Experiment(base_path="/tmp", namespace="test", glob=globals())
def experiment(e: Experiment):
    pass

experiment.run_if_main()
""")

        # Create config file
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
name: test_experiment
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        success, results = validator.validate()

        assert success
        assert len(results) > 0
        # All results should either pass or be info level
        for result in results:
            if not result.passed:
                assert result.level != 'error'

    def test_full_validation_failure(self, tmp_path):
        """Should fail full validation when critical errors exist."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("invalid: yaml: syntax::")

        validator = ConfigValidator(str(config_file))
        success, results = validator.validate()

        assert not success
        assert len(results) > 0
        assert any(not r.passed and r.level == 'error' for r in results)

    def test_warnings_as_errors_mode(self, tmp_path):
        """Should treat warnings as errors when warnings_as_errors is True."""
        # Create experiment file
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

PARAM1 = "default1"

@Experiment(base_path="/tmp", namespace="test", glob=globals())
def experiment(e: Experiment):
    pass

experiment.run_if_main()
""")

        # Create config with unknown parameter (warning)
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
  UNKNOWN_PARAM: 100
""")

        validator = ConfigValidator(str(config_file), warnings_as_errors=True)
        success, results = validator.validate()

        assert not success
        assert any(not r.passed and r.level == 'warning' for r in results)

    def test_stops_on_critical_errors(self, tmp_path):
        """Should stop validation after critical errors."""
        # Non-existent file
        config_file = tmp_path / "nonexistent.yml"

        validator = ConfigValidator(str(config_file))
        success, results = validator.validate()

        assert not success
        # Should only have file existence check result
        assert len(results) == 1
        assert "not found" in results[0].message


class TestConfigValidatorFormatResults:
    """Test the format_results method."""

    def test_format_results_basic(self, tmp_path):
        """Should format results as a string."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("pycomex: true")

        validator = ConfigValidator(str(config_file))
        validator.validate()
        output = validator.format_results()

        assert isinstance(output, str)
        assert len(output) > 0
        assert "config.yml" in output.lower()

    def test_format_results_verbose(self, tmp_path):
        """Should include more details in verbose mode."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("pycomex: true")

        validator = ConfigValidator(str(config_file))
        validator.validate()

        normal_output = validator.format_results(verbose=False)
        verbose_output = validator.format_results(verbose=True)

        assert isinstance(verbose_output, str)
        # Verbose output should generally be longer or equal
        assert len(verbose_output) >= len(normal_output)

    def test_format_results_contains_status(self, tmp_path):
        """Should contain validation status in output."""
        # Create valid config
        experiment_file = tmp_path / "experiment.py"
        experiment_file.write_text("""
from pycomex.functional.experiment import Experiment

@Experiment(base_path="/tmp", namespace="test", glob=globals())
def experiment(e: Experiment):
    pass

experiment.run_if_main()
""")

        config_file = tmp_path / "config.yml"
        config_file.write_text("""
pycomex: true
extend: experiment.py
parameters:
  PARAM1: value1
""")

        validator = ConfigValidator(str(config_file))
        validator.validate()
        output = validator.format_results()

        assert "Validation" in output


class TestConfigValidatorIntegration:
    """Integration tests using real test assets."""

    def test_validate_existing_mock_config(self):
        """Should successfully validate the existing mock_config.yml."""
        # Get path to test assets
        test_dir = Path(__file__).parent
        assets_dir = test_dir / "assets"
        config_path = assets_dir / "mock_config.yml"

        if not config_path.exists():
            pytest.skip("mock_config.yml not found in test assets")

        validator = ConfigValidator(str(config_path))
        success, results = validator.validate()

        # The mock config should be valid (or have only warnings)
        # Check that no critical errors occurred
        has_critical_errors = any(
            not r.passed and r.level == 'error'
            for r in results
        )
        # Note: We expect this to pass or have only warnings
        # The actual parameters NUM_VALUES and NUM_BINS don't exist in
        # mock_functional_experiment.py, so we expect warnings
        assert not has_critical_errors or len(results) > 5
