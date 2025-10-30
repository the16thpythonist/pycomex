"""Plugin integrating Optuna hyperparameter optimization into experiments."""

import datetime
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional, Any

import matplotlib.pyplot as plt

try:
    import optuna
    from optuna import Study, Trial
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    optuna = None
    Study = None
    Trial = None
    TPESampler = None

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.plugin import Plugin, hook


class StudyManager:
    """
    Manages Optuna studies and their SQLite database storage.

    The StudyManager creates and maintains a `.optuna` folder in the experiment base path,
    storing each study in a separate SQLite database file. This allows for persistent
    tracking of optimization trials across multiple experiment runs.

    :param base_path: The base path where the `.optuna` folder will be created
    """

    def __init__(self, base_path: str):
        """
        Initialize the StudyManager.

        :param base_path: Absolute path to the experiment base directory
        """
        self.base_path = Path(base_path)
        self.optuna_dir = self.base_path / '.optuna'

        # Create .optuna directory if it doesn't exist
        self.optuna_dir.mkdir(parents=True, exist_ok=True)

    def _get_storage_url(self, study_name: str) -> str:
        """
        Generate the SQLite storage URL for a given study.

        :param study_name: Name of the study
        :returns: SQLite URL string
        """
        db_path = self.optuna_dir / f"{study_name}.db"
        return f"sqlite:///{db_path}"

    def get_or_create_study(
        self,
        study_name: str,
        sampler: Optional[Any] = None,
        direction: str = "maximize"
    ) -> Any:
        """
        Get an existing study or create a new one.

        :param study_name: Name of the study
        :param sampler: Optuna sampler instance (defaults to TPESampler)
        :param direction: Optimization direction ('maximize' or 'minimize')
        :returns: Optuna Study object
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna is not installed. Install with: pip install pycomex[full]")

        storage_url = self._get_storage_url(study_name)

        if sampler is None:
            sampler = TPESampler(n_startup_trials=10, multivariate=True)

        study = optuna.create_study(
            study_name=study_name,
            storage=storage_url,
            load_if_exists=True,
            direction=direction,
            sampler=sampler
        )

        return study

    def list_studies(self) -> list[dict[str, Any]]:
        """
        List all studies in the .optuna directory.

        :returns: List of dictionaries containing study metadata
        """
        if not OPTUNA_AVAILABLE:
            return []

        studies = []

        for db_file in self.optuna_dir.glob("*.db"):
            study_name = db_file.stem
            storage_url = self._get_storage_url(study_name)

            try:
                study = optuna.load_study(
                    study_name=study_name,
                    storage=storage_url
                )

                best_trial = study.best_trial if len(study.trials) > 0 else None

                studies.append({
                    'name': study_name,
                    'n_trials': len(study.trials),
                    'best_value': best_trial.value if best_trial else None,
                    'best_trial_number': best_trial.number if best_trial else None,
                    'direction': study.direction.name,
                    'last_modified': datetime.datetime.fromtimestamp(db_file.stat().st_mtime),
                    'db_path': str(db_file)
                })
            except Exception as e:
                # If study can't be loaded, skip it
                continue

        return studies

    def get_study_info(self, study_name: str) -> dict[str, Any]:
        """
        Get detailed information about a specific study.

        :param study_name: Name of the study
        :returns: Dictionary containing detailed study information
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna is not installed")

        storage_url = self._get_storage_url(study_name)

        try:
            study = optuna.load_study(
                study_name=study_name,
                storage=storage_url
            )
        except KeyError:
            raise ValueError(f"Study '{study_name}' not found")

        trials_data = []
        for trial in study.trials:
            trials_data.append({
                'number': trial.number,
                'state': trial.state.name,
                'value': trial.value,
                'params': trial.params,
                'datetime_start': trial.datetime_start,
                'datetime_complete': trial.datetime_complete,
                'duration': trial.duration.total_seconds() if trial.duration else None,
            })

        return {
            'name': study_name,
            'direction': study.direction.name,
            'n_trials': len(study.trials),
            'best_trial': study.best_trial.number if len(study.trials) > 0 else None,
            'best_value': study.best_value if len(study.trials) > 0 else None,
            'best_params': study.best_params if len(study.trials) > 0 else {},
            'trials': trials_data,
        }

    def delete_study(self, study_name: str) -> bool:
        """
        Delete a specific study and its database file.

        :param study_name: Name of the study to delete
        :returns: True if deletion was successful, False otherwise
        """
        db_path = self.optuna_dir / f"{study_name}.db"

        if db_path.exists():
            try:
                db_path.unlink()
                return True
            except Exception:
                return False

        return False

    def delete_all_studies(self) -> int:
        """
        Delete all studies in the .optuna directory.

        :returns: Number of studies deleted
        """
        count = 0
        for db_file in self.optuna_dir.glob("*.db"):
            try:
                db_file.unlink()
                count += 1
            except Exception:
                continue

        return count



