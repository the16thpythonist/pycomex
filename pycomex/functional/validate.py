"""
Configuration file validation for PyComex.

This module provides comprehensive validation for PyComex YAML configuration files,
checking syntax, structure, parameter names, mixin existence, and more.

Example usage:

.. code-block:: python

    from pycomex.functional.validate import ConfigValidator

    validator = ConfigValidator("my_config.yml")
    success, results = validator.validate()

    if success:
        print("Config is valid!")
    else:
        print("Config has errors:")
        for result in results:
            if not result.passed:
                print(f"  - {result.message}")
"""

import difflib
import json
import os
import re
from dataclasses import dataclass
from typing import Any

import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pycomex.functional.experiment import Experiment, ExperimentConfig
from pycomex.functional.mixin import ExperimentMixin
from pycomex.utils import dynamic_import


@dataclass
class ValidationResult:
    """
    Represents the result of a single validation check.

    Attributes:
        passed: Whether the validation check passed
        message: Short description of what was validated
        level: Severity level ('error', 'warning', 'info')
        details: Optional detailed message with more context
    """

    passed: bool
    message: str
    level: str  # 'error', 'warning', 'info'
    details: str | None = None

    def __post_init__(self):
        """Validate level is one of the allowed values."""
        if self.level not in ['error', 'warning', 'info']:
            raise ValueError(f"Invalid level: {self.level}. Must be 'error', 'warning', or 'info'")


