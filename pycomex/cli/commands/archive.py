"""
Command implementations for archive management operations.
"""

import json
import os
import shutil
import sys
import zipfile

import rich_click as click

from pycomex.functional.experiment import Experiment
from pycomex.cli.display import (
    RichArchiveInfo,
    RichExperimentListInfo,
    RichExperimentTailInfo,
)


class ArchiveCommandsMixin:
    """
    Mixin class providing archive-related CLI commands.

    This mixin provides commands for:
    - archive group: Container for all archive commands
    - overview: Display archive statistics
    - list: List archived experiments
    - delete: Delete archived experiments
    - tail: Show recent experiments
    - compress: Compress experiments to ZIP
    - info: Display comprehensive statistics
    - modify: Modify experiment parameters/metadata
    """

    @click.group(
        "archive", short_help="Command group for managing archived experiments."
    )
    @click.option(
        "--path",
        help="The path to the results folder, containing the archived experiments.",
        type=click.Path(resolve_path=True),
        default=os.path.join(os.getcwd(), "results"),
        show_default=True,
    )
    @click.pass_obj
    def archive_group(self, path: str) -> None:
        """
        This command group contains commands that are related to the management of archived experiments.
        This includes commands to list, show and delete archived experiments. For non-default experiment
        archive locations, please use the `--path` option to specify the path where the archived experiments
        are stored.
        """
        if not os.path.exists(path):
            self.cons.print(
                f'[red]The provided path "[bold]{path}[/bold]" does not exist! '
                "Please provide a valid path to the archive folder.[/red]",
            )
            sys.exit(1)

        self.archive_path = path

    @click.command(
        "overview",
        short_help="Print some top-level information about the experiment archive.",
    )
    @click.option(
        "--select",
        type=click.STRING,
        help=(
            "Criterion by which to select the experiments to analyze. Is implemented as a python boolean "
            "expression that may use the special variables `m` (metadata dict) and `p` (parameters dict). "
            "Will be evaluated on all the experiments in the archive."
        ),
    )
    @click.pass_obj
    def archive_overview_command(self, select: str) -> None:
        """
        Display top-level information and comprehensive statistics about the experiment archive.

        This command analyzes the experiments in the archive and provides detailed statistics including:
        - Success/failure rates
        - Timing information (first/last experiment, durations)
        - Parameter and asset statistics
        - Disk space usage

        The --select option determines a snippet of python code which is supposed to evaluate to a boolean
        value that determines whether or not an experiment should be included in the analysis
        (True meaning it will be included, False meaning it will not be included). In this expression,
        the following special variables are available: `m` which is the metadata dictionary of the
        experiment and `p` which is the parameters value dict of the experiment.
        """

        ## --- reading the experiment archive ---

        # This method will return the list of all the absolute string paths of all the individual
        # archived experiments that are contained within the larger given archive path.
        experiment_archive_paths: list[str] = self.collect_experiment_archive_paths(
            self.archive_path
        )

        if len(experiment_archive_paths) == 0:
            self.cons.print(
                f'[red]There are no archived experiments in the given archive path "[bold]{self.archive_path}[/bold]"!'
                f"Perhaps the wrong folder was selected? Set the --path option to the archive"
                f"command group to provide a custom path.[/red]",
                fg="red",
            )
            sys.exit(1)

        # Apply selection filter if provided
        if select is not None:
            self.cons.print(f"Applying selection filter: [cyan]{select}[/cyan]")
            try:
                experiment_archive_paths = self.filter_experiment_archives_by_select(
                    experiment_archive_paths, select
                )
                if len(experiment_archive_paths) == 0:
                    self.cons.print(
                        "[yellow]No experiments match the selection criteria.[/yellow]"
                    )
                    return
            except Exception as e:
                self.cons.print(f"[red]Error during selection: {e}[/red]")
                sys.exit(1)

        ## --- printing detailed information ---
        # Show detailed statistics using RichArchiveInfo
        stats = self._compute_archive_statistics(experiment_archive_paths)
        self.cons.print(f"Experiment Archive @ [grey50]{self.archive_path}[/grey50]")
        if select:
            self.cons.print(f"[bright_black]Filtered by: {select}[/bright_black]")
        self.cons.print()
        archive_info = RichArchiveInfo(stats)
        self.cons.print(archive_info)

    @click.command(
        "list", short_help="List archived experiments with status and duration."
    )
    @click.option(
        "--select",
        type=click.STRING,
        help=(
            "Criterion by which to select the experiments to list. Is implemented as a python boolean "
            "expression that may use the special variables `m` (metadata dict) and `p` (parameters dict). "
            "Will be evaluated on all the experiments in the archive."
        ),
    )
    @click.pass_obj
    def archive_list_command(self, select: str) -> None:
        """
        Lists archived experiments with their status and duration in a compact format.

        Each experiment is displayed on a single line showing:
        - Status emoji (✅ for success, ❌ for failure, ⏳ for running)
        - Full path to the experiment archive
        - Duration in gray if available

        The --select option determines a snippet of python code which is supposed to evaluate to a boolean
        value that determines whether or not an experiment should be included in the list
        (True meaning it will be included, False meaning it will not be included). In this expression,
        the following special variables are available: `m` which is the metadata dictionary of the
        experiment and `p` which is the parameters value dict of the experiment.
        """

        ## --- reading the experiment archive ---

        # Get all experiment archive paths
        experiment_archive_paths: list[str] = self.collect_experiment_archive_paths(
            self.archive_path
        )

        if len(experiment_archive_paths) == 0:
            self.cons.print(
                f'[red]There are no archived experiments in the given archive path "[bold]{self.archive_path}[/bold]"!'
                f"Perhaps the wrong folder was selected? Set the --path option to the archive"
                f"command group to provide a custom path.[/red]"
            )
            sys.exit(1)

        # Apply selection filter if provided
        if select is not None:
            self.cons.print(f"Applying selection filter: [cyan]{select}[/cyan]")
            try:
                experiment_archive_paths = self.filter_experiment_archives_by_select(
                    experiment_archive_paths, select
                )
                if len(experiment_archive_paths) == 0:
                    self.cons.print(
                        "[yellow]No experiments match the selection criteria.[/yellow]"
                    )
                    return
            except Exception as e:
                self.cons.print(f"[red]Error during selection: {e}[/red]")
                sys.exit(1)

        ## --- loading metadata and sorting by start time ---

        experiments_with_metadata = []
        experiments_without_metadata = []

        for path in experiment_archive_paths:
            try:
                experiment_meta_path = os.path.join(path, Experiment.METADATA_FILE_NAME)
                with open(experiment_meta_path) as file:
                    metadata = json.load(file)
                experiments_with_metadata.append((path, metadata))
            except Exception:
                # Collect experiments with invalid metadata separately
                experiments_without_metadata.append(path)

        # Sort experiments with metadata by start_time (oldest first)
        experiments_with_metadata.sort(
            key=lambda x: x[1].get("start_time", 0)
        )

        ## --- displaying experiments ---

        self.cons.print(
            f"Found [bold]{len(experiment_archive_paths)}[/bold] experiments in archive @ [grey50]{self.archive_path}[/grey50]"
        )
        if select:
            self.cons.print(f"[bright_black]Filtered by: {select}[/bright_black]")
        self.cons.print()

        # Display experiments with metadata first (sorted by start time)
        for path, metadata in experiments_with_metadata:
            experiment_display = RichExperimentListInfo(path, metadata)
            self.cons.print(experiment_display)

        # Display experiments with invalid metadata last
        for path in experiments_without_metadata:
            self.cons.print(f"❌ {path} [bright_black](metadata error)[/bright_black]")

        self.cons.print()

    @click.command(
        "delete",
        short_help="Delete archived experiments. Allows to customize selection criteria "
        "to delete only specific experiments.",
    )
    @click.option(
        "--select",
        type=click.STRING,
        help=(
            "Criterion by which to select the experiments to delete. Is implemented as a python boolean "
            "expression that may use the special variables `m` (metadata dict) and `p` (parameters dict). "
            "Will be evaluated on all the experiments in the archive."
        ),
    )
    @click.option("--all", is_flag=True, help="select all experiments for deletion")
    @click.option(
        "--yes", is_flag=True, help="Do not ask for confirmation before deleting."
    )
    @click.option("-v", "--verbose", is_flag=True, help="Print additional information.")
    @click.pass_obj
    def archive_delete_command(
        self,
        select: str,
        all: bool,
        yes: bool,
        verbose: bool,
    ) -> None:
        """
        This command may be used to delete archived experiments from the overall experiment archive.

        The --select option determines a snippet of python code which is supposed to evaluate to a boolean
        value that determines whether or not an experiment should be selected for the deletion or not
        (True meaning it will be deleted, False meaning it will not be deleted). In this expression,
        the following special variables are available : `m` which is the metadata dictionary of the
        experiment and `p` which is the parameters value dict of the experiment.
        If the --yes flag is not set, the command will ask for confirmation before actually deleting
        the experiments. If the --yes flag is set, the command will not ask for confirmation and
        will delete the experiments immediately.
        """

        ## --- reading the experiment archive ---

        # This method will return the list of all the absolute string paths of all the individual
        # archived experiments that are contained within the larger given archive path.
        experiment_archive_paths: list[str] = self.collect_experiment_archive_paths(
            self.archive_path
        )

        if len(experiment_archive_paths) == 0:
            self.cons.print(
                f'[red]There are no archived experiments in the given archive path "[bold]{self.archive_path}[/bold]"!'
                f"Perhaps the wrong folder was selected? Set the --path option to the archive"
                f"command group to provide a custom path.[/red]",
                fg="red",
            )
            sys.exit(1)

        self.cons.print(f"Experiment Archive @ [grey50]{self.archive_path}[/grey50]")
        self.cons.print(
            f"Found a total of [bold white]{len(experiment_archive_paths)}[/bold white] experiments"
        )

        ## --- selecting experiments to delete ---

        # In this list we will collect all the paths of the experiments that we want to delete.
        delete_paths: list[str] = []

        # If the --all option is set, the selection is trivial as we just use all of the
        # experiments that were found in the archive.
        if all:
            self.cons.print("Selecting ALL experiments for deletion...")
            delete_paths = experiment_archive_paths

        elif select is not None:

            self.cons.print(f"Selecting based on expression: [cyan]{select}[/cyan] ...")
            try:
                delete_paths = self.filter_experiment_archives_by_select(
                    experiment_archive_paths, select
                )
            except Exception as e:
                self.cons.print(
                    f'[red]Error evaluating "select" expression: {e}[/red]'
                )
                sys.exit(1)

        elif select is None:
            pass

        ## --- asking for user confirmation ---

        self.cons.print(
            f"Selected [bold white]{len(delete_paths)}[/bold white] experiments for deletion."
        )
        if not yes:
            prompt = f"Are you sure you want to delete {len(delete_paths)} experiments? [y/N] "
            answer = click.prompt(prompt, type=click.Choice(["y", "n"]), default="n")
            if answer.lower() != "y":
                self.cons.print("[red]Aborting deletion of experiments![/red]")
                sys.exit(1)

        ## --- deleting the experiments ---

        self.cons.print("🗑️ Deleting experiments ...")
        for path in delete_paths:
            pass

            if verbose:
                self.cons.print(
                    f" * deleting [bold]{os.path.dirname(path)}[/bold] ([grey50]{path}[/grey50]) ... "
                )

            shutil.rmtree(path)

        self.cons.print("[green]✅ Deleted all selected experiments![/green]")

    @click.command("tail", short_help="Show information about the latest experiments.")
    @click.option(
        "-n",
        "--num",
        default=5,
        type=int,
        help="Number of latest experiments to show (default: 5).",
    )
    @click.option(
        "--select",
        type=click.STRING,
        help=(
            "Criterion by which to select the experiments to delete. Is implemented as a python boolean "
            "expression that may use the special variables `m` (metadata dict) and `p` (parameters dict). "
            "Will be evaluated on all the experiments in the archive."
        ),
    )
    @click.pass_obj
    def archive_tail_command(self, num: int, select: str) -> None:
        """
        Shows basic information about the last N experiments that have been added to the
        results archive. Experiments are sorted by their start time, with the most recent
        experiments shown first.

        The --select option determines a snippet of python code which is supposed to evaluate to a boolean
        value that determines whether or not an experiment should be included in the tail results
        (True meaning it will be included, False meaning it will not be included). In this expression,
        the following special variables are available: `m` which is the metadata dictionary of the
        experiment and `p` which is the parameters value dict of the experiment.
        """

        ## --- reading the experiment archive ---

        # Get all experiment archive paths
        experiment_archive_paths: list[str] = self.collect_experiment_archive_paths(
            self.archive_path
        )

        if len(experiment_archive_paths) == 0:
            self.cons.print(
                f'[red]There are no archived experiments in the given archive path "[bold]{self.archive_path}[/bold]"!'
                f"Perhaps the wrong folder was selected? Set the --path option to the archive"
                f"command group to provide a custom path.[/red]"
            )
            sys.exit(1)

        # Apply selection filter if provided
        if select is not None:
            self.cons.print(f"Applying selection filter: [cyan]{select}[/cyan]")
            try:
                experiment_archive_paths = self.filter_experiment_archives_by_select(
                    experiment_archive_paths, select
                )
                if len(experiment_archive_paths) == 0:
                    self.cons.print(
                        "[yellow]No experiments match the selection criteria.[/yellow]"
                    )
                    return
            except Exception as e:
                self.cons.print(f"[red]Error during selection: {e}[/red]")
                sys.exit(1)

        ## --- loading metadata and sorting by start time ---

        experiments_with_metadata = []
        for path in experiment_archive_paths:
            try:
                experiment_meta_path = os.path.join(path, Experiment.METADATA_FILE_NAME)
                with open(experiment_meta_path) as file:
                    metadata = json.load(file)
                experiments_with_metadata.append((path, metadata))
            except Exception:
                # Skip experiments with invalid metadata
                continue

        # Sort by start_time (most recent first)
        experiments_with_metadata.sort(
            key=lambda x: x[1].get("start_time", 0), reverse=True
        )

        # Take only the requested number
        latest_experiments = experiments_with_metadata[:num]

        if len(latest_experiments) == 0:
            self.cons.print("[red]No experiments with valid metadata found![/red]")
            sys.exit(1)

        ## --- display the results ---

        self.cons.print(
            f"Latest [bold]{len(latest_experiments)}[/bold] experiments from archive @ [grey50]{self.archive_path}[/grey50]"
        )
        self.cons.print()

        # Display each experiment
        for i, (path, metadata) in enumerate(latest_experiments):
            experiment_display = RichExperimentTailInfo(path, metadata)
            self.cons.print(experiment_display)

            # Add separator except for last item
            if i < len(latest_experiments) - 1:
                self.cons.print()

        self.cons.print()

    @click.command(
        "compress", short_help="Compress selected experiments into a ZIP archive."
    )
    @click.option(
        "--select",
        type=click.STRING,
        help=(
            "Criterion by which to select the experiments to compress. Is implemented as a python boolean "
            "expression that may use the special variables `m` (metadata dict) and `p` (parameters dict). "
            "Will be evaluated on all the experiments in the archive."
        ),
    )
    @click.option(
        "--name",
        default="results.zip",
        type=click.STRING,
        help="Name of the output ZIP file (default: results.zip).",
    )
    @click.option("--all", is_flag=True, help="Select all experiments for compression.")
    @click.option("-v", "--verbose", is_flag=True, help="Print additional information.")
    @click.pass_obj
    def archive_compress_command(
        self,
        select: str,
        name: str,
        all: bool,
        verbose: bool,
    ) -> None:
        """
        This command compresses selected archived experiments into a ZIP file.

        The --select option determines a snippet of python code which is supposed to evaluate to a boolean
        value that determines whether or not an experiment should be selected for compression
        (True meaning it will be included, False meaning it will not be included). In this expression,
        the following special variables are available : `m` which is the metadata dictionary of the
        experiment and `p` which is the parameters value dict of the experiment.

        The resulting ZIP file will maintain the same directory structure as the results folder,
        containing only the selected experiments. When extracted, it will create a 'results' folder
        with the same structure as the original archive.
        """

        ## --- reading the experiment archive ---

        # This method will return the list of all the absolute string paths of all the individual
        # archived experiments that are contained within the larger given archive path.
        experiment_archive_paths: list[str] = self.collect_experiment_archive_paths(
            self.archive_path
        )

        if len(experiment_archive_paths) == 0:
            self.cons.print(
                f'[red]There are no archived experiments in the given archive path "[bold]{self.archive_path}[/bold]"!'
                f"Perhaps the wrong folder was selected? Set the --path option to the archive"
                f"command group to provide a custom path.[/red]"
            )
            sys.exit(1)

        self.cons.print(f"Experiment Archive @ [grey50]{self.archive_path}[/grey50]")
        self.cons.print(
            f"Found a total of [bold white]{len(experiment_archive_paths)}[/bold white] experiments"
        )

        ## --- selecting experiments to compress ---

        # In this list we will collect all the paths of the experiments that we want to compress.
        compress_paths: list[str] = []

        if all:
            compress_paths = experiment_archive_paths
        elif select is not None:
            self.cons.print(f"Applying selection filter: [cyan]{select}[/cyan]")
            try:
                compress_paths = self.filter_experiment_archives_by_select(
                    experiment_archive_paths, select
                )
            except Exception as e:
                self.cons.print(f"[red]Error during selection: {e}[/red]")
                sys.exit(1)
        else:
            self.cons.print(
                "[red]You need to provide either --select or --all option to specify which experiments to compress.[/red]"
            )
            sys.exit(1)

        if len(compress_paths) == 0:
            self.cons.print(
                "[yellow]No experiments match the selection criteria.[/yellow]"
            )
            return

        self.cons.print(
            f"Selected [bold]{len(compress_paths)}[/bold] experiments for compression"
        )

        ## --- compressing experiments ---

        output_path = os.path.join(os.getcwd(), name)

        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:

                for experiment_path in compress_paths:
                    # Get the relative path from the archive root to maintain structure
                    rel_path = os.path.relpath(experiment_path, self.archive_path)

                    if verbose:
                        self.cons.print(f"Compressing: [cyan]{rel_path}[/cyan]")

                    # Walk through the experiment directory and add all files
                    for root, _, files in os.walk(experiment_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Calculate the archive path: results/namespace/experiment_id/file
                            archive_path = os.path.join(
                                "results", os.path.relpath(file_path, self.archive_path)
                            )
                            zip_file.write(file_path, archive_path)

                            if verbose:
                                self.cons.print(
                                    f"  Added: [grey50]{archive_path}[/grey50]"
                                )

        except Exception as e:
            self.cons.print(f"[red]Error creating ZIP file: {e}[/red]")
            sys.exit(1)

        self.cons.print(
            f"[green]✅ Successfully compressed {len(compress_paths)} experiments to [bold]{output_path}[/bold][/green]"
        )

        # Show file size
        file_size = os.path.getsize(output_path)
        if file_size > 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.2f} MB"
        elif file_size > 1024:
            size_str = f"{file_size / 1024:.2f} KB"
        else:
            size_str = f"{file_size} bytes"

        self.cons.print(f"Archive size: [bold]{size_str}[/bold]")

    @click.command(
        "info", short_help="Display comprehensive statistics about archived experiments."
    )
    @click.option(
        "--select",
        type=click.STRING,
        help=(
            "Criterion by which to select the experiments to analyze. Is implemented as a python boolean "
            "expression that may use the special variables `m` (metadata dict) and `p` (parameters dict). "
            "Will be evaluated on all the experiments in the archive."
        ),
    )
    @click.pass_obj
    def archive_info_command(self, select: str) -> None:
        """
        Display comprehensive statistics about archived experiments in the archive.

        This command analyzes the experiments in the archive and provides detailed statistics including:
        - Success/failure rates
        - Timing information (first/last experiment, durations)
        - Parameter and asset statistics

        The --select option determines a snippet of python code which is supposed to evaluate to a boolean
        value that determines whether or not an experiment should be included in the analysis
        (True meaning it will be included, False meaning it will not be included). In this expression,
        the following special variables are available: `m` which is the metadata dictionary of the
        experiment and `p` which is the parameters value dict of the experiment.
        """

        ## --- reading the experiment archive ---

        # Get all experiment archive paths
        experiment_archive_paths: list[str] = self.collect_experiment_archive_paths(
            self.archive_path
        )

        if len(experiment_archive_paths) == 0:
            self.cons.print(
                f'[red]There are no archived experiments in the given archive path "[bold]{self.archive_path}[/bold]"!'
                f"Perhaps the wrong folder was selected? Set the --path option to the archive"
                f"command group to provide a custom path.[/red]"
            )
            sys.exit(1)

        # Apply selection filter if provided
        if select is not None:
            self.cons.print(f"Applying selection filter: [cyan]{select}[/cyan]")
            try:
                experiment_archive_paths = self.filter_experiment_archives_by_select(
                    experiment_archive_paths, select
                )
                if len(experiment_archive_paths) == 0:
                    self.cons.print(
                        "[yellow]No experiments match the selection criteria.[/yellow]"
                    )
                    return
            except Exception as e:
                self.cons.print(f"[red]Error during selection: {e}[/red]")
                sys.exit(1)

        ## --- computing statistics ---

        stats = self._compute_archive_statistics(experiment_archive_paths)

        ## --- display results ---

        self.cons.print(f"Archive Statistics @ [grey50]{self.archive_path}[/grey50]")
        if select:
            self.cons.print(f"[bright_black]Filtered by: {select}[/bright_black]")
        self.cons.print()

        archive_info = RichArchiveInfo(stats)
        self.cons.print(archive_info)

    @click.command(
        "modify", short_help="Modify parameters or metadata of archived experiments."
    )
    @click.option(
        "--select",
        type=click.STRING,
        help=(
            "Criterion by which to select the experiments to modify. Is implemented as a python boolean "
            "expression that may use the special variables 'm' (metadata dict) and 'p' (parameters dict). "
            "Will be evaluated on all the experiments in the archive."
        ),
    )
    @click.option(
        "--all", is_flag=True, help="Select all experiments for modification."
    )
    @click.option(
        "--modify-parameters",
        type=click.STRING,
        help=(
            "Python code snippet to modify parameters. The variable 'p' (parameters dict) and 'm' (metadata dict) "
            "are available for use. Example: \"p['LEARNING_RATE'] *= 10\""
        ),
    )
    @click.option(
        "--modify-metadata",
        type=click.STRING,
        help=(
            "Python code snippet to modify metadata. The variable 'm' (metadata dict) and 'p' (parameters dict) "
            "are available for use. Example: \"m['tags'] = ['processed']\""
        ),
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        help="Preview changes without actually modifying the files.",
    )
    @click.option("-v", "--verbose", is_flag=True, help="Print detailed progress information.")
    @click.pass_obj
    def archive_modify_command(
        self,
        select: str,
        all: bool,
        modify_parameters: str,
        modify_metadata: str,
        dry_run: bool,
        verbose: bool,
    ) -> None:
        """
        This command modifies parameters or metadata of archived experiments.

        The --select option determines a snippet of python code which is supposed to evaluate to a boolean
        value that determines whether or not an experiment should be selected for modification
        (True meaning it will be modified, False meaning it will not be modified). In this expression,
        the following special variables are available: `m` which is the metadata dictionary of the
        experiment and `p` which is the parameters value dict of the experiment.

        The --modify-parameters option allows you to provide Python code that modifies the parameters
        dictionary `p`. The modifications will be persisted to the experiment metadata file.

        The --modify-metadata option allows you to provide Python code that modifies the metadata
        dictionary `m`. The modifications will be persisted to the experiment metadata file.

        If the --dry-run flag is set, the command will preview the changes without actually modifying
        the files.
        """
        # Check that at least one modification option is provided
        if not modify_parameters and not modify_metadata:
            self.cons.print(
                "[red]Error: At least one of --modify-parameters or --modify-metadata must be provided.[/red]"
            )
            sys.exit(1)

        # Check that at least one selection option is provided
        if not select and not all:
            self.cons.print(
                "[red]Error: Either --select or --all must be provided to specify which experiments to modify.[/red]"
            )
            sys.exit(1)

        ## --- reading the experiment archive ---

        # Collect all experiment archive paths
        experiment_archive_paths: list[str] = self.collect_experiment_archive_paths(
            self.archive_path
        )

        if len(experiment_archive_paths) == 0:
            self.cons.print(
                f'[red]There are no archived experiments in the given archive path "[bold]{self.archive_path}[/bold]"!'
                f"Perhaps the wrong folder was selected? Set the --path option to the archive "
                f"command group to provide a custom path.[/red]"
            )
            sys.exit(1)

        self.cons.print(f"Experiment Archive @ [grey50]{self.archive_path}[/grey50]")
        self.cons.print(
            f"Found a total of [bold white]{len(experiment_archive_paths)}[/bold white] experiments"
        )

        ## --- selecting experiments to modify ---

        modify_paths: list[str] = []

        if all:
            self.cons.print("Selecting ALL experiments for modification...")
            modify_paths = experiment_archive_paths
        elif select is not None:
            self.cons.print(f"Selecting based on expression: [cyan]{select}[/cyan] ...")
            try:
                modify_paths = self.filter_experiment_archives_by_select(
                    experiment_archive_paths, select
                )
            except Exception as e:
                self.cons.print(
                    f'[red]Error evaluating "select" expression: {e}[/red]'
                )
                sys.exit(1)

        if len(modify_paths) == 0:
            self.cons.print("[yellow]No experiments match the selection criteria.[/yellow]")
            return

        self.cons.print(
            f"Selected [bold white]{len(modify_paths)}[/bold white] experiments for modification."
        )

        if dry_run:
            self.cons.print("[yellow]DRY RUN MODE - No changes will be saved[/yellow]")

        ## --- validating modification code ---

        # Validate that the provided code snippets are syntactically correct
        if modify_parameters:
            try:
                compile(modify_parameters, "<modify-parameters>", "exec")
            except SyntaxError as e:
                self.cons.print(
                    f"[red]Syntax error in --modify-parameters: {e}[/red]"
                )
                sys.exit(1)

        if modify_metadata:
            try:
                compile(modify_metadata, "<modify-metadata>", "exec")
            except SyntaxError as e:
                self.cons.print(
                    f"[red]Syntax error in --modify-metadata: {e}[/red]"
                )
                sys.exit(1)

        ## --- modifying experiments ---

        self.cons.print("🔧 Modifying experiments ...")
        modified_count = 0
        error_count = 0

        for path in modify_paths:
            try:
                # Load the metadata of the experiment
                experiment_meta_path: str = os.path.join(
                    path, Experiment.METADATA_FILE_NAME
                )
                with open(experiment_meta_path) as file:
                    metadata: dict = json.load(file)

                # Create the evaluation context with metadata and parameters
                m = metadata
                p = {
                    param: info.get("value")
                    for param, info in metadata["parameters"].items()
                    if "value" in info
                }

                # Store original values for verbose output
                if verbose or dry_run:
                    original_p = p.copy()
                    # Note: original_m kept for future enhancement to show metadata changes
                    # original_m = json.loads(json.dumps(m))  # Deep copy

                # Create a safe execution environment
                exec_globals = {"m": m, "p": p}

                # Apply modifications
                if modify_parameters:
                    exec(modify_parameters, exec_globals)
                    # Update the metadata with modified parameter values
                    for param_name, param_value in p.items():
                        if param_name in metadata["parameters"]:
                            metadata["parameters"][param_name]["value"] = param_value

                if modify_metadata:
                    exec(modify_metadata, exec_globals)

                # Show changes if verbose or dry-run
                if verbose or dry_run:
                    # Extract experiment name from path for clearer output
                    path_parts = path.rstrip("/").split("/")
                    experiment_id = (
                        "/".join(path_parts[-2:]) if len(path_parts) >= 2 else path_parts[-1]
                    )

                    self.cons.print(f"\n📝 [cyan]{experiment_id}[/cyan]")

                    if modify_parameters:
                        changes_detected = False
                        for param_name in p.keys():
                            if param_name in original_p and original_p[param_name] != p[param_name]:
                                changes_detected = True
                                self.cons.print(
                                    f"  [yellow]p['{param_name}'][/yellow]: {original_p[param_name]} → {p[param_name]}"
                                )
                        if not changes_detected and verbose:
                            self.cons.print("  [dim]No parameter changes[/dim]")

                    if modify_metadata and verbose:
                        # For metadata, just indicate it was modified (could be complex)
                        self.cons.print("  [green]Metadata modification applied[/green]")

                # Save the modified metadata (unless dry-run)
                if not dry_run:
                    with open(experiment_meta_path, mode="w") as file:
                        content = json.dumps(metadata, indent=4, sort_keys=True)
                        file.write(content)

                    if verbose:
                        self.cons.print("  [green]✓ Saved[/green]")

                modified_count += 1

            except Exception as e:
                error_count += 1
                # Extract experiment name from path
                path_parts = path.rstrip("/").split("/")
                experiment_id = (
                    "/".join(path_parts[-2:]) if len(path_parts) >= 2 else path_parts[-1]
                )
                self.cons.print(
                    f"[red]✗ Error modifying {experiment_id}: {e}[/red]"
                )
                if verbose:
                    import traceback
                    self.cons.print(f"[red]{traceback.format_exc()}[/red]")

        ## --- summary ---

        self.cons.print()
        if dry_run:
            self.cons.print(
                f"[yellow]DRY RUN: Would modify {modified_count} experiment(s)[/yellow]"
            )
        else:
            self.cons.print(
                f"[green]✅ Successfully modified {modified_count} experiment(s)[/green]"
            )

        if error_count > 0:
            self.cons.print(f"[red]❌ Failed to modify {error_count} experiment(s)[/red]")
