"""Console script for pycomex."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import typing as t
import zipfile
from typing import Dict, Optional

import rich
import rich_click
import rich_click as click
from click.globals import get_current_context
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement
from rich.padding import Padding
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from rich.columns import Columns
from uv import find_uv_bin

from pycomex.functional.experiment import Experiment, run_experiment
from pycomex.utils import (
    TEMPLATE_ENV,
    TEMPLATE_PATH,
    dynamic_import,
    get_version,
    has_file_extension,
    is_experiment_archive,
    set_file_extension,
)

click.rich_click.USE_RICH_MARKUP = True


def section(string: str, length: int, padding: int = 2):
    half = int((length - len(string)) / 2) - padding
    rest = (length - len(string)) % 2
    return "\n".join(
        [
            "=" * length,
            "=" * half
            + " " * padding
            + string.upper()
            + " " * padding
            + "=" * (half + rest),
            "=" * length,
        ]
    )


def subsection(string: str, length: int, padding: int = 2):
    half = int((length - len(string)) / 2) - padding
    rest = (length - len(string)) % 2
    return "\n".join(
        [
            "-" * half
            + " " * padding
            + string.upper()
            + " " * padding
            + "-" * (half + rest),
        ]
    )


TEMPLATE_ENV.globals.update(
    {
        "section": section,
        "subsection": subsection,
    }
)

class RichLogo:
    """
    A rich display which will show the ASlurmX logo in ASCII art when printed.
    """

    STYLE = Style(bold=True, color="white")

    def __rich_console__(self, console, options):
        text_path = os.path.join(TEMPLATE_PATH, "logo_text.txt")
        with open(text_path) as file:
            text_string: str = file.read()
            text = Text(text_string, style=self.STYLE)
            
        image_path = os.path.join(TEMPLATE_PATH, "logo_image.txt")
        with open(image_path) as file:
            image_string: str = file.read()
            # Replace \e with actual escape character and create Text from ANSI
            ansi_string = image_string.replace('\\e', '\033')
            image = Text.from_ansi(ansi_string)
            
        side_by_side = Columns([image, text], equal=True, padding=(0, 3))
        yield Padding(side_by_side, (1, 3, 0, 3))


class RichHelp:

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        yield "[white bold]PyComex[/white bold] - A Python framework for computational experiments"
        yield ""
        yield (
            "PyComex is a microframework for the creation, execution and organization of computational experiments "
            "in python. This command line interface offers tools to easily create new experiment modules "
            "from boilerplate templates, inspect and interact with the archive of completed experiments and to "
            "execute experiments directly."
        )
        yield ""
        # ~ Experiment templating
        yield "📌 [magenta bold]Create Experiments[/magenta bold]"
        yield ""
        yield (
            "to create new experiments based on the boilerplate templates, use the [cyan]template[/cyan] command group. "
            "to create a new experiment module, use the [cyan]template experiment[/cyan] command."
        )
        yield Padding(
            Syntax(
                ("pycomex template experiment --name=my_experiment"),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield (
            "To create a new sub experiment derived from an existing experiment, use the [cyan]template extend[/cyan] command."
        )
        yield Padding(
            Syntax(
                (
                    "pycomex template extend --from=my_experiment.py --name=my_sub_experiment"
                ),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield ("Use [cyan]pycomex template --help[/cyan] for more information")
        yield ""

        # ~ Experiment execution
        yield "📌 [magenta bold]Run Experiments[/magenta bold]"
        yield ""
        yield (
            "To start a new run of an experiment module, you can either execute the python module directly - using "
            "[cyan]python my_experiment.py[/cyan] - or you can use the [cyan]run[/cyan] command. "
        )
        yield Padding(
            Syntax(
                ("pycomex run my_experiment --PARAM1=5000 --PARAM2=20"),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield ("Use [cyan]pycomex run --help[/cyan] for more information")
        yield ""

        # ~ Experiment Archives
        yield "📌 [magenta bold]Experiment Archives[/magenta bold]"
        yield ""
        yield (
            "All experiments that are executed will automatically be archived in a structured way. "
            "The [cyan]archive[/cyan] command group can be used to interact with the archive of completed experiments. "
            "The [cyan]archive info[/cyan] command can be used to print generic information about the selected archive "
            "folder, for instance."
        )
        yield Padding(
            Syntax(
                ("pycomex archive info"),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield ("Use [cyan]pycomex archive --help[/cyan] for more information")


class RichExperimentParameterInfo:

    def __init__(self, experiment: Experiment):
        self.experiment = experiment

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        width = options.size.width

        num_parameters = len(self.experiment.metadata["parameters"])
        for index, (parameter, data) in enumerate(
            self.experiment.metadata["parameters"].items()
        ):
            title = f"[cyan]{parameter}[/cyan]"
            if "type" in data:
                title = title + f' - {data["type"]}'

            yield title

            if "description" in data and len(data["description"]) > 3:
                yield data["description"]

            if index + 1 < num_parameters:
                yield ""


class RichExperimentHookInfo:

    def __init__(self, experiment: Experiment):
        self.experiment = experiment

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = options.size.width

        num_parameters = len(self.experiment.metadata["hooks"])
        for index, (hook, data) in enumerate(self.experiment.metadata["hooks"].items()):
            title = f"[magenta]{hook}[/magenta]"
            if "type" in data:
                title = title + f' - {data["type"]}'

            yield title

            if "description" in data and len(data["description"]) > 3:
                yield data["description"]

            if index + 1 < num_parameters:
                yield ""


class RichExperimentInfo:

    def __init__(self, path: str, experiment: Experiment):
        self.path = path
        self.experiment = experiment

        self.name = os.path.basename(self.path).split(".")[0]

    # ~ Implementing renderable
    # The following are magic methods which allow this object to produce the actual rich console
    # output.

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        width = options.size.width

        # ~ The header
        yield rich.panel.Panel(
            rich.align.Align(self.name, align="center"),
            box=rich.box.HEAVY,
            style="markdown.h1.border",
        )
        yield rich.panel.Panel(
            rich.markdown.Markdown(self.experiment.metadata["description"]),
            title="description",
            title_align="left",
            border_style="bright_black",
        )
        yield rich.panel.Panel(
            RichExperimentParameterInfo(self.experiment),
            title="parmeters",
            title_align="left",
            border_style="bright_black",
        )
        yield rich.panel.Panel(
            RichExperimentHookInfo(self.experiment),
            title="hooks",
            title_align="left",
            border_style="bright_black",
        )

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        return Measurement(len(self.name) + 20, options.max_width)


class RichExperimentList:

    def __init__(self, experiments: list[Experiment]):
        self.experiments = experiments

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = options.size.width

        num_experiments = len(self.experiments)
        for index, experiment in enumerate(self.experiments):
            name = experiment.metadata["name"]
            title = f"[yellow]{name}[/yellow]"
            yield title

            description = experiment.metadata["short_description"]
            yield description

            # parameters = experiment.metadata['parameters']
            # yield f'[bright_black]n.o. params: {len(parameters)}[/bright_black]'

            if index + 1 < num_experiments:
                yield ""


class RichExperimentTailInfo:

    def __init__(self, experiment_path: str, metadata: dict):
        self.experiment_path = experiment_path
        self.metadata = metadata

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        import datetime

        # Extract experiment name from path (last two folders)
        path_parts = self.experiment_path.rstrip("/").split("/")
        experiment_id = (
            "/".join(path_parts[-2:]) if len(path_parts) >= 2 else path_parts[-1]
        )

        # Experiment name and status
        name = self.metadata.get("name", "Unknown")
        status = self.metadata.get("status", "unknown")

        # Status with emojis and colors
        if status == "done":
            status_display = "✅ completed"
            status_color = "green"
        elif status == "running":
            status_display = "⏳ running"
            status_color = "yellow"
        else:
            status_display = f"❌ {status}"
            status_color = "red"

        yield f"[cyan]{name}[/cyan] [{status_color}]{status_display}[/{status_color}] [bright_black]({experiment_id})[/bright_black]"

        # Timing information
        start_time = self.metadata.get("start_time")
        if start_time:
            dt = datetime.datetime.fromtimestamp(start_time)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            yield f"  Started: {formatted_time}"

        # End time if experiment is done
        if status == "done" and start_time:
            duration = self.metadata.get("duration", 0)
            if duration > 0:
                end_time = start_time + duration
                end_dt = datetime.datetime.fromtimestamp(end_time)
                formatted_end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                yield f"  Ended:   {formatted_end_time}"

        # Duration if available
        duration = self.metadata.get("duration", 0)
        if duration > 0:
            duration_str = f"{duration:.2f}s"
            yield f"  Duration: {duration_str}"

        # Short description
        short_desc = self.metadata.get("short_description", "")
        if short_desc:
            # Truncate if too long
            if len(short_desc) > 80:
                short_desc = short_desc[:77] + "..."
            yield f"  [bright_black]{short_desc}[/bright_black]"


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


class CLI(click.RichGroup):

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
        self.add_command(self.template_group)

        self.archive_group.add_command(self.archive_info_command)
        self.archive_group.add_command(self.archive_delete_command)
        self.archive_group.add_command(self.archive_tail_command)
        self.archive_group.add_command(self.archive_compress_command)
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

    @click.command(
        "inspect", short_help="inspect an experiment that was previously terminated."
    )
    @click.argument("experiment_path", type=click.Path(exists=True))
    @click.pass_obj
    def inspect_command(self, experiment_path: str) -> None:
        """
        This command will pass
        """
        experiment_path = os.path.abspath(experiment_path)
        click.secho(f"inspecting experiment @ {experiment_path}")

        # TODO: Implement some pretty printing that shows the metadata etc.

    ## --- "reproduce" command ---

    @click.command(
        "reproduce",
        short_help="reproduce an experiment that was previously terminated in reproducible mode.",
        context_settings={"ignore_unknown_options": True},
    )
    @click.option(
        "--env-only",
        is_flag=True,
        help="Only create the virtual environment and install dependencies.",
    )
    @click.argument("experiment_path", type=click.Path(exists=True))
    @click.argument("experiment_args", type=click.UNPROCESSED, nargs=-1)
    @click.pass_obj
    def reproduce_command(
        self, env_only: bool, experiment_path: str, experiment_args: str
    ) -> None:
        """
        [bright]This command will attempt to execute an experiment that was previously exported in "reproducible" mode. The
        [bold cyan]EXPERIMENT_PATH[/] may either point to an experiment archive folder or a ZIP file containing an
        experiment archive folder.

        [bright]To reproduce the experiment, the command will first reconstruct a virtual environment with the same
        conditions as the original experiment was run in. By default, the experiment will then be executed. To
        only create the virtual environment and install the dependencies, the --env-only flag can be used.
        """
        # processing the experiment arguments
        experiment_options = {}
        for arg in experiment_args:
            if arg.startswith("--"):
                key_value = arg[2:].split("=", 1)
                if len(key_value) == 2:
                    key, value = key_value
                    experiment_options[key] = value

        experiment_path = os.path.abspath(experiment_path)
        click.secho(
            "attempting to reproduce experiment @ "
            + click.style(experiment_path, fg="cyan")
        )
        # The basis for the reproduction of an experiment is the archive folder that is generated by a terminated previous
        # run of an experiment. There are two ways of providing this archive folder to this command: Either directly as
        # a folder or as an archive path which first needs to be extracted into a folder.
        if os.path.isfile(experiment_path):
            if zipfile.is_zipfile(experiment_path):
                archive_path = experiment_path
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    temp_dir = tempfile.mkdtemp(dir=os.path.dirname(experiment_path))
                    zip_ref.extractall(temp_dir)
                    experiment_path = temp_dir

            else:
                click.secho("the provided file path is not a valid archive!", fg="red")
                return

        if not os.path.isdir(experiment_path):
            click.secho("the provided path is not a valid directory!", fg="red")
            return

        # Now that we are sure that we have a valid folder path, we need to check if the given folder
        # actually contains a valid experiment archive.
        if not Experiment.is_archive(experiment_path):
            click.secho(
                "The given folder path is not a valid experiment archive!", fg="red"
            )
            return

        # If we are now sure that the experiment is in fact a valid experiment archive, we can then load the
        # metadata from that experiment. This metadata can then be used to check if the experiment was stored
        # in reproducible mode. If it wasn't we can also terminate the command.
        metadata: dict = Experiment.load_metadata(experiment_path)
        reproducible = (
            metadata["parameters"].get("__REPRODUCIBLE__", {}).get("value", False)
        )
        if not reproducible:
            click.secho(
                "The experiment was not stored in reproducible mode!", fg="red"
            )
            return

        uv = os.fsdecode(find_uv_bin())
        # At this point we can now actually be sure that the given experiment path is valid and that the
        # experiment was stored in valid mode. We can now proceed to actually go through the steps for the
        # reproduction of the experiment.
        # The first of which is the creation of a new virtual environment with the same conditions as
        # the original experiment.
        venv_path = os.path.join(experiment_path, ".venv")
        if not os.path.exists(venv_path):
            click.secho("... creating virtual environment", fg="bright_black")
            subprocess.run([uv, "venv", "--python", "3.10", "--seed", venv_path])

        # After creating the virtual env, we want to install all the dependencies into it
        dependencies_path = os.path.join(
            experiment_path, Experiment.DEPENDENCIES_FILE_NAME
        )
        with open(dependencies_path) as file:
            content: str = file.read()
            dependencies: dict = json.loads(content)

        env = os.environ.copy()
        env["VIRTUAL_ENV"] = venv_path

        click.secho("... installing dependencies", fg="bright_black")
        with tempfile.NamedTemporaryFile("w", delete=True) as file:
            for dep_info in dependencies.values():
                if not dep_info["editable"]:
                    file.write(f'{dep_info["name"]}=={dep_info["version"]}\n')

            file.flush()
            subprocess.run([uv, "pip", "install", "--requirement", file.name], env=env)

        click.secho("... installing sources", fg="bright_black")
        sources_path = os.path.join(experiment_path, ".sources")
        for file_name in os.listdir(sources_path):
            source_path = os.path.join(sources_path, file_name)
            subprocess.run([uv, "pip", "install", "--no-deps", source_path], env=env)

        if env_only:
            click.secho(
                "environment setup complete. skipping experiment execution...",
                fg="green",
            )

        # ~ running the experiment
        click.secho("... collecting parameters", fg="bright_black")
        experiment_parameters = {
            name: info["value"]
            for name, info in metadata["parameters"].items()
            # The boolean usable flag indicates whether ot not a parameter was actually a simple-enough type to
            # be properly json serialized into the metadata file or not. In case it wasn't, we can't use it here.
            if "usable" in info and info["usable"]
        }
        experiment_parameters.update({"__DEBUG__": False, "__REPRODUCIBLE__": False})
        experiment_parameters.update(experiment_options)
        kwargs = [f"--{name}={value}" for name, value in experiment_parameters.items()]

        # Finally we can use uv again to execute the copy of the experiment code that has been stored in the
        # experiment archive as well.
        click.secho("... running experiment", fg="bright_black")
        code_path = os.path.join(experiment_path, Experiment.CODE_FILE_NAME)
        subprocess.run([uv, "run", "--no-project", code_path, *kwargs], env=env)

    ## --- "run" command ---
    # The "run" command is a special command which can be used to execute an experiment module from the command
    # line. Specifically, it should also be possible to execute a standalone experiment config file using this
    # command...

    @click.command(
        "run",
        short_help="Run an experiment module or config file.",
        context_settings=dict(ignore_unknown_options=True),
    )
    @click.argument("path", type=click.Path(exists=True, resolve_path=True))
    @click.argument("experiment_parameters", nargs=-1)
    @click.pass_obj
    def run_command(
        self,
        path: str,
        experiment_parameters: tuple,
    ) -> None:
        """
        Executes the experiment module or config file at the given PATH.
        """
        click.secho(f"Running experiment module @ {path}")
        extension = os.path.basename(path).split(".")[-1]

        # ~ create experiment
        experiment: Experiment | None = None

        # In case of a yml file, we assume that this is a config file which extends upon
        # an existing experiment module.
        if extension in ["yml", "yaml"]:
            experiment = Experiment.from_config(
                config_path=path,
            )

        # In the case of the python file, we assume that this directly represents a python
        # experiment module.
        elif extension in ["py"]:
            module = dynamic_import(path)
            if hasattr(module, "__experiment__"):
                experiment = module.__experiment__

            else:
                click.secho(
                    "The given python file does not contain a valid experiment module!",
                    fg="red",
                )
                return

        # Now we parse out all of the parameters that were passed as additional options to
        # the "run" command.
        experiment.arg_parser.parse(experiment_parameters)

        click.echo("Starting the experiment...")
        experiment.run()

    ## --- "template" command group ---

    @click.group(
        "template", short_help="Command group for templating common file types."
    )
    @click.pass_obj
    def template_group(self):
        """
        This command group contains commands that can be used to create new files from common templates, such
        as experiment modules or analysis notebooks.
        """
        pass

    @click.command("analysis", short_help="Create a template for an analysis notebook.")
    @click.option(
        "-t",
        "--type",
        type=click.Choice(["jupyter"]),
        default="jupyter",
        help="The type of the analysis template to create.",
    )
    @click.option("-o", "--output", type=click.STRING, default="analysis")
    @click.pass_obj
    def template_analysis_command(self, type: str, output: str) -> None:
        """
        Will create a new jupyter notebook file which contains boilerplate code for experiment analysis. These
        analysis notebooks can be used to load specific experiments from an archive folder, access their results,
        sort them according to a customizable criterion and then process the aggregated results into a visualization
        or a table.
        """
        click.echo("Creating analysis template...")

        # If the given "output" string is an absolute path, we use it as it is. Otherwise,
        # we resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        if type == "jupyter":

            template = TEMPLATE_ENV.get_template("analysis.ipynb")

            if not has_file_extension(output_path):
                output_path = set_file_extension(output_path, ".ipynb")

            content = template.render()
            with open(output_path, "w") as file:
                file.write(content)

        elif type == "python":

            template = TEMPLATE_ENV.get_template("analysis.py.j2")

            if not has_file_extension(output_path):
                output_path = set_file_extension(output_path, ".py")

            content = template.render()
            with open(output_path, "w") as file:
                file.write(content)

        click.secho(f"✅ created analysis template @ {output_path}", bold=True)

    @click.command(
        "experiment", short_help="Create a template for a Python experiment module."
    )
    @click.option(
        "-n",
        "--name",
        type=click.STRING,
        required=True,
        help="The name of the experiment module.",
    )
    @click.option(
        "-d",
        "--description",
        type=click.STRING,
        default="A new computational experiment.",
        help="Description of the experiment.",
    )
    @click.pass_obj
    def template_experiment_command(
        self,
        name: str,
        description: str,
    ) -> None:
        """
        Will create a new Python experiment module from a template. The experiment will include
        basic boilerplate code for setting up parameters, logging, and result collection.
        """
        click.echo("Creating experiment template...")

        output = f"{name}.py"

        # If the given "output" string is an absolute path, use it as it is. Otherwise,
        # resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        # Ensure .py extension
        if not has_file_extension(output_path):
            output_path = set_file_extension(output_path, ".py")
        elif not output_path.endswith(".py"):
            output_path = set_file_extension(output_path, ".py")

        template = TEMPLATE_ENV.get_template("experiment.py.j2")
        content = template.render(experiment_name=name, description=description)

        with open(output_path, "w") as file:
            file.write(content)

        click.secho(f"✅ created experiment template @ {output_path}", bold=True)

    @click.command(
        "extend", short_help="Create a new experiment by extending an existing one."
    )
    @click.option(
        "-n",
        "--name",
        type=click.STRING,
        required=True,
        help="The name of the newly created experiment file.",
    )
    @click.option(
        "--from",
        "from_path",
        type=click.Path(exists=True),
        required=True,
        help="File path to an existing experiment module to extend from.",
    )
    @click.pass_obj
    def template_extend_command(
        self,
        name: str,
        from_path: str,
    ) -> None:
        """
        Will create a new Python experiment module by extending an existing experiment. The new
        experiment will inherit all parameters and hook stubs from the base experiment, allowing
        for easy creation of sub-experiments with modified behavior.
        """
        click.echo("Creating extended experiment template...")

        # Load the base experiment
        try:
            # First try to import from the module to get the experiment definition
            base_experiment = Experiment.import_from(from_path, {})
        except Exception as e:
            click.secho(f"Error loading base experiment: {e}", fg="red")
            return

        output = f"{name}.py"

        # If the given "output" string is an absolute path, use it as it is. Otherwise,
        # resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        # Ensure .py extension
        if not has_file_extension(output_path):
            output_path = set_file_extension(output_path, ".py")
        elif not output_path.endswith(".py"):
            output_path = set_file_extension(output_path, ".py")

        # Extract parameters from base experiment
        parameters = base_experiment.metadata.get("parameters", {})
        hooks = base_experiment.metadata.get("hooks", {})

        # Also get the actual parameter values from the parameters dict
        for param_name, param_value in base_experiment.parameters.items():
            if param_name in parameters:
                # Format the value appropriately for Python code
                if isinstance(param_value, str):
                    parameters[param_name]["value"] = repr(param_value)
                else:
                    parameters[param_name]["value"] = param_value

        # Extract function signatures from hook implementations
        import inspect

        # Process all hooks from hook_map to extract their signatures
        for hook_name, hook_functions in base_experiment.hook_map.items():
            if not hook_name.startswith("__") and hook_functions:
                # Ensure the hook exists in our hooks dict
                if hook_name not in hooks:
                    hooks[hook_name] = {"name": hook_name}

                # Get the first hook function implementation for signature extraction
                func = hook_functions[0]
                try:
                    signature = inspect.signature(func)
                    # Format the signature as a string for the template
                    params = []
                    for param_name, param in signature.parameters.items():
                        if param.annotation != param.empty:
                            # Handle typing annotations properly
                            annotation_name = getattr(
                                param.annotation, "__name__", str(param.annotation)
                            )
                            params.append(f"{param_name}: {annotation_name}")
                        else:
                            params.append(param_name)
                    hooks[hook_name]["signature"] = ", ".join(params)

                    # Also try to get the docstring as description
                    if func.__doc__ and "description" not in hooks[hook_name]:
                        hooks[hook_name]["description"] = func.__doc__.strip()

                except Exception:
                    # Fallback to basic signature if inspection fails
                    hooks[hook_name]["signature"] = "e: Experiment"

        # Get the base experiment name for the extend call
        base_experiment_name = os.path.basename(from_path)
        if base_experiment_name.endswith(".py"):
            base_experiment_name = base_experiment_name[:-3]

        template = TEMPLATE_ENV.get_template("experiment_extend.py.j2")
        content = template.render(
            experiment_name=name,
            base_experiment_path=from_path,
            base_experiment_name=base_experiment_name,
            parameters=parameters,
            hooks=hooks,
            description=f"Extended experiment based on {base_experiment_name}",
        )

        with open(output_path, "w") as file:
            file.write(content)

        click.secho(
            f"✅ created extended experiment template @ {output_path}", bold=True
        )

    @click.command(
        "config",
        short_help="Create a new config.yml file by extracting parameters from an existing experiment.",
    )
    @click.option(
        "-n",
        "--name",
        type=click.STRING,
        required=True,
        help="The name of the newly created config file.",
    )
    @click.option(
        "--from",
        "from_path",
        type=click.Path(exists=True),
        required=True,
        help="File path to an existing experiment module to extract configuration from.",
    )
    @click.pass_obj
    def template_config_command(
        self,
        name: str,
        from_path: str,
    ) -> None:
        """
        Will create a new config.yml file by extracting parameters from an existing experiment.
        The config file will extend the base experiment and include all its default parameters.
        """
        click.echo("Creating config template...")

        # Load the base experiment
        try:
            # Import from the module to get the experiment definition
            base_experiment = Experiment.import_from(from_path, {})
        except Exception as e:
            click.secho(f"Error loading base experiment: {e}", fg="red")
            return

        output = f"{name}.yml"

        # If the given "output" string is an absolute path, use it as it is. Otherwise,
        # resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        # Ensure .yml extension
        if not has_file_extension(output_path):
            output_path = set_file_extension(output_path, ".yml")
        elif not output_path.endswith(".yml"):
            output_path = set_file_extension(output_path, ".yml")

        # Extract parameters from base experiment
        parameters = {}

        # Get parameter values from the parameters dict
        for param_name, param_value in base_experiment.parameters.items():
            if not param_name.startswith("__"):
                parameters[param_name] = param_value

        # Get the base experiment name for the extend reference
        base_experiment_name = os.path.basename(from_path)

        template = TEMPLATE_ENV.get_template("config.yml.j2")
        content = template.render(
            config_name=name,
            base_experiment_path=from_path,
            base_experiment_name=base_experiment_name,
            parameters=parameters,
            description=f"Configuration file extending {base_experiment_name}",
        )

        with open(output_path, "w") as file:
            file.write(content)

        click.secho(f"✅ created config template @ {output_path}", bold=True)

    ## --- "archive" command group ---
    # This command group will contain commands that are related to the management of archived
    # experiment results. This includes commands to list, show and delete archived experiments.

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
        "info",
        short_help="Print some top-level information about the experiment archive.",
    )
    @click.option(
        "--full",
        is_flag=True,
        help="Print more detailed information. Can take a long time.",
    )
    @click.pass_obj
    def archive_info_command(self, full: bool) -> None:

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

        ## --- printing basic information ---
        # By default we only print very basic information about the archive mainly the number
        # of experiments that are contained in it.
        self.cons.print(f"Experiment Archive @ {self.archive_path}")
        self.cons.print(
            f"[green]Contains [bold]{len(experiment_archive_paths)}[/bold] experiments.[/green]"
        )

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
            for path in experiment_archive_paths:

                # We load the metadata of the experiment from the archive path.
                experiment_meta_path: str = os.path.join(
                    path, Experiment.METADATA_FILE_NAME
                )
                with open(experiment_meta_path) as file:
                    metadata: dict = json.load(file)

                # We then evaluate the select expression with the metadata and parameters of the
                # experiment as special variables which are available in the expression.
                m = metadata
                p = {
                    param: info["value"]
                    for param, info in metadata["parameters"].items()
                    if "value" in info
                }
                locals: dict = {
                    "metadata": m,
                    "meta": m,
                    "m": m,
                    "parameters": p,
                    "params": p,
                    "p": p,
                }

                try:
                    if eval(select, locals):
                        delete_paths.append(path)

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
