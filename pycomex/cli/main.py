"""
Main CLI classes and entry point for PyComex.

This module is part of the refactored CLI package structure. The CLI was previously
a monolithic 2,656-line file (cli.py) and has been reorganized into a modular package
for better maintainability and code organization.

Package Structure
=================

The CLI package is organized as follows::

    pycomex/cli/
    ├── __init__.py              # Public API exports (backward compatibility)
    ├── main.py                  # This file: CLI and ExperimentCLI base classes
    ├── display.py               # Rich display classes for formatted output
    ├── utils.py                 # Helper functions (section, subsection)
    └── commands/
        ├── __init__.py         # Command mixin exports
        ├── run.py              # RunCommandsMixin (run, reproduce, inspect)
        ├── template.py         # TemplateCommandsMixin (template operations)
        └── archive.py          # ArchiveCommandsMixin (archive management)

Architecture: Mixin Pattern
============================

The CLI uses a **mixin pattern** to organize commands into logical groups:

1. **RunCommandsMixin** (commands/run.py):
   - ``run_command()``: Execute experiment modules or config files
   - ``reproduce_command()``: Reproduce experiments from archives
   - ``inspect_command()``: Inspect terminated experiments

2. **TemplateCommandsMixin** (commands/template.py):
   - ``template_group()``: Container for template commands
   - ``template_analysis_command()``: Create analysis notebooks
   - ``template_experiment_command()``: Create new experiments
   - ``template_extend_command()``: Extend existing experiments
   - ``template_config_command()``: Create config files
   - ``template_validate_command()``: Validate config files

3. **ArchiveCommandsMixin** (commands/archive.py):
   - ``archive_group()``: Container for archive commands
   - ``archive_overview_command()``: Display archive statistics
   - ``archive_list_command()``: List archived experiments
   - ``archive_delete_command()``: Delete experiments
   - ``archive_tail_command()``: Show recent experiments
   - ``archive_compress_command()``: Compress to ZIP
   - ``archive_info_command()``: Comprehensive statistics
   - ``archive_modify_command()``: Modify parameters/metadata

Classes in This Module
======================

**ExperimentCLI**: A generic experiment CLI for a folder of experiment modules.
Discovers experiments, lists them, shows info, and executes them.

**CLI**: The main PyComex CLI class that combines all command mixins::

    class CLI(RunCommandsMixin, TemplateCommandsMixin, ArchiveCommandsMixin, click.RichGroup):
        ...

The CLI class inherits from all mixins to provide the complete command set.
It also contains utility methods used by the command mixins:
- ``collect_experiment_archive_paths()``: Collect all experiment archives
- ``filter_experiment_archives_by_select()``: Filter by Python expression
- ``_compute_archive_statistics()``: Compute aggregate statistics

Entry Point
===========

The ``cli()`` function at the bottom of this module is the main entry point
registered in pyproject.toml::

    [project.scripts]
    pycomex = "pycomex.cli:cli"
    pycx = "pycomex.cli:cli"

Backward Compatibility
======================

All imports that previously worked with the monolithic cli.py continue to work::

    from pycomex.cli import ExperimentCLI, CLI, cli

This is maintained through proper exports in ``__init__.py``.

Display Components
==================

Rich display classes are in ``display.py``:
- RichLogo, RichHelp
- RichExperimentInfo, RichExperimentList, RichExperimentParameterInfo
- RichExperimentTailInfo, RichExperimentListInfo
- RichArchiveInfo, RichEnvironmentComparison

These provide formatted, colorful terminal output using the Rich library.
"""

import json
import os
import sys

import rich
import rich.console
import rich_click as click
from click.globals import get_current_context
from rich.console import Console

from pycomex.functional.experiment import Experiment, run_experiment
from pycomex.utils import (
    dynamic_import,
    get_version,
    is_experiment_archive,
)
from pycomex.cli.utils import section
from pycomex.cli.display import (
    RichExperimentInfo,
    RichExperimentList,
    RichLogo,
    RichHelp,
)
from pycomex.cli.commands import (
    RunCommandsMixin,
    TemplateCommandsMixin,
    ArchiveCommandsMixin,
)