class OptunaPlugin(Plugin):
    """
    This plugin integrates Optuna hyperparameter optimization into PyComex experiments.

    The plugin provides:
    - Automatic study management with SQLite storage in `.optuna` folder
    - Experiment hooks for parameter optimization and objective tracking
    - CLI commands for running optimizations and inspecting results

    Usage in experiment modules:
        1. Define __optuna_parameters__ hook to specify parameters to optimize
        2. Define __optuna_objective__ hook to extract objective value
        3. Optionally define __optuna_sampler__ hook to customize sampler
        4. Run with: pycomex optuna run experiment.py
    """

    def __init__(self, config):
        super().__init__(config)

        # Study management
        self.base_path: Optional[str] = None
        self.study_manager: Optional[StudyManager] = None

        # Current trial tracking
        self.current_study: Optional[Any] = None
        self.current_trial: Optional[Any] = None

        # Repetition state (unified for single and multi-run)
        self.total_repetitions: int = 1
        self.current_repetition_index: int = 0
        self.collected_objectives: list[float] = []
        self.trial_parameters: Optional[dict] = None

    def prepare_trial_repetitions(self, repetitions: int):
        """
        Prepare for a trial with N repetitions.

        This resets the repetition state and should be called before starting
        a new trial (whether single or multi-run).

        :param repetitions: Number of repetitions (>= 1)
        """
        self.total_repetitions = repetitions
        self.current_repetition_index = 0
        self.collected_objectives = []
        self.trial_parameters = None

    def is_first_repetition(self) -> bool:
        """Check if this is the first repetition of the current trial."""
        return self.current_repetition_index == 0

    def is_last_repetition(self) -> bool:
        """Check if this is the last repetition of the current trial."""
        return self.current_repetition_index == (self.total_repetitions - 1)

    def advance_repetition(self):
        """Advance to the next repetition."""
        self.current_repetition_index += 1

    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register custom CLI commands using the OptunaCommandsMixin."""
        from pycomex.plugins.optuna.cli import OptunaCommandsMixin

        # Create a mixin instance with this plugin instance
        # This allows the commands to access plugin state (for run command)
        mixin = OptunaCommandsMixin(plugin=self)

        # Create the optuna command group and add all subcommands
        optuna_group = mixin.optuna_group
        optuna_group.add_command(mixin.optuna_run_command)
        optuna_group.add_command(mixin.optuna_list_command)
        optuna_group.add_command(mixin.optuna_info_command)
        optuna_group.add_command(mixin.optuna_delete_command)
        optuna_group.add_command(mixin.optuna_report_command)

        # Register the optuna group with the main CLI
        cli.add_command(optuna_group)

    @hook("before_experiment_initialize", priority=0)
    def before_experiment_initialize(
        self, config: Config, experiment: Experiment, **kwargs
    ) -> None:
        """
        This hook is called at the beginning of Experiment.initialize(), after all parameter
        overrides (including CLI arguments) have been applied.

        For unified multi-run architecture:
        - On first repetition: Creates trial, gets parameter suggestions, caches them
        - On subsequent repetitions: Reuses cached parameters from first repetition

        This ensures all repetitions use the same trial parameters for proper averaging.
        """
        # Check if Optuna mode is enabled by checking the parameter value
        optuna_enabled = experiment.parameters.get("__OPTUNA__", False)
        if not optuna_enabled:
            experiment.metadata["__optuna__"] = False
            return

        # Set metadata flag
        experiment.metadata["__optuna__"] = True

        # Store base path for later use
        self.base_path = experiment.base_path

        if not OPTUNA_AVAILABLE:
            experiment.logger.error("Optuna is not installed but __OPTUNA__ flag is set")
            return

        # === FIRST REPETITION: Create trial and get parameters ===
        if self.is_first_repetition():
            experiment.logger.info("Initializing Optuna optimization...")

            # Initialize StudyManager
            self.study_manager = StudyManager(experiment.base_path)

            # Check for required hooks
            if "__optuna_parameters__" not in experiment.hook_map:
                experiment.logger.error(
                    "Optuna optimization requires __optuna_parameters__ hook to be defined. "
                    "See documentation for details."
                )
                experiment.metadata["__optuna__"] = False
                return

            if "__optuna_objective__" not in experiment.hook_map:
                experiment.logger.error(
                    "Optuna optimization requires __optuna_objective__ hook to be defined. "
                    "See documentation for details."
                )
                experiment.metadata["__optuna__"] = False
                return

            # Get sampler from experiment hook or use default
            sampler = experiment.apply_hook("__optuna_sampler__", default=None)
            if sampler is None:
                sampler = TPESampler(n_startup_trials=10, multivariate=True)
                experiment.logger.debug("Using default TPESampler")

            # Determine optimization direction (default: maximize)
            direction = experiment.apply_hook("__optuna_direction__", default="maximize")

            # Get or create study
            study_name = experiment.metadata["name"]
            try:
                self.current_study = self.study_manager.get_or_create_study(
                    study_name=study_name,
                    sampler=sampler,
                    direction=direction
                )
                experiment.logger.info(f"Loaded study '{study_name}' with {len(self.current_study.trials)} existing trials")
            except Exception as e:
                experiment.logger.error(f"Failed to create/load Optuna study: {e}")
                experiment.metadata["__optuna__"] = False
                return

            # Create a new trial
            try:
                self.current_trial = self.current_study.ask()
                experiment.logger.info(f"Created trial #{self.current_trial.number}")
            except Exception as e:
                experiment.logger.error(f"Failed to create trial: {e}")
                experiment.metadata["__optuna__"] = False
                return

            # Get parameter suggestions from experiment hook
            try:
                param_suggestions = experiment.apply_hook(
                    "__optuna_parameters__",
                    trial=self.current_trial
                )

                if not isinstance(param_suggestions, dict):
                    experiment.logger.error(
                        f"__optuna_parameters__ hook must return a dictionary, got {type(param_suggestions)}"
                    )
                    experiment.metadata["__optuna__"] = False
                    return

                # Cache parameters for subsequent repetitions
                self.trial_parameters = param_suggestions.copy()

                # Replace experiment parameters with trial suggestions
                for param_name, param_value in param_suggestions.items():
                    if param_name in experiment.parameters:
                        old_value = experiment.parameters[param_name]
                        experiment.parameters[param_name] = param_value
                        # Also update the attribute for direct access
                        setattr(experiment, param_name, param_value)
                        experiment.logger.debug(
                            f"Parameter '{param_name}': {old_value} -> {param_value}"
                        )
                    else:
                        experiment.logger.warning(
                            f"Parameter '{param_name}' from __optuna_parameters__ not found in experiment parameters"
                        )

                experiment.logger.info(f"Applied {len(param_suggestions)} parameter suggestions from Optuna trial")

            except Exception as e:
                experiment.logger.error(f"Error applying Optuna parameters: {e}")
                import traceback
                experiment.logger.debug(traceback.format_exc())
                experiment.metadata["__optuna__"] = False
                return

        # === SUBSEQUENT REPETITIONS: Reuse cached parameters ===
        else:
            if self.trial_parameters is None:
                experiment.logger.error("No cached trial parameters found for repetition")
                experiment.metadata["__optuna__"] = False
                return

            experiment.logger.debug(f"Reusing cached parameters for repetition {self.current_repetition_index + 1}/{self.total_repetitions}")

            # Apply cached parameters
            for param_name, param_value in self.trial_parameters.items():
                if param_name in experiment.parameters:
                    experiment.parameters[param_name] = param_value
                    setattr(experiment, param_name, param_value)
                else:
                    experiment.logger.warning(
                        f"Cached parameter '{param_name}' not found in experiment parameters"
                    )

    @hook("after_experiment_finalize", priority=0)
    def after_experiment_finalize(
        self,
        config: Config,
        experiment: Experiment,
        **kwargs,
    ) -> None:
        """
        This hook is called after the experiment finalization.

        For unified multi-run architecture:
        - On all repetitions: Collects objective values
        - On last repetition only: Reports averaged objective to Optuna study

        This ensures stochastic experiments can be properly evaluated across multiple runs.
        """
        # Only proceed if Optuna mode is enabled
        if not experiment.metadata.get("__optuna__", False):
            return

        if not OPTUNA_AVAILABLE or self.current_trial is None or self.current_study is None:
            return

        try:
            # Get objective value from experiment hook
            objective_value = experiment.apply_hook("__optuna_objective__")

            if objective_value is None:
                experiment.logger.error("__optuna_objective__ hook returned None")
                # Mark trial as failed (only on last repetition)
                if self.is_last_repetition():
                    self.current_study.tell(self.current_trial, state=optuna.trial.TrialState.FAIL)
                return

            if not isinstance(objective_value, (int, float)):
                experiment.logger.error(
                    f"__optuna_objective__ must return a numeric value, got {type(objective_value)}"
                )
                # Mark trial as failed (only on last repetition)
                if self.is_last_repetition():
                    self.current_study.tell(self.current_trial, state=optuna.trial.TrialState.FAIL)
                return

            # Collect objective value
            self.collected_objectives.append(objective_value)

            if self.total_repetitions > 1:
                experiment.logger.info(
                    f"Repetition {self.current_repetition_index + 1}/{self.total_repetitions} "
                    f"objective: {objective_value}"
                )

            # === LAST REPETITION: Report averaged objective to Optuna ===
            if self.is_last_repetition():
                # Calculate average objective value
                avg_objective = sum(self.collected_objectives) / len(self.collected_objectives)

                experiment.logger.info("Finalizing Optuna trial...")
                if self.total_repetitions > 1:
                    experiment.logger.info(
                        f"Averaged objective over {len(self.collected_objectives)} repetitions: "
                        f"{avg_objective:.6f} (values: {[f'{v:.6f}' for v in self.collected_objectives]})"
                    )

                # Report averaged objective value and complete trial
                self.current_study.tell(self.current_trial, avg_objective)
                experiment.logger.info(f"Trial #{self.current_trial.number} completed with objective value: {avg_objective}")

                # Log if this is the best trial so far
                if len(self.current_study.trials) > 0:
                    best_value = self.current_study.best_value
                    if avg_objective == best_value:
                        experiment.logger.info("🎉 This is the best trial so far!")

        except Exception as e:
            experiment.logger.error(f"Error finalizing Optuna trial: {e}")
            import traceback
            experiment.logger.debug(traceback.format_exc())
            # Mark trial as failed (only on last repetition)
            if self.is_last_repetition():
                try:
                    self.current_study.tell(self.current_trial, state=optuna.trial.TrialState.FAIL)
                except Exception:
                    pass