"""CLI commands for Optuna hyperparameter optimization plugin."""

import os
import rich_click as click

try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    optuna = None

from pycomex.utils import dynamic_import
from pycomex.functional.experiment import Experiment
from pycomex.plugins.optuna.display import RichOptunaStudyList, RichOptunaStudyInfo
from pycomex.plugins.optuna.main import StudyManager


class OptunaCommandsMixin:
    """
    Mixin providing Optuna CLI commands.

    This mixin provides CLI commands for hyperparameter optimization with Optuna:
    - run: Execute experiments with Optuna optimization
    - list: List all studies
    - info: Show detailed study information
    - delete: Delete studies

    The mixin follows the same pattern as PyComex's core command mixins
    (RunCommandsMixin, TemplateCommandsMixin, ArchiveCommandsMixin).
    """

    def __init__(self, plugin=None):
        """
        Initialize the mixin.

        :param plugin: OptunaPlugin instance (required for run command)
        """
        self.plugin = plugin

    @property
    def optuna_group(self):
        """
        Command group for Optuna hyperparameter optimization commands.

        :return: Click command group for Optuna operations
        """
        @click.group(
            name="optuna",
            short_help="Optuna hyperparameter optimization commands"
        )
        def group():
            """Optuna hyperparameter optimization integration."""
            pass

        return group

    @property
    def optuna_run_command(self):
        """
        Run an experiment with Optuna optimization.

        This command executes an experiment with parameter values suggested by Optuna's
        optimization algorithm. The experiment must define the __optuna_parameters__ and
        __optuna_objective__ hooks.

        :return: Click command for running optimized experiments
        """
        @click.command(
            "run",
            short_help="Run an experiment with Optuna optimization",
            context_settings={"ignore_unknown_options": True, "allow_extra_args": True}
        )
        @click.argument(
            "path",
            type=click.Path(exists=True)
        )
        @click.pass_context
        def command(ctx, path):
            """
            Run an experiment module or config file with Optuna optimization.

            This command executes an experiment with parameter values suggested by Optuna's
            optimization algorithm. The experiment must define the __optuna_parameters__ and
            __optuna_objective__ hooks.

            Supports both Python experiment modules (.py) and YAML config files (.yml/.yaml).

            If __OPTUNA_REPETITIONS__ is greater than 1, the experiment will be run multiple times
            with the same parameters and the objective values will be averaged.

            Example usage:

                pycomex optuna run experiment.py

                pycomex optuna run config.yml

                pycomex optuna run experiment.py NUM_EPOCHS=20

                pycomex optuna run config.yml --__OPTUNA_REPETITIONS__ 5
            """
            cli_instance = ctx.obj

            cli_instance.cons.print("[bold cyan]Running experiment with Optuna optimization...[/bold cyan]")

            # Get the plugin instance
            plugin = self.plugin
            if plugin is None:
                cli_instance.cons.print("[bold red]Error:[/bold red] Optuna plugin not loaded")
                return

            try:
                # Determine file type from extension
                extension = os.path.basename(path).split(".")[-1]

                # Load experiment based on file type
                experiment: Experiment | None = None

                # YAML config files
                if extension in ["yml", "yaml"]:
                    experiment = Experiment.from_config(config_path=path)
                    is_config_file = True

                # Python modules
                elif extension in ["py"]:
                    module = dynamic_import(path)
                    if not hasattr(module, "__experiment__"):
                        cli_instance.cons.print(
                            "[bold red]Error:[/bold red] The given python file does not contain a valid experiment module!"
                        )
                        return
                    experiment = module.__experiment__
                    is_config_file = False

                else:
                    cli_instance.cons.print(
                        f"[bold red]Error:[/bold red] Unsupported file type: .{extension}. "
                        f"Expected .py, .yml, or .yaml"
                    )
                    return

                # Parse additional parameters from command line
                # Automatically add --__OPTUNA__ True to enable Optuna mode
                extra_args = list(ctx.args) + ["--__OPTUNA__", "True"]
                experiment.arg_parser.parse(extra_args)

                # Sync special parameters like __DEBUG__, __OPTUNA__, etc.
                experiment.update_parameters_special()

                # Get number of repetitions (always >= 1)
                repetitions = max(1, experiment.parameters.get("__OPTUNA_REPETITIONS__", 1))

                # Initialize plugin state for this trial (unified for single/multi-run)
                plugin.prepare_trial_repetitions(repetitions)

                if repetitions > 1:
                    cli_instance.cons.print(f"[dim]Running {repetitions} repetitions per trial[/dim]")

                # Execute all repetitions
                for rep_idx in range(repetitions):
                    if repetitions > 1:
                        cli_instance.cons.print(f"[dim]Repetition {rep_idx + 1}/{repetitions}[/dim]")

                    # For repetitions after the first, reload experiment to get a fresh instance
                    if rep_idx > 0:
                        if is_config_file:
                            # Reload from config file
                            experiment = Experiment.from_config(config_path=path)
                        else:
                            # Re-import Python module
                            module = dynamic_import(path)
                            experiment = module.__experiment__

                        # Re-apply CLI arguments
                        experiment.arg_parser.parse(extra_args)
                        experiment.update_parameters_special()

                    # Run the experiment
                    experiment.run()

                    # Advance to next repetition (plugin will track this)
                    plugin.advance_repetition()

            except Exception as e:
                cli_instance.cons.print(f"[bold red]Error:[/bold red] {e}")
                import traceback
                traceback.print_exc()
                raise

        return command

    @property
    def optuna_list_command(self):
        """
        List all Optuna studies in the current directory.

        :return: Click command for listing studies
        """
        @click.command(
            "list",
            short_help="List all Optuna studies in current directory"
        )
        @click.pass_obj
        def command(cli_instance):
            """
            List all Optuna studies in the current directory.

            Shows a table with study names, number of trials, best values, and last modification dates.
            """
            if not OPTUNA_AVAILABLE:
                cli_instance.cons.print("[bold red]Error:[/bold red] Optuna is not installed. Install with: pip install pycomex[full]")
                return

            # Find the base path (current directory or look for .optuna folder)
            base_path = os.getcwd()
            study_manager = StudyManager(base_path)

            studies = study_manager.list_studies()

            # Use Rich display class
            cli_instance.cons.print(RichOptunaStudyList(studies))

        return command

    @property
    def optuna_info_command(self):
        """
        Show detailed information about a study.

        :return: Click command for showing study information
        """
        @click.command(
            "info",
            short_help="Show detailed information about a study"
        )
        @click.argument("study_name")
        @click.pass_obj
        def command(cli_instance, study_name):
            """
            Show detailed information about a specific Optuna study.

            Displays all trials with their parameters, objective values, and states.
            The best trial is highlighted.
            """
            if not OPTUNA_AVAILABLE:
                cli_instance.cons.print("[bold red]Error:[/bold red] Optuna is not installed. Install with: pip install pycomex[full]")
                return

            base_path = os.getcwd()
            study_manager = StudyManager(base_path)

            try:
                info = study_manager.get_study_info(study_name)
            except ValueError as e:
                cli_instance.cons.print(f"[bold red]Error:[/bold red] {e}")
                return

            # Use Rich display class
            cli_instance.cons.print(RichOptunaStudyInfo(info))

        return command

    @property
    def optuna_delete_command(self):
        """
        Delete Optuna study or studies.

        :return: Click command for deleting studies
        """
        @click.command(
            "delete",
            short_help="Delete Optuna study or studies"
        )
        @click.argument("study_name", required=False)
        @click.option(
            "--all",
            is_flag=True,
            help="Delete all studies in the current directory"
        )
        @click.option(
            "--yes", "-y",
            is_flag=True,
            help="Skip confirmation prompt"
        )
        @click.pass_obj
        def command(cli_instance, study_name, all, yes):
            """
            Delete one or more Optuna studies.

            Either specify a STUDY_NAME to delete a specific study, or use --all to delete
            all studies in the current directory.
            """
            if not OPTUNA_AVAILABLE:
                cli_instance.cons.print("[bold red]Error:[/bold red] Optuna is not installed. Install with: pip install pycomex[full]")
                return

            if not study_name and not all:
                cli_instance.cons.print("[bold red]Error:[/bold red] Must specify either STUDY_NAME or --all flag")
                return

            if study_name and all:
                cli_instance.cons.print("[bold red]Error:[/bold red] Cannot specify both STUDY_NAME and --all flag")
                return

            base_path = os.getcwd()
            study_manager = StudyManager(base_path)

            if all:
                # Delete all studies
                if not yes:
                    studies = study_manager.list_studies()
                    if not studies:
                        cli_instance.cons.print("[yellow]No studies to delete.[/yellow]")
                        return

                    cli_instance.cons.print(f"[bold yellow]Warning:[/bold yellow] This will delete {len(studies)} studies:")
                    for study in studies:
                        cli_instance.cons.print(f"  - {study['name']}")

                    confirm = click.confirm("Are you sure you want to delete all studies?")
                    if not confirm:
                        cli_instance.cons.print("Cancelled.")
                        return

                count = study_manager.delete_all_studies()
                cli_instance.cons.print(f"[bold green]Deleted {count} studies.[/bold green]")

            else:
                # Delete specific study
                if not yes:
                    confirm = click.confirm(f"Are you sure you want to delete study '{study_name}'?")
                    if not confirm:
                        cli_instance.cons.print("Cancelled.")
                        return

                success = study_manager.delete_study(study_name)
                if success:
                    cli_instance.cons.print(f"[bold green]Study '{study_name}' deleted successfully.[/bold green]")
                else:
                    cli_instance.cons.print(f"[bold red]Error:[/bold red] Could not delete study '{study_name}' (not found or permission denied)")

        return command

    @property
    def optuna_report_command(self):
        """
        Generate HTML report with visualizations for a study.

        :return: Click command for generating reports
        """
        @click.command(
            "report",
            short_help="Generate HTML report with visualizations"
        )
        @click.argument("study_name")
        @click.option(
            "--output", "-o",
            type=click.Path(),
            help="Output directory path (default: {study_name}_report in current directory)"
        )
        @click.pass_obj
        def command(cli_instance, study_name, output):
            """
            Generate an HTML report with visualizations for an Optuna study.

            Creates a folder containing:
            - index.html: Main report page with study summary and analysis
            - plots/: Directory with all visualization PNG files

            The report includes:
            - Optimization history showing convergence
            - Parameter importance analysis
            - Parallel coordinate plot for multi-dimensional view
            - Slice plots showing individual parameter effects
            - Contour plots for parameter interactions
            - Empirical distribution function
            - Trial timeline

            Example usage:

                pycomex optuna report my_study

                pycomex optuna report my_study --output custom_folder

                pycomex optuna report experiment_name -o reports/latest
            """
            if not OPTUNA_AVAILABLE:
                cli_instance.cons.print("[bold red]Error:[/bold red] Optuna is not installed. Install with: pip install pycomex[full]")
                return

            from pycomex.plugins.optuna.report import OptunaReportGenerator

            cli_instance.cons.print(f"[bold cyan]Generating report for study '{study_name}'...[/bold cyan]")

            # Find the base path (current directory or look for .optuna folder)
            base_path = os.getcwd()
            study_manager = StudyManager(base_path)

            # Create report generator
            report_gen = OptunaReportGenerator(study_manager)

            try:
                # Generate report
                report_path = report_gen.generate_report(study_name, output_dir=output)

                # Success message
                cli_instance.cons.print(f"[bold green]✓ Report generated successfully![/bold green]")
                cli_instance.cons.print(f"[dim]Location:[/dim] {report_path.absolute()}")
                cli_instance.cons.print(f"[dim]Open in browser:[/dim] {(report_path / 'index.html').absolute()}")

            except ValueError as e:
                cli_instance.cons.print(f"[bold red]Error:[/bold red] {e}")
                return
            except Exception as e:
                cli_instance.cons.print(f"[bold red]Error generating report:[/bold red] {e}")
                import traceback
                cli_instance.cons.print(f"[dim]{traceback.format_exc()}[/dim]")
                raise

        return command