class ExperimentCLI(click.RichGroup):
    """
    This class implements a generic experiment click command line interface. It is "generic" in that
    sense that it can be used to implement a distinct experiment CLI for each folder that contains experiment
    modules. Given that experiment folder path, an instance of this class will expose a CLI that can
    list experiments, show detailed experiment information and execute experiments.

    :param name: The string name of the experiment cli
    :param experiments_path: Absolute string path to the folder which contains the experiment modules
    :param experiments_base_path: Absolute string path to the folder that acts as the archive for those
        experiments. This is usually called the "results" folder.
    :param version: A version string can optionally be supplied which will be printed for the
        --version option of the CLI
    :param additional_help: This is a string which can be used to add additional information to the help
        text of the CLI.
    """

    def __init__(
        self,
        name: str,
        experiments_path: str,
        experiments_base_path: str | None = None,
        version: str = "0.0.0",
        additional_help: str = "",
        **kwargs,
    ):
        super(ExperimentCLI, self).__init__(
            name=name, callback=self.callback, invoke_without_command=True, **kwargs
        )
        self.experiments_path = experiments_path
        self.base_path = experiments_base_path
        self.version = version

        version_option = click.Option(["--version"], is_flag=True)
        self.params.append(version_option)

        # ~ Loading all the experiments
        self.experiment_modules: dict[str, str] = {}
        self.experiments: dict[str, Experiment] = {}
        # This method will iterate through all the files in the given experiment folder, check which one of the
        # files is (a) a python file and (b) actually implements an experiment. All those will then be used
        # to populate the self.experiments dictionary so that this can then be used as the basis for all
        # the commands in the group.
        self.discover_experiments()

        # ~ Constructing the help string.
        # This is the string which will be printed when the help option is called.
        self.help = (
            f"Experiment CLI. Use this command line interface to list, show and execute the various "
            f"computational experiments which are contained in this package.\n"
            f"Experiment Modules: {experiments_path}"
        )
        if additional_help != "":
            self.help += "\n\n"
            self.help += additional_help

        self.context = None

        # ~ Adding default commands
        self.add_command(self.list_experiments)

        self.add_command(self.experiment_info)
        self.experiment_info.params[0].type = click.Choice(self.experiments.keys())

        self.add_command(self.run_experiment)
        self.run_experiment.params[0].type = click.Choice(self.experiments.keys())

    ## --- commands ---
    # The following methods are actually the command implementations which are the specific commands
    # that are part of the command group that is represented by the ExperimentCLI object instance itself.

    @click.command(
        "list", short_help="Prints a list of all experiments in this package"
    )
    @click.pass_obj
    def list_experiments(self):
        """
        Prints an overview of all the experiment modules which were discovered in this package.
        """
        experiment_list = RichExperimentList(
            experiments=list(self.experiments.values())
        )
        group = rich.console.Group(
            rich.panel.Panel(
                experiment_list,
                title="experiments",
                title_align="left",
                border_style="bright_black",
            )
        )
        rich.print(group)

    @click.command("info", short_help="Prints information about one experiment")
    @click.argument("experiment")
    @click.pass_obj
    def experiment_info(self, experiment: str, length: int = 100):
        """
        Prints detailed information about the experiment with the string identifier EXPERIMENT.
        """
        experiment_info = RichExperimentInfo(
            path=self.experiment_modules[experiment],
            experiment=self.experiments[experiment],
        )
        rich.print(experiment_info)

    @click.command("run", short_help="Run an experiment")
    @click.argument("experiment")
    @click.pass_obj
    def run_experiment(self, experiment: str, length: int = 100):
        """
        Starts a new run of the experiment with the string identifier EXPERIMENT.
        """
        if self.context.terminal_width is not None:
            length = self.context.terminal_width

        click.secho(section(experiment, length))
        click.secho()

        experiment = run_experiment(
            self.experiment_modules[experiment],
        )

        click.secho(f"archive: {experiment.path}")

    # ~ click.Group implementation

    # This is the method that is actually executed when the CLI object instance itself is invoked!
    def callback(self, version):

        # This is actually really important. If this is left out, all the commands which are implemented
        # as methods of this class will not work at all! Because the "self" argument which they all receive
        # is actually this context object! Thus it is also imperative that all the methods use the
        # "click.pass_obj" decorator.
        self.context = get_current_context()
        self.context.obj = self

        if version:
            print(self.version)
            sys.exit(0)

    ## --- utility functions ---
    # The following methods implement some kind of utiltiy functions for this class

    def discover_experiments(self):
        """
        This method will iterate through all the files (only top level!) of the given self.experiment_path and
        check each file if it is (1) a valid python module and (2) a valid experiment module. All the experiment
        modules that are found are saved to the self.experiments dictionary.

        :returns None:
        """
        assert os.path.exists(self.experiments_path) and os.path.isdir(
            self.experiments_path
        ), (
            f'The provided path "{self.experiments_path}" is not a valid folder path. Please provide the '
            f"path to the FOLDER, which contains all the experiment modules"
        )

        for root, folders, files in os.walk(self.experiments_path):
            for file_name in sorted(files):
                file_path = os.path.join(root, file_name)
                if file_path.endswith(".py"):
                    name, _ = file_name.split(".")

                    # Now just because it is a python file doesn't mean it is an experiment. To make sure we
                    # are going to import each of the python modules.
                    # 27.10.23 - Added the try-except block around this importing operation because previously, the
                    # the construction of the entire CLI object would fail if there was any kind of python module in
                    # the given experiment folder that contained a syntax error for example. With this we will now
                    # simply ignore any modules that contain errors!
                    try:
                        module = dynamic_import(file_path)
                        if hasattr(module, "__experiment__"):
                            self.experiment_modules[name] = file_path
                            self.experiments[name] = module.__experiment__
                    except Exception as e:
                        print(e)

            # We only want to explore the top level directory!
            break

        assert (
            len(self.experiment_modules) != 0
        ), "No experiment modules were detected in the folder of "