class ConfigValidator:
    """
    Validates PyComex configuration files comprehensively.

    This class performs a series of validation checks on a PyComex YAML configuration
    file, ensuring it is correctly formatted and references valid experiments and mixins.

    Validation checks include:
    - File existence and readability
    - YAML syntax correctness
    - Required field presence (extend, parameters)
    - Base experiment file existence and validity
    - Parameter name matching with base experiment
    - Mixin file existence and validity
    - Environment variable availability
    - Path field validity

    Example:

    .. code-block:: python

        validator = ConfigValidator("config.yml", warnings_as_errors=False)
        success, results = validator.validate()

        # Format and display results
        output = validator.format_results(verbose=True)
        print(output)

    :param config_path: Path to the YAML configuration file to validate
    :param warnings_as_errors: If True, treat warnings as errors (default: False)
    """

    def __init__(self, config_path: str, warnings_as_errors: bool = False):
        self.config_path = config_path
        self.warnings_as_errors = warnings_as_errors
        self.results: list[ValidationResult] = []
        self.config_data: dict | None = None
        self.experiment_config: ExperimentConfig | None = None

    def validate(self) -> tuple[bool, list[ValidationResult]]:
        """
        Run all validation checks on the configuration file.

        This method executes all validation checks in a logical order, stopping
        if critical errors are found (e.g., file doesn't exist, invalid YAML).

        :returns: A tuple of (success, results) where success is True if all
            checks passed (or only warnings), and results is a list of ValidationResult
            objects for each check performed.
        """
        self.results = []

        # Phase 1: Basic file checks
        result = self.validate_file_exists()
        self.results.append(result)
        if not result.passed:
            return False, self.results

        # Phase 2: YAML syntax
        result = self.validate_yaml_syntax()
        self.results.append(result)
        if not result.passed:
            return False, self.results

        # Phase 3: Schema validation
        result = self.validate_schema()
        self.results.append(result)
        if not result.passed:
            return False, self.results

        # Phase 4: Extended experiment validation
        result = self.validate_extend_field()
        self.results.append(result)
        # Continue even if experiment validation fails (for better error reporting)

        # Phase 5: Parameter validation (only if experiment loaded successfully)
        if self.results[-1].passed:
            result = self.validate_parameters()
            self.results.append(result)

        # Phase 6: Mixin validation
        result = self.validate_mixins()
        self.results.append(result)

        # Phase 7: Environment variable validation
        result = self.validate_env_vars()
        self.results.append(result)

        # Phase 8: Path validation
        result = self.validate_paths()
        self.results.append(result)

        # Determine overall success
        has_errors = any(
            not r.passed and r.level == 'error'
            for r in self.results
        )
        has_warnings = any(
            not r.passed and r.level == 'warning'
            for r in self.results
        )

        if self.warnings_as_errors:
            success = not (has_errors or has_warnings)
        else:
            success = not has_errors

        return success, self.results

    def validate_file_exists(self) -> ValidationResult:
        """
        Validate that the configuration file exists and is readable.

        :returns: ValidationResult indicating whether the file exists
        """
        try:
            if not os.path.exists(self.config_path):
                return ValidationResult(
                    passed=False,
                    message="Config file not found",
                    level='error',
                    details=f"File does not exist: {self.config_path}"
                )

            if not os.path.isfile(self.config_path):
                return ValidationResult(
                    passed=False,
                    message="Config path is not a file",
                    level='error',
                    details=f"Path exists but is not a file: {self.config_path}"
                )

            # Try to open and read the file
            with open(self.config_path, 'r') as f:
                f.read()

            return ValidationResult(
                passed=True,
                message="File exists and is readable",
                level='info'
            )

        except PermissionError:
            return ValidationResult(
                passed=False,
                message="Permission denied",
                level='error',
                details=f"Cannot read file (permission denied): {self.config_path}"
            )
        except Exception as e:
            return ValidationResult(
                passed=False,
                message="File access error",
                level='error',
                details=f"Error accessing file: {str(e)}"
            )

    def validate_yaml_syntax(self) -> ValidationResult:
        """
        Validate that the file contains valid YAML syntax.

        :returns: ValidationResult indicating whether YAML is valid
        """
        try:
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.load(f, Loader=yaml.FullLoader)

            if self.config_data is None:
                return ValidationResult(
                    passed=False,
                    message="Config file is empty",
                    level='error',
                    details="File parsed successfully but contains no data"
                )

            return ValidationResult(
                passed=True,
                message="YAML syntax is valid",
                level='info'
            )

        except yaml.YAMLError as e:
            return ValidationResult(
                passed=False,
                message="Invalid YAML syntax",
                level='error',
                details=f"YAML parsing error: {str(e)}"
            )
        except Exception as e:
            return ValidationResult(
                passed=False,
                message="Error reading YAML",
                level='error',
                details=f"Unexpected error: {str(e)}"
            )

    def validate_schema(self) -> ValidationResult:
        """
        Validate that the config has required fields and correct structure.

        :returns: ValidationResult indicating whether schema is valid
        """
        try:
            # Try to create an ExperimentConfig using Pydantic validation
            self.experiment_config = ExperimentConfig(
                path=self.config_path,
                **self.config_data
            )

            return ValidationResult(
                passed=True,
                message="Required fields present (extend, parameters)",
                level='info'
            )

        except ValidationError as e:
            # Extract missing fields from Pydantic error
            errors = e.errors()
            missing_fields = [err['loc'][0] for err in errors if err['type'] == 'missing']

            if missing_fields:
                details = f"Missing required fields: {', '.join(missing_fields)}"
            else:
                details = f"Schema validation error: {str(e)}"

            return ValidationResult(
                passed=False,
                message="Schema validation failed",
                level='error',
                details=details
            )
        except Exception as e:
            return ValidationResult(
                passed=False,
                message="Schema validation error",
                level='error',
                details=f"Unexpected error: {str(e)}"
            )

    def validate_extend_field(self) -> ValidationResult:
        """
        Validate that the 'extend' field points to a valid experiment file.

        :returns: ValidationResult indicating whether extended experiment is valid
        """
        try:
            extend_path = self.experiment_config.extend

            # Check if it's a relative path
            if not os.path.isabs(extend_path):
                # Resolve relative to config file directory
                config_dir = os.path.dirname(os.path.abspath(self.config_path))
                full_extend_path = os.path.join(config_dir, extend_path)
            else:
                full_extend_path = extend_path

            # Check file exists
            if not os.path.exists(full_extend_path):
                return ValidationResult(
                    passed=False,
                    message=f"Base experiment not found: {extend_path}",
                    level='error',
                    details=f"File does not exist: {full_extend_path}"
                )

            # Check it's a Python file
            if not extend_path.endswith('.py'):
                return ValidationResult(
                    passed=False,
                    message=f"Base experiment is not a Python file: {extend_path}",
                    level='error',
                    details="The 'extend' field must point to a .py file"
                )

            # Try to import the experiment
            try:
                experiment = Experiment.import_from(full_extend_path, {})
                return ValidationResult(
                    passed=True,
                    message=f"Base experiment found: {os.path.basename(extend_path)}",
                    level='info'
                )
            except Exception as e:
                return ValidationResult(
                    passed=False,
                    message=f"Base experiment is not importable: {extend_path}",
                    level='error',
                    details=f"Import error: {str(e)}"
                )

        except Exception as e:
            return ValidationResult(
                passed=False,
                message="Error validating extend field",
                level='error',
                details=f"Unexpected error: {str(e)}"
            )

    def validate_parameters(self) -> ValidationResult:
        """
        Validate that parameter names match those in the base experiment.

        This method compares the parameters defined in the config against the
        parameters available in the base experiment, warning about typos and
        unknown parameters.

        :returns: ValidationResult indicating whether parameters are valid
        """
        try:
            # Get parameters from config
            config_params = set(self.experiment_config.parameters.keys())

            # Import base experiment to get its parameters
            extend_path = self.experiment_config.extend
            if not os.path.isabs(extend_path):
                config_dir = os.path.dirname(os.path.abspath(self.config_path))
                full_extend_path = os.path.join(config_dir, extend_path)
            else:
                full_extend_path = extend_path

            experiment = Experiment.import_from(full_extend_path, {})
            base_params = set(experiment.parameters.keys())

            # Check for unknown parameters (not in base experiment)
            unknown_params = config_params - base_params
            warnings = []

            for param in unknown_params:
                # Try to find similar parameter names (typo detection)
                close_matches = difflib.get_close_matches(
                    param,
                    base_params,
                    n=1,
                    cutoff=0.6
                )

                if close_matches:
                    warnings.append(
                        f"Parameter '{param}' not found (did you mean '{close_matches[0]}'?)"
                    )
                else:
                    warnings.append(
                        f"Parameter '{param}' not found in base experiment"
                    )

            # Check that parameter values are JSON-serializable
            for param, value in self.experiment_config.parameters.items():
                try:
                    json.dumps(value)
                except (TypeError, OverflowError):
                    warnings.append(
                        f"Parameter '{param}' has non-JSON-serializable value (type: {type(value).__name__})"
                    )

            if warnings:
                return ValidationResult(
                    passed=False,  # Mark as not passed, but level is warning
                    message=f"{len(config_params)} parameters checked ({len(warnings)} warnings)",
                    level='warning',
                    details="\n".join(warnings)
                )
            else:
                return ValidationResult(
                    passed=True,
                    message=f"All {len(config_params)} parameters recognized",
                    level='info'
                )

        except Exception as e:
            return ValidationResult(
                passed=False,
                message="Error validating parameters",
                level='error',
                details=f"Unexpected error: {str(e)}"
            )

    def validate_mixins(self) -> ValidationResult:
        """
        Validate that all specified mixins exist and are valid.

        :returns: ValidationResult indicating whether mixins are valid
        """
        try:
            if self.experiment_config.include is None:
                return ValidationResult(
                    passed=True,
                    message="No mixins specified",
                    level='info'
                )

            # Handle both single mixin and list of mixins
            mixin_paths = self.experiment_config.include
            if isinstance(mixin_paths, str):
                mixin_paths = [mixin_paths]

            errors = []
            config_dir = os.path.dirname(os.path.abspath(self.config_path))

            for mixin_path in mixin_paths:
                # Resolve path
                if not os.path.isabs(mixin_path):
                    full_mixin_path = os.path.join(config_dir, mixin_path)
                else:
                    full_mixin_path = mixin_path

                # Check existence
                if not os.path.exists(full_mixin_path):
                    errors.append(f"Mixin file not found: {mixin_path}")
                    continue

                # Check it's a Python file
                if not mixin_path.endswith('.py'):
                    errors.append(f"Mixin is not a Python file: {mixin_path}")
                    continue

                # Try to import
                try:
                    mixin = ExperimentMixin.import_from(full_mixin_path, {})
                except Exception as e:
                    errors.append(f"Mixin '{mixin_path}' is not importable: {str(e)}")

            if errors:
                return ValidationResult(
                    passed=False,
                    message=f"Mixin validation failed ({len(errors)} errors)",
                    level='error',
                    details="\n".join(errors)
                )
            else:
                count = len(mixin_paths)
                message = f"Mixin '{mixin_paths[0]}' is valid" if count == 1 else f"All {count} mixins are valid"
                return ValidationResult(
                    passed=True,
                    message=message,
                    level='info'
                )

        except Exception as e:
            return ValidationResult(
                passed=False,
                message="Error validating mixins",
                level='error',
                details=f"Unexpected error: {str(e)}"
            )

    def validate_env_vars(self) -> ValidationResult:
        """
        Validate that all referenced environment variables are available.

        :returns: ValidationResult indicating whether environment variables are valid
        """
        try:
            # Pattern to find ${VAR} references
            env_var_pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*?)(?::-(.*?))?\}'

            # Convert config data to string to search for env var references
            config_str = yaml.dump(self.config_data)

            # Find all environment variable references
            matches = re.finditer(env_var_pattern, config_str)
            env_vars_found = set()
            missing_vars = []

            for match in matches:
                var_name = match.group(1)
                has_default = match.group(2) is not None

                env_vars_found.add(var_name)

                # Check if variable exists in environment
                if var_name not in os.environ:
                    if not has_default:
                        missing_vars.append(var_name)

            if not env_vars_found:
                return ValidationResult(
                    passed=True,
                    message="No environment variables referenced",
                    level='info'
                )

            if missing_vars:
                details = "Missing environment variables without defaults:\n" + "\n".join(
                    f"  - ${{{var}}}" for var in missing_vars
                )
                return ValidationResult(
                    passed=False,
                    message=f"Environment variable validation failed ({len(missing_vars)} missing)",
                    level='warning',  # Warning because they might be set at runtime
                    details=details
                )
            else:
                return ValidationResult(
                    passed=True,
                    message=f"All {len(env_vars_found)} environment variables available",
                    level='info'
                )

        except Exception as e:
            return ValidationResult(
                passed=False,
                message="Error validating environment variables",
                level='error',
                details=f"Unexpected error: {str(e)}"
            )

    def validate_paths(self) -> ValidationResult:
        """
        Validate that path fields are valid and don't contain invalid characters.

        :returns: ValidationResult indicating whether paths are valid
        """
        try:
            issues = []

            # Validate base_path if specified
            if hasattr(self.experiment_config, 'base_path') and self.experiment_config.base_path:
                base_path = self.experiment_config.base_path

                # Check for invalid characters
                invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
                if any(char in base_path for char in invalid_chars):
                    issues.append(f"base_path contains invalid characters: {base_path}")

            # Validate namespace if specified
            if hasattr(self.experiment_config, 'namespace') and self.experiment_config.namespace:
                namespace = self.experiment_config.namespace

                # Check for invalid characters (allow / for path separators)
                invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
                if any(char in namespace for char in invalid_chars):
                    issues.append(f"namespace contains invalid characters: {namespace}")

            # Validate name if specified
            if hasattr(self.experiment_config, 'name') and self.experiment_config.name:
                name = self.experiment_config.name

                # Check for invalid characters
                invalid_chars = ['/', '\\', '<', '>', ':', '"', '|', '?', '*']
                if any(char in name for char in invalid_chars):
                    issues.append(f"name contains invalid characters: {name}")

            if issues:
                return ValidationResult(
                    passed=False,
                    message="Path validation failed",
                    level='error',
                    details="\n".join(issues)
                )
            else:
                return ValidationResult(
                    passed=True,
                    message="Path fields are valid",
                    level='info'
                )

        except Exception as e:
            return ValidationResult(
                passed=False,
                message="Error validating paths",
                level='error',
                details=f"Unexpected error: {str(e)}"
            )

    def format_results(self, verbose: bool = False) -> str:
        """
        Format validation results as a Rich-formatted string.

        :param verbose: If True, show detailed messages for all checks

        :returns: Formatted string ready for console output
        """
        console = Console()

        # Create title panel
        config_name = os.path.basename(self.config_path)
        title_panel = Panel(
            f"Config Validation: [bold]{config_name}[/bold]",
            border_style="cyan",
            padding=(0, 2)
        )

        # Collect output
        output_lines = []

        # Add title
        with console.capture() as capture:
            console.print(title_panel)
        output_lines.append(capture.get())
        output_lines.append("")

        # Add results
        for result in self.results:
            # Determine symbol and color
            if result.passed:
                symbol = "✓"
                color = "green"
            elif result.level == 'warning':
                symbol = "⚠"
                color = "yellow"
            else:  # error
                symbol = "✗"
                color = "red"

            # Format message
            text = Text()
            text.append(symbol + " ", style=f"bold {color}")
            text.append(result.message)

            with console.capture() as capture:
                console.print(text)
            output_lines.append(capture.get().rstrip())

            # Add details if verbose or if it's an error/warning
            if result.details and (verbose or not result.passed):
                # Indent details
                for line in result.details.split('\n'):
                    output_lines.append(f"    {line}")

        output_lines.append("")

        # Add summary
        has_errors = any(not r.passed and r.level == 'error' for r in self.results)
        has_warnings = any(not r.passed and r.level == 'warning' for r in self.results)

        if has_errors:
            status_text = Text("Validation: ", style="bold") + Text("FAILED", style="bold red")
            error_count = sum(1 for r in self.results if not r.passed and r.level == 'error')
            status_text.append(f" ({error_count} error(s))", style="red")
        elif has_warnings:
            status_text = Text("Validation: ", style="bold") + Text("PASSED", style="bold yellow")
            warning_count = sum(1 for r in self.results if not r.passed and r.level == 'warning')
            status_text.append(f" ({warning_count} warning(s))", style="yellow")
        else:
            status_text = Text("Validation: ", style="bold") + Text("PASSED", style="bold green")

        with console.capture() as capture:
            console.print(status_text)
        output_lines.append(capture.get())

        return "\n".join(output_lines)