class CLI(RunCommandsMixin, TemplateCommandsMixin, ArchiveCommandsMixin, click.RichGroup):
    """
    Main PyComex CLI class.

    This class combines all command mixins to provide the full CLI functionality:
    - RunCommandsMixin: Commands for running and reproducing experiments
    - TemplateCommandsMixin: Commands for creating templates
    - ArchiveCommandsMixin: Commands for managing experiment archives
    """

    def __init__(self, *args, **kwargs):
        click.RichGroup.__init__(self, *args, invoke_without_command=True, **kwargs)
        self.cons = Console()

        # ~ adding the default commands

        # This command can be used to execute existing experiments
        self.add_command(self.run_command)

        # This command can be used to reproduce previously executed experiments
        self.add_command(self.reproduce_command)

        self.template_group.add_command(self.template_analysis_command)
        self.template_group.add_command(self.template_experiment_command)
        self.template_group.add_command(self.template_extend_command)
        self.template_group.add_command(self.template_config_command)
        self.template_group.add_command(self.template_validate_command)
        self.add_command(self.template_group)

        self.archive_group.add_command(self.archive_overview_command)
        self.archive_group.add_command(self.archive_list_command)
        self.archive_group.add_command(self.archive_delete_command)
        self.archive_group.add_command(self.archive_tail_command)
        self.archive_group.add_command(self.archive_compress_command)
        self.archive_group.add_command(self.archive_info_command)
        self.archive_group.add_command(self.archive_modify_command)
        self.add_command(self.archive_group)

    def format_help(self, ctx, formatter) -> None:
        """
        This method overrides the default "format_help" function of the click.Group class.
        This method is used to override the help string that is printed for the --help
        option of the overall group.
        """
        rich.print(RichLogo())
        rich.print(RichHelp())

        self.format_usage(ctx, formatter)
        self.format_options(ctx, formatter)
        self.format_epilog(ctx, formatter)

    ## --- utility methods ---
    # The following methods do not directly implement CLI commands but rather provide utility
    # functionality that can be used throught the CLI commands.

    def collect_experiment_archive_paths(self, path: str) -> list[Experiment]:
        """
        Given the `path` to the experiment archive folder, this method will collect and return
        a list of all the individual experiment archive folders that are contained within
        that larger experiment archive.

        :param path: The absolute string path to the experiment archive folder.

        :returns: A list of absolute string paths to the individual experiment archive folder.
        """
        experiment_namespace_paths: list[str] = []
        for obj_name in os.listdir(path):
            obj_path = os.path.join(path, obj_name)
            if os.path.isdir(obj_path):
                experiment_namespace_paths.append(obj_path)

        # This list will store all the actual experiment archive paths
        experiment_paths: list[Experiment] = []
        for namespace_path in experiment_namespace_paths:
            for dirpath, dirnames, filenames in os.walk(namespace_path):

                if is_experiment_archive(dirpath):
                    experiment_paths.append(dirpath)
                    # prevents the further recursion into the subdirectories of
                    # an already found experiment archive folder.
                    dirnames.clear()

        return experiment_paths

    def filter_experiment_archives_by_select(self, experiment_archive_paths: list[str], select: str) -> list[str]:
        """
        Filter experiment archive paths based on a select expression.

        This method takes a list of experiment archive paths and a select expression,
        loads the metadata for each experiment, and evaluates the select expression
        to determine which experiments should be included in the result.

        :param experiment_archive_paths: List of absolute string paths to experiment archives
        :param select: Python boolean expression that can use 'm' (metadata dict) and 'p' (parameters dict)

        :returns: List of experiment archive paths that match the select criteria
        :raises: Exception if the select expression cannot be evaluated
        """
        filtered_paths: list[str] = []

        for path in experiment_archive_paths:
            # Load the metadata of the experiment from the archive path
            experiment_meta_path: str = os.path.join(
                path, Experiment.METADATA_FILE_NAME
            )
            with open(experiment_meta_path) as file:
                metadata: dict = json.load(file)

            # Create the evaluation context with metadata and parameters
            m = metadata
            p = {
                param: info["value"]
                for param, info in metadata["parameters"].items()
                if "value" in info
            }
            locals_dict: dict = {
                "metadata": m,
                "meta": m,
                "m": m,
                "parameters": p,
                "params": p,
                "p": p,
            }

            # Evaluate the select expression and include path if it returns True
            if eval(select, locals_dict):
                filtered_paths.append(path)

        return filtered_paths

    def _compute_archive_statistics(self, experiment_archive_paths: list[str]) -> dict:
        """
        Compute comprehensive statistics for the given experiment archive paths.

        :param experiment_archive_paths: List of absolute string paths to experiment archives
        :returns: Dictionary containing computed statistics
        """
        stats = {
            "total_experiments": len(experiment_archive_paths),
            "successful_experiments": 0,
            "failed_experiments": 0,
            "error_types": {},  # Track count of each error type
            "first_experiment_time": None,
            "last_experiment_time": None,
            "avg_duration": None,
            "max_duration": None,
            "total_duration": None,
            "avg_parameters": None,
            "total_parameters": None,
            "min_parameters": None,
            "max_parameters": None,
            "avg_assets": None,
            "total_assets": None,
            "min_assets": None,
            "max_assets": None,
            "total_size_gb": None,
        }

        if len(experiment_archive_paths) == 0:
            return stats

        durations = []
        start_times = []
        parameter_counts = []
        asset_counts = []
        total_size_bytes = 0

        for path in experiment_archive_paths:
            try:
                # Load metadata
                experiment_meta_path = os.path.join(path, Experiment.METADATA_FILE_NAME)
                with open(experiment_meta_path) as file:
                    metadata = json.load(file)

                # Success/failure statistics
                status = metadata.get("status", "unknown")
                has_error = metadata.get("has_error", False)

                if status == "done" and not has_error:
                    stats["successful_experiments"] += 1
                else:
                    stats["failed_experiments"] += 1
                    # Track error types for failed experiments
                    error_type = metadata.get("error_type")
                    if error_type:
                        stats["error_types"][error_type] = stats["error_types"].get(error_type, 0) + 1
                    else:
                        # Handle legacy experiments without error_type or experiments that failed without exceptions
                        if status == "failed":
                            stats["error_types"]["Unknown"] = stats["error_types"].get("Unknown", 0) + 1

                # Timing statistics
                start_time = metadata.get("start_time")
                if start_time is not None:
                    start_times.append(start_time)

                duration = metadata.get("duration")
                if duration is not None and duration > 0:
                    durations.append(duration)

                # Parameter statistics
                parameters = metadata.get("parameters", {})
                # Count non-system parameters (exclude __ prefixed)
                user_param_count = sum(1 for param in parameters.keys() if not param.startswith("__"))
                parameter_counts.append(user_param_count)

                # Asset statistics and disk space calculation
                try:
                    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                    asset_count = len(files)
                    asset_counts.append(asset_count)

                    # Calculate disk space for this experiment
                    experiment_size = 0
                    for file_name in files:
                        file_path = os.path.join(path, file_name)
                        try:
                            experiment_size += os.path.getsize(file_path)
                        except (OSError, FileNotFoundError):
                            # Skip files that can't be accessed
                            pass
                    total_size_bytes += experiment_size
                except OSError:
                    # Skip if can't read directory
                    pass

            except (FileNotFoundError, json.JSONDecodeError, OSError):
                # Skip experiments with invalid metadata
                stats["failed_experiments"] += 1
                continue

        # Compute timing statistics
        if start_times:
            stats["first_experiment_time"] = min(start_times)
            stats["last_experiment_time"] = max(start_times)

        if durations:
            stats["avg_duration"] = sum(durations) / len(durations)
            stats["max_duration"] = max(durations)
            stats["total_duration"] = sum(durations)

        # Compute parameter statistics
        if parameter_counts:
            stats["avg_parameters"] = sum(parameter_counts) / len(parameter_counts)
            stats["total_parameters"] = sum(parameter_counts)
            stats["min_parameters"] = min(parameter_counts)
            stats["max_parameters"] = max(parameter_counts)

        # Compute asset statistics
        if asset_counts:
            stats["avg_assets"] = sum(asset_counts) / len(asset_counts)
            stats["total_assets"] = sum(asset_counts)
            stats["min_assets"] = min(asset_counts)
            stats["max_assets"] = max(asset_counts)

        # Compute disk space statistics
        if total_size_bytes > 0:
            stats["total_size_gb"] = total_size_bytes / (1024 ** 3)  # Convert bytes to GB

        return stats


@click.group(cls=CLI)
@click.option("-v", "--version", is_flag=True)
@click.pass_context
def cli(ctx: click.Context, version: bool) -> None:
    """Console script for pycomex."""

    ctx.obj = ctx.command

    if version:
        version = get_version()
        click.secho(version)
        sys.exit(0)


# rich_click.rich_clickify()
if __name__ == "__main__":
    cli()  # pragma: no cover
