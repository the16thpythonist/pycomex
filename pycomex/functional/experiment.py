import argparse
import datetime
import inspect
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
import typing as t
import typing as typ
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import matplotlib.pyplot as plt
import yaml
from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.pretty import pretty_repr
from rich.table import Table
from rich.text import Text
from rich_argparse import RichHelpFormatter
from uv import find_uv_bin

from pycomex.config import Config
from pycomex.functional.cache import ExperimentCache
from pycomex.functional.parameter import ActionableParameterType
from pycomex.utils import (
    TEMPLATE_ENV,
    AnsiSanitizingFormatter,
    CustomJsonEncoder,
    SetArguments,
    dynamic_import,
    file_namespace,
    folder_path,
    get_comments_from_module,
    get_dependencies,
    parse_hook_info,
    parse_parameter_info,
    random_string,
    trigger_notification,
    type_string,
)

HELLO: str = ""


class ExperimentConfig(BaseModel):

    model_config = {"validate_default": True}

    # required fields
    path: str
    extend: str
    parameters: dict[str, Any]

    # optional fields
    name: str | None = None
    base_path: str | None = None
    namespace: str | None = None
    description: str | None = None

    @field_validator("name", mode="after")
    @classmethod
    def default_name(cls, v: object, info: FieldValidationInfo) -> object:

        if v is None:
            path = info.data.get("path")
            file_name_split = os.path.basename(path).split(".")
            return file_name_split[0]

        return v

    @field_validator("base_path", mode="after")
    @classmethod
    def default_base_path(cls, v: object, info: FieldValidationInfo) -> object:
        if v is None:
            path = info.data.get("path")
            return str(folder_path(path))

        return v

    @field_validator("namespace", mode="after")
    @classmethod
    def default_namespace(cls, v: object, info: FieldValidationInfo) -> object:
        if v is None:
            path = info.data.get("path")
            return file_namespace(path)

        return v


class ExperimentArgumentParser(argparse.ArgumentParser):
    """
    This class handles the parsing of the command line arguments when DIRECTLY calling an
    experiment module with the intention of overwriting experiment parameters through the
    command line arguments.

    The parser object is constructed with a reference to the "parameters" map of the
    experiment object which stores the actual experiment parameter values which will be
    available to the experiment code. Additionally, the parser object is also constructed
    with a reference to the "parameter_metadata" dictionary which contains additional
    information about the parameters such as the type and a description.

    Calling the "parse" method will actually parse the command line arguments and then
    update the "parameters" map with all the values that are actually provided through
    the command line arguments.
    """

    def __init__(
        self,
        parameter_map: dict[str, typ.Any],
        parameter_metadata: dict[str, dict],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.parameter_map = parameter_map
        self.parameter_metadata = parameter_metadata

        self.console = Console()

        self.parameters: set[str] = set(parameter_map.keys()) | set(
            parameter_metadata.keys()
        )

        for parameter in self.parameters:

            if parameter:
                value = self.parameter_map.get(parameter, None)
                metadata = self.parameter_metadata.get(parameter, {})

                # it is not entirely clear if a parameter actually has metadata information for a
                # given experiment so we query the values with some safe defaults here.
                metadata = self.parameter_metadata.get(parameter, {})
                type_name = metadata.get("type", "")
                description = metadata.get("description", "")

                # Most importantly the help string will show the type and the description of the parameter
                help_string = f"({type_name}) {description}"

                # If the string representation of the value isn't too long, we also want to include that
                # as additional information in the help string.
                value_string = str(value)
                if value is not None and len(value_string) <= 20:
                    help_string += f" DEFAULT: {value_string}"

                action = self.add_argument(
                    f"--{parameter}", metavar="", help=description
                )
                action.type_string = type_name
                action.default_string = value_string

    def format_help(self):
        """
        Custom implementation of how the help string is output to the console.
        """
        table = Table.grid(expand=True, padding=(0, 2), pad_edge=False)
        table.add_column("Parameter", style="sandy_brown", justify="left")
        table.add_column("Description", style="white", justify="left")

        self._actions.sort(key=lambda x: x.dest)
        for action in self._actions:

            if hasattr(action, "type_string"):

                content = action.help
                if action.type_string:
                    content = f"[bold]({action.type_string})[/bold] {content}"
                if action.default_string:
                    content = f"{content}\n[dim]DEFAULT: {action.default_string}[/dim]"

                if action.option_strings:
                    options = ", ".join(action.option_strings)
                    table.add_row(options, content)
                else:
                    table.add_row(action.dest, content)

        self.console.print("Experiment Parameters:\n")
        self.console.print(table)

    def parse(self, parameters: dict | None = None) -> dict:
        """
        Evaluates the command line arguments and updates the parameter map with the values.
        """
        args = self.parse_args(parameters)
        for parameter in self.parameters:
            if parameter in args and getattr(args, parameter) is not None:
                content = getattr(args, parameter)
                value = eval(content)
                self.parameter_map[parameter] = value

        return self.parameter_map


class Experiment:
    """
    Functional Experiment Implementation. This class acts as a decorator for a function which implements
    the main functionality of a computational experiment. This decorator class primarily handles the
    following aspects of the computational experiment:

    - Automatic construction of the dictionary / file structure for the experiment archive which contains
      the various artifacts that are created during the experiment runtime.
    - Automatic discovery of the experiment parameters which are either given as global variables in the
      corresponding experiment module or alternatively can be overwritten through command line arguments.
    """

    # The name of the archive file that will store all of the experiment data that has been directly
    # commited to the experiment object during the runtime of the experiment.
    DATA_FILE_NAME: str = "experiment_data.json"
    # The name of the archive file that will store the metadata of the experiment during the execution
    # of the experiment as well as afterward.
    METADATA_FILE_NAME: str = "experiment_meta.json"
    # The name of the python module file that will be copied into the experiment archive folder.
    CODE_FILE_NAME: str = "experiment_code.py"

    # This is the filename that will be used to save the python dependencies when terminating the
    # experiment in reproducible mode.
    DEPENDENCIES_FILE_NAME: str = ".dependencies.json"

    def __init__(
        self,
        base_path: str,
        namespace: str,
        glob: dict,
        debug: bool = False,
        name_format: str = "{date}__{time}__{id}",
        notify: bool = True,
        console_width: int = 120,
    ) -> None:

        self.base_path = base_path
        self.namespace = namespace
        self.glob = glob
        self.debug = debug
        self.name_format = name_format
        self.notify = notify
        self.console_width = console_width

        # 26.06.24
        # The config object is a singleton object which is used to store all the configuration information
        # of pycomex in general. Most importantly, the config singleton stores the reference to the plugin
        # manager "pm" that will be used throughout the experiment lifetime to create entry points to extend
        # it's functionality.
        self.config = Config()

        # --- setting up logging ---
        self.log_formatter = logging.Formatter("%(asctime)s - %(message)s")
        self.log_formatter_file = AnsiSanitizingFormatter("%(asctime)s - %(message)s")
        stream_handler = logging.StreamHandler(sys.stdout)
        # stream_handler = RichHandler(
        #     show_level=False,
        #     show_time=False,
        #     show_path=False,
        #     markup=True,
        #     rich_tracebacks=True
        # )
        self.logger = logging.Logger(name="experiment", level=logging.DEBUG)
        self.logger.addHandler(stream_handler)

        # After the experiment was properly initialized, this will hold the absolute string path to the *archive*
        # folder of the current experiment execution!
        self.path: str | None = None

        # 08.11.23
        # Optionally it is possible to define a specific name before the experiment is started and then
        # the experiment archive will be created with that custom name. In the default case (if this stays None)
        # the name will be generated according to some pattern
        self.name: str | None = None

        self.func: t.Callable | None = None
        self.parameters: dict = {}
        self.data: dict = {}
        self.metadata: dict = {
            "status": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "has_error": False,
            "base_path": str(base_path),
            "namespace": str(namespace),
            "description": "",
            "short_description": "",
            "parameters": {},
            "hooks": {},
            # 02.07.24 - This list will store the string names of all the tracked quantities (stored with the
            # "track" method). These names are the keys to the experiment data storage dict where the actual
            # values are stored.
            "__track__": [],
        }

        # 01.10.24 - The special parameters (double underscore) are always a possibility and as such we
        # can already populate the metadata of these parameters without it having to be specifically
        # defined in the individual experiment module.
        self.metadata["parameters"] = {
            "__DEBUG__": {
                "type": "bool",
                "description": (
                    "Flag to enable debug mode. In debug mode the experiment archive folder will be "
                    'called "debug" and will be overwritten when another experiment is started with '
                    "the same name."
                ),
            },
            "__TESTING__": {
                "type": "bool",
                "description": (
                    "Flag to enable testing mode. In testing mode the experiment will be executed "
                    "with minimal runtime and minimal resources simply to test if all the components "
                    "work. Implementing testing mode is optional and will have to be done by each "
                    "experiment individually."
                ),
            },
            "__REPRODUCIBLE__": {
                "type": "bool",
                "description": (
                    "Flag to enable reproducible mode. In reproducible mode, additional information "
                    "will be stored in the experiment archive at the end of the experiment execution. "
                    "This information will include a snapshot of the dependencies and the source code."
                ),
            },
            "__PREFIX__": {
                "type": "str",
                "description": (
                    "A string that will be prefixed to the experiment name. This can be used to "
                    "differentiate between different runs of the same experiment. This will only be "
                    "used as the prefix for the experiment name and not for the actual folder name."
                ),
            },
            "__CACHING__": {
                "type": "bool",
                "description": (
                    "Flag to enable or disable the experiment cache system. When False, cached "
                    "results will not be loaded even if available, forcing recomputation. "
                    "New results will still be saved to cache unless explicitly configured otherwise."
                ),
            },
        }
        # Then we can also set some default values for these special parameters
        self.parameters.update(
            {
                "__DEBUG__": False,
                "__TESTING__": False,
                "__REPRODUCIBLE__": False,
                "__PREFIX__": "",
                "__CACHING__": True,
            }
        )

        self.error = None
        self.tb = None

        # 27.10.23
        # This boolean flag indicates whether the experiment is currently actually being executed or whether one is
        # just dealing with a stored version of the experiment. It will be set to True only right before the actual
        # function implementation of the experiment is executed.
        self.is_running: bool = False
        # 27.10.23
        # This boolean flag indicates whether the experiment is currently in the testing mode. This flag is only
        # set to True after the testing hook function implementation was already executed.
        self.is_testing: bool = False

        # This list will contain the absolute string paths to all the python module files, which this
        # experiment depends on (for example in the case that this experiment is a sub experiment that was
        # created with the "extend" constructor)
        self.dependencies: list[str] = []

        self.analyses: list[t.Callable] = []
        self.hook_map: dict[str, list[t.Callable]] = defaultdict(list)

        # 01.10.24 - We can use this hook to modify the default attributes / metadata of the experiment
        # object before actually starting to load the experiment specific attributes.
        self.config.pm.apply_hook("before_experiment_parameters", experiment=self)

        # --- setting up the cache ---
        # 11.09.25
        # The experiment cache object will be able to manage the cache folder, which can be used inside of
        # an experiment implementation to cache intermediate results - that may be extensive to compute -
        # between individual experiment runs. So if an experiment is executed multiple times and needs to
        # run the same (part of a) compuation multiple times, it can use the cache to store the results
        # of that computation and then load it from the cache in subsequent runs.
        self.cache_path = os.path.join(self.base_path, ".cache")
        self.cache = ExperimentCache(
            path=self.cache_path,
            experiment=self,
        )

        # This method here actually "discovers" all the parameters (=global variables) of the experiment module.
        # It essentially iterates through all the global variables of the given experiment module and then if it finds
        # a parameter (CAPS) it inserts it into the "self.parameters" dictionary of this object.
        self.update_parameters()

        # 27.10.23
        # This method will extract other metadata from the source experiment module. This metadata for example includes
        # a description of the experiment (the doc string of the experiment module).
        # Only after this method has been called, will those properties of the "self.metadata" dict actually contain
        # the appropriate values.
        self.read_module_metadata()

        # Here we do a bit of a trick, we insert a special value into the global dictionary of the source experiment
        # dict wich contains a reference to the experiment object itself. This will later make it a lot easier when we
        # import an experiment module to actually get the experiment object instance from it, because we can't guarantee
        # what variable name the user will actually give it, but this we can assume to always be there.
        self.glob["__experiment__"] = self

        # 06.09.24
        # This object handles the parsing of the command line arguments in the case that the experiment module is
        # exectued directly from the command line. This object will then update the parameters dictionary with the
        # values that were actually provided through the command line arguments.
        self.arg_parser = ExperimentArgumentParser(
            parameter_map=self.parameters,
            parameter_metadata=self.metadata["parameters"],
        )

        # This hook can be used to inject additional functionality at the end of the experiment constructor.
        self.config.pm.apply_hook(
            "experiment_constructed",
            experiment=self,
        )

    @property
    def dependency_names(self) -> list[str]:
        """
        A list of all the names of the python dependency modules, without the file extensions.
        """
        names = []
        for path in self.dependencies:
            name = os.path.basename(path)
            name = os.path.splitext(name)[0]
            names.append(name)

        return names

    def update_parameters_special(self):
        """
        Process special parameters that have side effects beyond simple value storage.

        Special parameters are those that begin and end with double underscores (e.g., __DEBUG__).
        These parameters can trigger specific behaviors or modify experiment state when their
        values change. This method is called after parameter discovery to apply any necessary
        side effects based on the current parameter values.

        Currently handles:
        - __DEBUG__: Enables debug mode which affects archive naming
        - __CACHING__: Controls whether the cache system loads existing cached results

        :returns: None
        """
        if "__DEBUG__" in self.parameters:
            self.debug = bool(self.parameters["__DEBUG__"])

        if "__CACHING__" in self.parameters:
            caching_enabled = bool(self.parameters["__CACHING__"])
            self.cache.set_enabled(caching_enabled)

    def update_parameters(self):
        """
        This method updates the internal parameters dictionary of the experiment object with the values of the
        global variables of the experiment module. This is done by iterating through all the global variables of
        the experiment module and then checking if the variable name is in all caps. If it is, then it is considered
        a parameter and inserted into the parameters dictionary.

        :returns: None
        """
        for name, value in self.glob.items():
            if name.isupper():
                self.parameters[name] = value

        # This method will search through the freshly updated parameters dictionary for "special" keys
        # and then use those values to trigger some more fancy updates based on those.
        self.update_parameters_special()

    def update_arg_parser(self) -> None:
        """
        This method constructs a new experiment argument parser instance based on the current state of
        the parameter dictionary and the parameter metdata dictionary. This is useful to update the
        argument parser in case the parameter dictionary has been updated.

        :returns: None
        """
        self.arg_parser = ExperimentArgumentParser(
            self.parameters, self.metadata["parameters"]
        )

    # ~ Module Metadata

    def read_module_metadata(self):
        """
        This method extract certain information of the original experiment module and saves them as the appropriate
        metadata for the experiment object.
        This information includes for example the module doc string of the experiment module which will be attached as
        the "description" of the experiment.

        :returns: None
        """
        # ~ the experiment name
        # We simply use the name of the python experiment module as the name of the experiment as well!
        name = os.path.basename(self.glob["__file__"]).split(".")[0]
        self.metadata["name"] = name

        # ~ the experiment description
        # We simply say that the docstring of the module is the experiment description.

        doc_string = self.glob["__doc__"]
        doc_string = "" if doc_string is None else doc_string
        description = doc_string.lstrip(" \n")
        self.metadata["description"] = description
        short_description = doc_string.split("\n\n")[0]
        short_description = textwrap.shorten(short_description, width=600)
        self.metadata["short_description"] = short_description

        # ~ the experiment parameters
        # We also importantly want to automatically extract some additionional information about the

        # At the point that this method is usually executed, we can already expect that the experiment parameters
        # were discovered and saved into the self.parameters dictionary.
        # So now we iterate through this dictionary and then.
        for parameter, value in self.parameters.items():
            if parameter not in self.metadata["parameters"]:
                self.metadata["parameters"][parameter] = {
                    "name": parameter,
                }

        # Here we get the type annotations.
        # This also needs some additional justification, becasue the observant reader will question why we do not
        # just use the __annotations__ property of the glob dictionary of the experiment module here. The problem
        # is that we want to get the annotations of the same file before that file is fully loaded by importlib!
        # Which means that in most cases, the __annotations__ dict will not have been created yet!
        # But using inspect like this works, although we have to do a bit of a hack with the frame. I think that we
        # can be sure that the frame twice on top from this point on is always experiment module itself.
        frame = inspect.currentframe().f_back.f_back
        module = inspect.getmodule(frame)
        annotations = inspect.get_annotations(module)

        for parameter, type_instance in annotations.items():
            if parameter in self.parameters:
                self.metadata["parameters"][parameter]["type"] = type_string(
                    type_instance
                )

        module_path = self.glob["__file__"]
        comment_lines = get_comments_from_module(module_path)
        comment_string = "\n".join([line.lstrip("#") for line in comment_lines])
        parameter_info: dict[str, str] = parse_parameter_info(comment_string)
        for parameter, description in parameter_info.items():
            if parameter in self.parameters:
                self.metadata["parameters"][parameter]["description"] = description

        # The experiment hooks
        # We also want to save information about all the available hooks in the metadata dictionary

        # The most basic information that we can gather about the hooks is which hooks are even available
        # at all. This information is directly accessible over the main hook dictionary.
        for hook, func_list in self.hook_map.items():
            if hook not in self.metadata["hooks"]:
                self.metadata["hooks"][hook] = {
                    "name": hook,
                    "num": len(func_list),
                }

        # Then we can do something similar to the parameters, where we parse all the comments inside the
        # experiment module and check if there is the special hook description syntax somewhere.
        hook_info: dict[str, str] = parse_hook_info(comment_string)
        for hook, description in hook_info.items():
            if hook not in self.metadata["hooks"]:
                self.metadata["hooks"][hook] = {
                    "name": hook,
                }

            self.metadata["hooks"][hook]["description"] = description

    # --- Logging --- 
    # The following methods are all related to logging information to the experiment log. This 
    # log will be printed to the console on the one hand but also ends up in a persistent log file 
    # in the experiment archive folder as well.

    def log(self, message: str, **kwargs):
        """
        Log a message to both the console and the experiment log file.

        This is the primary logging method that outputs messages to stdout during
        experiment execution and also saves them to the persistent log file in the
        experiment archive folder.

        Example:

        .. code-block:: python

            experiment.log("Starting model training...")
            experiment.log("Epoch 1 completed with loss: 0.123")

        :param message: The message to log.
        :param kwargs: Additional keyword arguments passed to the logger.
        """
        self.logger.info(message, **kwargs)

    def log_lines(self, lines: list[str]):
        """
        Log multiple lines of text, each as a separate log entry.

        This method is convenient for logging multiple related messages at once,
        such as the output from a subprocess or a list of status updates.

        Example:

        .. code-block:: python

            status_lines = [
                "Model initialization complete",
                "Loading training data",
                "Starting training loop"
            ]
            experiment.log_lines(status_lines)

        :param lines: List of strings, each to be logged as a separate message.
        """
        for line in lines:
            self.log(line)

    def _create_experiment_start_panel(self) -> Panel:
        """
        Create a Rich panel for experiment start information.

        :returns: Rich Panel with experiment start details
        """
        start_time = datetime.datetime.fromtimestamp(self.metadata['start_time'])

        content_lines = [
            f"[bold cyan]Namespace:[/bold cyan] {self.namespace}",
            f"[bold cyan]Start Time:[/bold cyan] {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"[bold cyan]Archive Path:[/bold cyan] {self.path}",
            f"[bold cyan]Debug Mode:[/bold cyan] {self.debug}",
            f"[bold cyan]Parameters:[/bold cyan] {len(self.parameters)} total",
        ]

        # Add Python version and platform info
        content_lines.extend([
            f"[bold cyan]Python Version:[/bold cyan] {sys.version.split()[0]}",
            f"[bold cyan]Platform:[/bold cyan] {sys.platform}",
        ])

        content = "\n".join(content_lines)

        return Panel(
            content,
            title="🚀 [bold green]EXPERIMENT STARTED[/bold green]",
            border_style="green",
            padding=(1, 2),
            expand=True,
            width=self.console_width
        )

    def _create_experiment_end_panel(self) -> Panel:
        """
        Create a Rich panel for experiment end information.

        :returns: Rich Panel with experiment end details
        """
        start_time = datetime.datetime.fromtimestamp(self.metadata['start_time'])
        end_time = datetime.datetime.fromtimestamp(self.metadata['end_time'])
        duration_hrs = self.metadata['duration'] / 3600
        duration_mins = self.metadata['duration'] / 60

        # Format duration nicely
        if duration_hrs >= 1:
            duration_str = f"{duration_hrs:.2f} hours"
        elif duration_mins >= 1:
            duration_str = f"{duration_mins:.1f} minutes"
        else:
            duration_str = f"{self.metadata['duration']:.1f} seconds"

        content_lines = [
            f"[bold cyan]Duration:[/bold cyan] {duration_str}",
            f"[bold cyan]Start Time:[/bold cyan] {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"[bold cyan]End Time:[/bold cyan] {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"[bold cyan]Error Occurred:[/bold cyan] {'Yes' if self.error else 'No'}",
            f"[bold cyan]Parameters Count:[/bold cyan] {len(self.parameters)}",
        ]

        # Add data size information if available
        try:
            if os.path.exists(self.data_path):
                data_size = os.path.getsize(self.data_path)
                if data_size >= 1024 * 1024:  # MB
                    size_str = f"{data_size / (1024 * 1024):.1f} MB"
                elif data_size >= 1024:  # KB
                    size_str = f"{data_size / 1024:.1f} KB"
                else:
                    size_str = f"{data_size} bytes"
                content_lines.append(f"[bold cyan]Data Size:[/bold cyan] {size_str}")
        except (OSError, AttributeError):
            pass

        content = "\n".join(content_lines)

        # Choose panel style based on whether there was an error
        if self.error:
            title = "❌ [bold red]EXPERIMENT ENDED (WITH ERROR)[/bold red]"
            border_style = "red"
        else:
            title = "✅ [bold green]EXPERIMENT COMPLETED[/bold green]"
            border_style = "green"

        return Panel(
            content,
            title=title,
            border_style=border_style,
            padding=(1, 2),
            expand=True,
            width=self.console_width
        )

    def log_parameters(self, parameters: Optional[List[str]] = None):
        """
        Log either all parameters of the experiment or only those specified in the parameters list.

        Each parameter is logged in the format " * {parameter_name}: {parameter_value}".
        Complex objects are safely converted to string representations to avoid logging issues.

        Example:

        .. code-block:: python

            # Log all parameters
            experiment.log_parameters()

            # Log only specific parameters
            experiment.log_parameters(['LEARNING_RATE', 'BATCH_SIZE'])

        :param parameters: Optional list of parameter names to log. If None, all parameters are logged.
        """
        if parameters is None:
            # Log all parameters
            params_to_log = self.parameters
        else:
            # Log only specified parameters
            params_to_log = {name: self.parameters[name] for name in parameters if name in self.parameters}

        for param_name, param_value in params_to_log.items():
            try:
                # Try to convert to string safely
                if isinstance(param_value, (str, int, float, bool, type(None))):
                    # Simple types can be logged directly
                    value_str = str(param_value)
                else:
                    # Complex objects - use repr for safer string conversion
                    value_str = repr(param_value)
                    # Truncate very long representations
                    if len(value_str) > 200:
                        value_str = value_str[:197] + "..."
            except Exception:
                # Fallback for objects that can't be converted safely
                value_str = f"<{type(param_value).__name__} object>"

            self.log(f" * {param_name}: {value_str}")

    def log_pretty(self, value: Any):
        """
        Log a pretty formatted representation of a data structure using rich.pretty.

        This method formats complex data structures in a readable way and logs them
        to the experiment output.

        Example:

        .. code-block:: python

            data = {"metrics": {"accuracy": 0.95, "loss": 0.05}, "config": {"lr": 0.001}}
            experiment.log_pretty(data)

        :param value: The data structure to log in pretty format.
        """
        pretty_string = pretty_repr(value)
        self.log(pretty_string)

    # --- Hook System ---
    # The following methods are related to the hook system of the experiment object, where it 
    # it possible to attach new functions to the experiemnt object which may be overwritten by 
    # subsequent sub-experiment implementations.

    def hook(self, name: str, replace: bool = True, default: bool = True):
        """
        This method can be used to register functions as hook candidates for the experiment object to use
        whenver the corresponding call of the "apply_hook" method is issued with a matching unique string
        identifier ``name``.

        This method returns a decorator function that can be used to decorate functions which should then
        be registered as the callbacks of the hooks.

        NOTE: Every hook callback receives the Experiment object that called it as the first positional argument!

        .. code-block:: python

            @experiment.hook("before_run")
            def before_run(e: Experiment) -> str:
                return "Hello World!"

        :param name: The unique string identifier to associate with the hook.
        :param replace: If this is True, the registered hook will replace any previously registered hooks.
            Otherwise, the hooks will be appended to the list of registered hooks and all of them will be
            executed in the order of their registration when the hook is called.
        :param default: If this is True, the registered hook will be registered but only as a fallback
            option. It won't be used as soon as at least one other callback is registered to the same hook.

        :returns: A decorator function
        """

        def decorator(func, *args, **kwargs):
            # 07.05.23 - The default flag should only be used for any default implementations used within the
            # base experiment file or in any case were the hook is defined for the first time. When that flag
            # is active it will only be used as a fallback option if sub experiment hasn't provided any more
            # relevant implementation.
            if default and name in self.hook_map:
                return

            if replace:
                self.hook_map[name] = [func]
            else:
                # We need to PREPEND the function here because we are actually building the hooks up backwards
                # through the inheritance hierarchy. So the prepending here is actually needed to make it work
                # in the way that a user would intuitively expect.
                self.hook_map[name] = self.hook_map[name] + [func]

        return decorator

    def apply_hook(self, name: str, default: t.Any | None = None, **kwargs):
        """
        This method can be used to execute (all) the registered hook functions that are associated with the
        string identifier ``name``.

        :param name: The unique string identifier of the hook.
        :param default: The default value that will be returned if no hook function is registered for the

        :returns: The return value of the last executed hook function.
        """
        result = default

        if name in self.hook_map:
            for func in self.hook_map[name]:
                result = func(self, **kwargs)

        return result

    # ~ Testing functionality
    # The "testing" functionality refers to a feature of the Experiment object whereby it can be put into the
    # "testing" mode by setting the magic parameter __TESTING__ to True. In this testing mode special hooks will
    # be executed that modify the experiment parameters in a way that results in a minimal runtime of the experiment
    # which only serves the purpose of testing if all the code actually runs without exceptions.

    # 27.10.23 - this method is a decorator which can be used to define the special testing hooks. Within these
    # testing hook implementations we implement the parameter changes that are applied to the model if
    def testing(self, func: t.Callable) -> t.Callable:
        """
        This method can be used as a decorator for a function within an experiment module. The decorated function will then
        be subsequently used as the implementation of how to put the experiment itself into testing mode. So when the experiment
        is actually put into testing mode via __TESTING__, that code will be executed to modify the parameters and whatever
        else is required for it.

        :returns: None
        """
        # We dont need to check anything here because by design the testing implementation should always be overriding.
        # In each highest instance in the hierarchy of sub experiments should it be possible to define distinct
        # testing behavior that is not implicitly modified or dependent on the lower levels.
        self.hook_map["__TESTING__"] = func

        # This requires a bit more explanation because it gets a bit convoluted here. We actually immediately *try* to
        # execute the testing immediately after adding the function at the point where the decoration happens.
        # We need this because of the way that the testing function will most likely be defined in BASE experiment
        # modules - that is INSIDE the experiment function. At that point the experiment has already started and
        # if we dont execute it right then, there's no idiomatic way to do so at a later point.
        # Although this isn't a big problem because this function will actually check various conditions to make sure
        # that we are not actually executing the testing function for example when defining the testing hook in a child
        # experiment or when merely importing an experiment from another file.
        self.apply_testing_if_possible()

        return func

    def apply_testing_if_possible(self):
        """
        This will execute the function which has been provided to the experiment as an implementation of the testing
        function, IF a certain set of conditions is satisfied.

        These are the conditions under which the testing code will be executed:

        - The experiment is actually configured to run in testing mode by the magic parameter __TESTING__
        - The experiment has been provided with a function that can be executed for the testing mode
        - The experiment is actually currently being executed as indicated by the is_running flag
        - The experiment is not already in testing mode

        :returns: None
        """
        # "applying" the test mode means to actually execute the function that is currently saved as the "testing"
        # hook. However, we only actually execute that in case a very specific set of conditions is met:
        # - the experiment needs to be already running.
        # - the testing hasn't been applied before
        # - the experiment is not currently in it's loaded form
        # - there actually exists a test to be executed

        # First and most important criterium: Is the experiment even configured to testing mode?
        # This is indicated with the magic parameter __TESTING__
        if "__TESTING__" not in self.parameters or not self.parameters["__TESTING__"]:
            return

        # Is there actually a test hook impementation that could be executed?
        # This is implemented as the special __TESTING__ name for a hook
        if "__TESTING__" not in self.hook_map:
            return

        # Also if the experiment is not actually in execution mode we are not running the test either
        if not self.is_running:
            return

        # And finally, if the testing has already been applied then we also dont't do it
        if self.is_testing:
            return

        # Only after all these conditions have been checked do we actually execute the testing hook
        # implementation here.
        self.apply_hook("before_testing")
        func = self.hook_map["__TESTING__"]
        func(self)

        self.is_testing = True

    # ~ Posthoc Analysis functionality

    def analysis(self, func, *args, **kwargs):
        self.analyses.append(func)

    def execute_analyses(self):
        for func in self.analyses:
            func(self)

    def get_analysis_code_map(self) -> dict[str, str]:
        map = {}
        for func in self.analyses:
            name = f"{func.__module__}.{func.__name__}"
            map[name] = inspect.getsource(func)

        return map

    # ~ Experiment Execution

    def initialize(self) -> None:
        """
        This method handles all the initial preparations that are needed to set up the
        experiment before any of the custom code can be implemented. This for example
        includes the creation of the archive folder, the initilization of the Logger
        instance and the copying of the original code into the archive folder. The method
        will also set up all the necessary metadata such as the start time of the experiment.

        :returns: None
        """
        # ~ creating archive
        self.prepare_path()

        # ~ creating the log file
        file_handler = logging.FileHandler(self.log_path)
        file_handler.setFormatter(self.log_formatter_file)
        self.logger.addHandler(file_handler)

        # ~ creating the track path
        self.track_path = os.path.join(self.path, ".track")
        os.mkdir(self.track_path)

        # ~ copying all the code into the archive
        self.save_dependencies()
        self.save_code()

        # ~ updating the metadata
        self.metadata["status"] = "running"
        self.metadata["start_time"] = time.time()
        self.metadata["duration"] = 0
        self.metadata["description"] = self.glob["__doc__"]
        self.save_metadata()

        # ~ creating the analysis module
        self.save_analysis()

        # ~ logging the start conditions
        start_panel = self._create_experiment_start_panel()
        # Render the panel to string for proper console and log file display
        console = Console(file=None, width=self.console_width)
        with console.capture() as capture:
            console.print(start_panel)
        self.log_lines(capture.get().split('\n'))

    def finalize(self) -> None:
        """
        This method is called at the very end of the experiment.
        This method will for example save the final experiment metadata and main experiment
        object storage to the corresponding JSON files in the archive folder. It will print
        the final log messages and system notification to inform the user about the end of
        the experiment.
        """
        # ~ updating the metadata
        self.metadata["end_time"] = time.time()
        self.metadata["duration"] = (
            self.metadata["end_time"] - self.metadata["start_time"]
        )
        self.metadata["status"] = "done"

        # ~ saving all the data
        self.save_metadata()
        self.save_data()

        # ~ handling a possible exception during the experiment
        if self.error:
            template = TEMPLATE_ENV.get_template("functional_experiment_error.out.j2")
            self.log_lines(template.render({"experiment": self}).split("\n"))

        # ~ logging the end conditions
        end_panel = self._create_experiment_end_panel()
        # Render the panel to string for proper console and log file display
        console = Console(file=None, width=self.console_width)
        with console.capture() as capture:
            console.print(end_panel)
        self.log_lines(capture.get().split('\n'))

        # ~ potentially packaging reproducible information
        # The "finalize_reproducible" method wraps all the functionality to package the reproduction information
        # into the experiment archive folder.
        if self.parameters["__REPRODUCIBLE__"]:
            self.finalize_reproducible()

    def finalize_reproducible(self) -> None:
        """
        This method is called at the very end of the experiment - only if the experiment is terminated in
        reproducible mode. This method will create all the assets that will be required for a experiment
        reproduction later on.

        This includes a snapshot of the dependencies and the source code of the editable dependencies.

        :returns: None
        """
        self.log(Text("...packaging for reproducibility", style="bright_black"))

        # ~ saving the dependencies
        # One part of the reproducibility is the to gather a snapshot of the exact dependencies and versions
        # that are active in the current python runtime environment. This is done by saving the dependencies
        # into a json file in the experiment archive folder.
        self.log("...exporting dependencies")
        dependencies: dict[str, dict] = get_dependencies()
        self.commit_json(self.DEPENDENCIES_FILE_NAME, dependencies)

        # ~ exporting source code
        # Besides all the dependencies that can be installed via the source code of the experiment, there is
        # the *current* state of the package that contains the experiment itself which most likely isn't connected
        # to specific package version.
        # So for that package we will actually use UV to build a tarball and then save that into the archive
        # as well so that it can later be installed from that tarball.
        uv_bin = find_uv_bin()

        path = os.path.join(self.path, ".sources")
        os.mkdir(path)

        self.log("...export editable installs")
        with tempfile.TemporaryDirectory() as temp_path:

            for name, info in dependencies.items():
                if info["editable"]:
                    self.log(f' - source "{name}" @ {info["path"]}')
                    subprocess.run(
                        [
                            uv_bin,
                            "build",
                            info["path"],
                            "--sdist",
                            "--out-dir",
                            temp_path,
                        ]
                    )

            # Now that we have created all the tarballs in the temporary directory, we can now move them into
            # the experiment archive folder.
            for file in os.listdir(temp_path):
                if file.endswith(".tar.gz"):
                    shutil.move(os.path.join(temp_path, file), os.path.join(path, file))

        # There might be some additional operations that need to be performed for specific experiment parameters.
        # These additional actions are implemented in the "on_reproducible" method for those parameters that are
        # annotated by a specific subclass of ActionableParameterType.
        self.log("...post-processing parameters")
        for parameter, info in self.metadata["parameters"].items():
            if isinstance(info["type"], ActionableParameterType):
                self.parameters[parameter]["type"].on_reproducible(
                    experiment=self, value=self.parameters[parameter]["value"]
                )

    def execute(self) -> None:
        """
        This method actually executes ALL of the necessary functionality of the experiment.
        This inludes the initialization of the experiment, the execution of the custom experiment
        implementation and the finalization of the experiment artifacts.

        :returns: None
        """
        self.initialize()

        self.config.pm.apply_hook(
            "after_experiment_initialize",
            experiment=self,
        )

        try:
            # This flag will be used at various other places to check whether a given experiment object is
            # currently actually in the process of executing or whether it is rather a
            self.is_running = True
            # Right before we actually start the main execution code of the
            self.apply_testing_if_possible()

            # 27.10.23 - Added the "before_execute" and the "after_execute" hook because they might be useful
            # in the future.
            self.apply_hook("before_run")

            self.func(
                self
            )  # This is where the actual user defined experiment code gets executed!

            self.apply_hook("after_run")

        except Exception as error:
            self.error = error
            self.tb = traceback.format_exc()

        self.finalize()

        self.config.pm.apply_hook(
            "after_experiment_finalize",
            experiment=self,
        )

        # 25.06.25
        # Previously it was a source of a lot of confusion for other people using the library that the
        # actual error was only logged and then the error which would actually stop the program would
        # occurr somewhere in the analysis part.
        # Additionally, its not really possible to use the debugger to debug an experiment file if the
        # primary error is only silently logged. Therefore, we actually raise the original error here
        # at the end - after we've done all of the cleanup.
        if self.error:

            self.config.pm.apply_hook(
                "before_experiment_error",
                experiment=self,
                error=self.error,
                traceback=self.tb,
            )

            raise self.error.with_traceback(self.error.__traceback__)

    def __call__(self, func, *args, **kwargs):
        self.func = func

        return self

    def set_main(self) -> None:
        """
        Will modify the internal dictionary in such a way that after this method was called,
        "is_main" will evaluate as True.

        :returns: None
        """
        self.glob["__name__"] = "__main__"

    def is_main(self) -> bool:
        """
        Returns True only if the current global context is "__main__" which is only the case if the python
        module is directly being executed rather than being imported for example.

        :returns: bool
        """
        return self.glob["__name__"] == "__main__"

    def run_if_main(self):
        """
        This method will actually execute the main implementation of the experiment, but only if the current
        global context is the __main__ context. That is only true if the corresponding python module is actually
        being executed rather than imported.

        This is the method that any experiment method should be using at the very end of the module. A user should
        NOT use execute() directly, as that would issue the experiment to be executed in the case of an import as well!

        .. code-block:: python

            # Define the experiment...

            # At the end of the experiment module
            experiment.run_if_main()

        :returns: None
        """
        if self.is_main():

            # 06.09.24: The parse method will optionall update / overwrite the self.parameters dictionary with
            # all of the arguments that were passed to the experiment through the command line. This is a very
            # important step because it allows the user to overwrite the default parameters of the experiment
            # with command line arguments.
            self.arg_parser.parse()
            # It is possible that some special parameters have been overwritten through the command line arguments
            # so we need to call this method to make sure that those changes are actually applied.
            self.update_parameters_special()

            self.execute()
            self.execute_analyses()

    def run(self):
        """
        unlike, the method "run_if_main", this method will actually execute the experiment no matter what. At the point
        at which this method is called, the experiment will be executed
        """
        self.execute()
        self.execute_analyses()

    # ~ Archive management

    def check_path(self) -> None:
        if not self.path:
            raise ValueError(
                "Attempting to access a specific path of archive, but not archive path exists "
                "yet! Please make sure an experiment is either loaded or properly initialized "
                "first before attempting to access any specific archive element."
            )

    @property
    def metadata_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), self.METADATA_FILE_NAME)

    @property
    def data_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), self.DATA_FILE_NAME)

    @property
    def code_path(self) -> str:
        self.check_path()
        # 04.07.2023 - This is one of those super weird bugs. Previously the path of the code file was just
        # "code.py", but this naming has actually resulted in a bug - namely that it was not possible to
        # use tensorflow any longer from either within that code file or the analysis file within an experiment
        # archive folder. This is because tensorflow is doing some very weird dynamic shenanigans where at some
        # point they execute the line "import code" which then referenced to our python module causing a
        # circular import and thus an error!
        return os.path.join(str(self.path), self.CODE_FILE_NAME)

    @property
    def log_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), "experiment_out.log")

    @property
    def error_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), "experiment_error.log")

    @property
    def analysis_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), "analysis.py")

    def prepare_path(self):
        """
        This method will for one thing create the actual path to the archive folder of the current expriment. This
        means that it will combine the information about the base path, the namespace and the name of the experiment
        to create the actual absolute path at which the archive folder should exist.

        Additionally, this method will also CREATE that folder (hierarchy) if it does not already exist. So potentially
        this method will actually create multiple nested folders on the system.

        :returns: None
        """
        # One thing which we will need to assume as given here is that the given base_path exists!
        # The rest of the nested sub structure we can create if need be, but the base path has to exist in
        # the first place as a starting point
        if not os.path.exists(self.base_path):
            raise NotADirectoryError(
                f'The given base path "{self.base_path}" for the experiment archive '
                f"does not exist! Please make sure the path points to a valid folder."
            )

        if not os.path.isdir(self.base_path):
            raise NotADirectoryError(
                f'The given experiment base path "{self.base_path}" is not a '
                f"directory! Please make sure the file points to a valid folder."
            )

        # Then we can iterate through all the components of the namespace and recursively create those
        # directories if they not already exist.
        namespace_list = self.namespace.split("/")
        current_path = self.base_path
        for name in namespace_list:
            current_path = os.path.join(current_path, name)
            if not os.path.exists(current_path):
                os.mkdir(current_path)

        # 08.11.23
        # Now at this point we can be sure that the base path exists and we can create the specific
        # archive folder.
        # How this archive folder will be called depends on some conditions.
        # - Most importantly, if the experiment was given an actual name (self.name != None) then
        #   we want to use that name, otherwise the name will be auto generated
        # - The next best option would be if the experiment is in debug mode, we will call the
        #   resulting folder "debug"
        # - In the last case we generate a name from the current datetime combined with a random
        #   string to make it unique.

        if self.debug:
            self.name = "debug"

        elif self.name is None:
            # This method will format the full name of the experiment which includes not only the
            # name of the experiment but also the date and time information about the starting
            # time.
            self.name = self.format_full_name()

            if "__PREFIX__" in self.parameters and self.parameters["__PREFIX__"]:
                prefix = self.parameters["__PREFIX__"]
                self.name = f"{prefix}__{self.name}"

        # Now that we have decided on the name we can assemble the full path
        self.path = os.path.join(current_path, self.name)

        # If the experiment is in "debug" mode that means that we actually want to get rid of the previous
        # archive folder with the same name, it one exists
        if self.debug and os.path.exists(self.path):
            shutil.rmtree(self.path)

        # And then finally in any case we create a new and clean folder
        os.mkdir(self.path)

    def format_full_name(
        self, date_time: datetime.datetime = datetime.datetime.now()
    ) -> str:
        """
        Given a datetime object ``data_time``, this function will format the "full" experiment name
        which does not only include the name of the experiment but also the time and date specificied
        by the datetime as well as a random ID string.

        This full name is therefore guaranteed to be unique for each experiment execution.

        :param date_time: the datetime object which specifies the time and date that should be included
            in the experiment name. Default is now()

        :returns: the string name
        """
        date_string = date_time.strftime("%d_%m_%Y")
        time_string = date_time.strftime("%H_%M")
        id_string = random_string(length=4)
        name = self.name_format.format(
            date=date_string,
            time=time_string,
            id=id_string,
        )
        return name

    def save_metadata(self) -> None:
        """
        This method will store the metadata of the experiment object into a JSON file in the archive folder.
        The method will overwrite any potentially existing file with the same name with the current metadata.

        :returns: None
        """
        # 07.11.24
        # It is actually quite useful to also store the information about the parameter value and not just the
        # type and the description, which is why we are actually adding this information to the metadata here
        # before saving it.
        # The only thing we have to be wary of here is that parameters don't necessary need to be JSON encodable
        # types. So for all values that are not json encodable we will simply convert them to their string
        # representation.
        for parameter, value in self.parameters.items():
            try:
                json.dumps(value)  # Check if value is JSON encodable
                self.metadata["parameters"][parameter]["value"] = value
                # We add the additional usable flag here to indicate whether or not a parameter has actually been
                # exported to a JSON format correctly in such a way that it could be reused later on.
                self.metadata["parameters"][parameter]["usable"] = True
            except (TypeError, OverflowError):
                self.metadata["parameters"][parameter]["value"] = str(value)
                self.metadata["parameters"][parameter]["usable"] = False

        # Then we can save it with human readable formatting
        with open(self.metadata_path, mode="w") as file:
            content = json.dumps(self.metadata, indent=4, sort_keys=True)
            file.write(content)

    def save_data(self) -> None:
        """
        Saves the internal ``self.data`` dictionary with all the experiment data into a JSON file in the
        experiment data folder, the name of which is determined by ``self.data_path`` and which
        normally is "experiment_data.json".

        note: Items of the data dictionary which start with an underscore will NOT be saved into this file.
            Those entries can be used to exchange data between different hooks only within the same experiment
            runtime!

        :returns: None
        """

        with open(self.data_path, mode="w") as file:

            # 16.02.25 - This is the filtered data which does not contian the internal data that starts with
            # an underscore.
            data = {
                key: value
                for key, value in self.data.items()
                if not key.startswith("_")
            }

            content = json.dumps(data, cls=CustomJsonEncoder)
            file.write(content)

    def save_code(self) -> None:
        source_path = self.glob["__file__"]
        destination_path = self.code_path
        shutil.copy(source_path, destination_path)

    def save_dependencies(self) -> None:
        for path in self.dependencies:
            file_name = os.path.basename(path)
            destination_path = os.path.join(self.path, file_name)
            shutil.copy(path, destination_path)

    def save_analysis(self) -> None:
        with open(self.analysis_path, mode="w") as file:
            template = TEMPLATE_ENV.get_template("functional_analysis.py.j2")
            content = template.render({"experiment": self})
            file.write(content)

    # ~ Internal data storage

    def __getitem__(self, key):
        """
        This class implements custom behavior when using an index assignment operation. Only string keys
        are supported, but these strings may describe nested structures by using the "/" character, as one
        would do to define a nested folder structure.

        As an example consider the two equivalent ways of retrieving a value stored within an experiments
        data store (assuming the value exists):

        .. code-block:: python

            with (e := Experiment('/tmp', 'name', globals()):
                # ... adding data
                value = e.data['metrics']['mse']['10']
                value = e['metrics/mse/10']

        :returns: The value from the data store
        """
        keys = key.split("/")
        current = self.data
        for key in keys:
            if key in current:
                current = current[key]
            else:
                raise KeyError(
                    f'The namespace "{key}" does not exist within the experiment data storage'
                )

        return current

    def __setitem__(self, key, value):
        """
        This class implements custom behavior when using an index assignment operation. Only string keys
        are supported, but these strings may describe nested structures by using the "/" character, as one
        would do to define a nested folder structure. If the specified nested location does not already
        exist within the internal data dict structure, it will be *automatically* created.

        .. code-block:: python

            with (e := Experiment('/tmp', 'name', globals()):
                # This will be saved into e.data['metrics']['repetitions']['10']['metric']
                # and if that nesting does not exist like this it will be created automatically, no matter
                # how many of the intermediate steps are missing!
                e['metrics/repetitions/10/metric'] = 10.23

        :returns: None
        """
        if not isinstance(key, str):
            raise ValueError(
                "You are attempting to add to the internal experiment storage, by using a non "
                "string key. This is not possible! Please use a valid query string to identify "
                "the (nested) location where to save the value within the storage structure."
            )

        # ~ Decoding the nesting and potentially creating it along the way if it does not exist
        keys = key.split("/")
        current = self.data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}

            current = current[key]

        # 28.11.2022
        # At this point we were previously performing a value processing. For example if the value to be
        # saved was a numpy array it was converted into a list. This was done to prevent an exception to
        # arise from numpy arrays which are not naturally serializable.
        # - I realized that this should be addressed by a custom JsonEncoder because there are other ways
        #   for a numpy array to accidentally enter the experiment storage which are not caught here
        # - This causes unwanted implicit behaviour, where the user for example thinks he has saved a numpy
        #   array into the experiment storage & wants to retrieve it as such again during the same runtime.

        current[keys[-1]] = value

    def __getattr__(self, item: str) -> Any:
        """
        This magic method implements the behavior whenever an attribute of the experiment object is accessed. This
        is usually done with the dot notation, for example "experiment.attribute". The method will return the
        value of the attribute with the given name ``item``.

        This method implements custom behavior when an attribute with an upper case name (e.g. PARAMETER) is accessed.
        In that case, the method will not actually return a direct attribute of the experiment object, but will rather
        check if a parameter with the given name exists in the self.parameters dictionary. If it does, the value of that
        parameter is returned.

        :param item: The name of the attribute that should be accessed

        :returns: any
        """

        if item.isupper():

            if item not in self.parameters:
                raise KeyError(
                    f'There exists no experiment parameter with the name "{item}"!'
                )

            # In the special case that the given parameter has been annotated with the ActionableParameterType, we
            # want to use the get() method to retrieve the value of the parameter instead.
            if (
                item in self.metadata["parameters"]
                and "type" in self.metadata["parameters"][item]
                and isinstance(
                    self.metadata["parameters"][item]["type"], ActionableParameterType
                )
            ):

                self.metadata["parameters"][item]["type"].get(
                    experiment=self,
                    value=self.parameters[item],
                )

            # Otherwise we just return the value that is stored in the parameters dictionary
            return self.parameters[item]
        else:
            return super(Experiment, self).__getattr__(item)

    def __setattr__(self, key: str, value: Any) -> None:
        """
        This magic method implements the behavior whenever an attribute of the experiment object is set. This is
        usually done with the dot notation, for example "experiment.attribute = 10". The method will set the value
        of the attribute with the given name ``key`` to the given value ``value``.

        This method implements custom behavior when an attribute with an upper case name (e.g. PARAMETER) is set.
        In that case, the method will not actually set a direct attribute of the experiment object, but will rather
        add the given key value combination as a new entry to the self.parameters dictionary.

        :param key: The name of the attribute that should be set
        :param value: The value that should be set

        :returns: None
        """
        if key.isupper():

            # In the special case that the given parameter has been annotated with the ActionableParameterType, we
            # want to use the set() method to overwrite the value of the parameter.
            if (
                key in self.metadata["parameters"]
                and "type" in self.metadata["parameters"][key]
                and isinstance(
                    self.metadata["parameters"][key]["type"], ActionableParameterType
                )
            ):

                value = self.metadata["parameters"][key]["type"].set(
                    experiment=self,
                    value=value,
                )

            self.parameters[key] = value
            self.glob[key] = value

            # 07.11.24
            # We also want to store the value of the parameter in the parameter metadata directory because
            # we now also want that value to be exported to the metadata file as well!
            if key in self.metadata["parameters"]:
                self.metadata["parameters"][key]["value"] = value

            # Apply special parameter side effects (e.g., updating cache enabled state)
            self.update_parameters_special()

        else:
            super(Experiment, self).__setattr__(key, value)

    # ~ File Handling Utility

    def open(self, file_name: str, *args, **kwargs):
        """
        This is an alternative file context for the default python ``open`` implementation.
        """
        path = os.path.join(self.path, file_name)
        return open(path, *args, **kwargs)

    def commit_fig(
        self,
        file_name: str,
        fig: t.Any,
    ) -> None:
        """
        Given the name ``file_name`` for a file and matplotlib Figure instance, this method will save the
        figure into a new image file in the archive folder.

        :returns: None
        """
        path = os.path.join(self.path, file_name)
        fig.savefig(path)

        self.config.pm.apply_hook(
            "experiment_commit_fig",
            experiment=self,
            name=file_name,
            figure=fig,
        )

    def commit_json(
        self,
        file_name: str,
        data: dict | list,
        encoder_cls=CustomJsonEncoder,
    ) -> None:
        """
        Given the name ``file_name`` for a file and some json encodable data structure ``data``, this method
        will write that data into a new JSON file in the archive folder.

        :param file_name: The name that the file should have, including the .json extension.
        :param data: Either a dict or list which can be json encoded, meaning no custom data structures
        :param encoder_cls: A Json EncoderClass when custom objects need to be encoded. Default is the
            pycomex.CustomJsonEncoder, which is able to encode numpy data by default.

        :returns: None
        """
        path = os.path.join(self.path, file_name)
        with open(path, mode="w") as file:
            content = json.dumps(data, cls=encoder_cls)
            file.write(content)

        self.config.pm.apply_hook(
            "experiment_commit_json",
            experiment=self,
            name=file_name,
            data=data,
            content=content,
        )

    def commit_raw(self, file_name: str, content: str) -> None:
        """
        Given the name ``file_name`` for a file and the string ``content``, this method will save the
        string content into a new file of that name within the experiment archive folder.

        :param file_name: The name that the file should have, including the file extension
        :param content: The string content to write into the text file

        :returns: void
        """
        file_path = os.path.join(self.path, file_name)
        with open(file_path, mode="w") as file:
            file.write(content)

        self.config.pm.apply_hook(
            "experiment_commit_raw",
            experiment=self,
            name=file_name,
            content=content,
        )

    def track(self, name: str, value: float | plt.Figure) -> None:
        """
        This method can be used to track a specific value within the experiment object. This is useful for example
        to keep track of the current state of a model during training or to save the results of a specific
        computation.

        When tracking a quantity to a specific name, each new value will be added to the experiment data storage
        using the name as the corresponding key in the storage.
        Additionally, the tracked name will be addded to the metadata '__track__' list which will provide an
        overview of all the tracked quantities in the experiment.

        **Tracking Figures**
        It is also possible to track figures / images by providing either the Figure object or the absolute string
        path to an image as the corresponding value. In this case, the figure will be saved into a special folder in
        the experiment archive folder and the list will hold the relative paths towards these files.

        :param name: The name under which the value should be saved
        :param value: The value to be saved

        :returns: None
        """
        if name not in self.data:
            self[name] = []
            self.metadata["__track__"].append(name)

        if isinstance(value, plt.Figure):
            index = len(self[name]) + 1
            rel_path = os.path.join(".track", f"{name}_{index:03d}.png")
            image_path = os.path.join(self.path, rel_path)
            value.savefig(image_path)

            self[name].append(rel_path)

        elif isinstance(value, (float, int)):
            self[name].append(value)

        self.config.pm.apply_hook(
            "experiment_track",
            experiment=self,
            name=name,
            value=value,
        )

    def track_many(self, data: dict[str, float]) -> None:
        """
        This method can be used to track multiple values at once. The data should be a dictionary where the keys
        are the names under which the values should be saved and the values are the values to be saved.

        :param data: A dictionary where the keys are the names and the values are the values to be saved

        :returns: None
        """
        for key, value in data.items():
            self.track(key, value)

    # ~ Alternate constructors

    @classmethod
    def import_from(
        cls,
        experiment_path: str,
        glob: dict,
    ):
        """
        Given the ``experiment_path``, which is either a relative name of the experiment module or an absolute path,
        this method will dynamically import that experiment module and return the Experiment object that is defined
        in it - without executing the experiment.

        ..code-block:: python

            experiment = Experiment.import_from('experiment.py', globals())

            # Force the experiment to run - for example as part of a parameter sweep
            experiment.run()

        :param experiment_path: The relative or absolute path to the experiment module
        :param glob: The globals() dictionary

        :returns: The Experiment object from the imported module
        """

        # 28.04.23 - this fixes a bug, where the relative import would only work the current working
        # directory is exactly the folder that also contains. Previously if the working directory was
        # a different one, it would not work.
        try:
            module = dynamic_import(experiment_path)
        except (FileNotFoundError, ImportError):
            parent_path = os.path.dirname(glob["__file__"])
            experiment_path = os.path.join(parent_path, *os.path.split(experiment_path))
            module = dynamic_import(experiment_path)

        # 28.04.23 - before this was implemented over a hardcoded variable name for an experiment, but
        # strictly speaking we can't assume that the experiment instance will always be called the same
        # this is just a soft suggestion.
        experiment = None
        for key in dir(module):
            value = getattr(module, key)
            if isinstance(value, Experiment):
                experiment = value

        assert (
            experiment is not None
        ), f'No object of the type "Experiment" could be found in the given module @ {experiment_path}'

        return experiment

    @classmethod
    def extend(
        cls, experiment_path: str, base_path: str, namespace: str, glob: dict
    ) -> "Experiment":
        """
        This method can be used to extend an experiment through experiment inheritance by providing the
        path ``experiment_path`` to the base experiment module. It will return the ``Experiment`` instance
        which can subsequently be extended by defining hook implementations and modifying parameters.

        ..code-block: python

            experiment = Experiment.extend(
                experiment_path='base_experiment.py',
                base_path=os.getcwd(),
                namespace='results/sub_experiment',
                glob=globals(),
            )

            experiment.PARAMETER = 2 * experiment.PARAMETER

            experiment.hook('hook')
            def hook(e):
                e.log('hook implementation')

        :param experiment_path: Either a relative or an absolute path to the python module which contains
            the base experiment code to be extended.
        :param base_path: An absolute path to the folder to act as the base path for the archive structure
        :param namespace: A namespace string that defines the archive structure of the experiment
        :param glob: The globals() dictionary

        :returns: Experiment instance
        """
        # First of all we need to import that module to access the Experiment instance that is
        # defined there. That is the experiment which we need to extend.
        # This method will import the experiment object dynamically from the given experiment path and then
        # return that object.
        experiment: Experiment = cls.import_from(experiment_path, glob=glob)

        # Then we need to push the path of that file to the dependencies.
        experiment.dependencies.append(experiment.glob["__file__"])

        # Finally we need to replace all the archive-specific parameters like the base path
        # and the namespace
        experiment.base_path = base_path
        experiment.namespace = namespace
        # The globals we merely want to update and not replace since we probably won't define
        # all of the parameters new in the sub experiment module.
        # TODO: nested updates!
        experiment.glob.update(glob)
        experiment.update_parameters()

        # 30.10.23 - This method will read all the metadata from the thingy
        experiment.read_module_metadata()

        # 25.09.24 - This method will update the argument parser with the new parameters
        # that have potentially been added in the sub experiment module which have not existed
        # in the base experiment.
        experiment.update_arg_parser()

        # This line is necessary so that the experiments can be discovered by the CLI
        glob["__experiment__"] = experiment

        return experiment

    @classmethod
    def from_config(cls, config_path: str, **kwargs) -> "Experiment":

        with open(config_path) as file:
            config_data = yaml.load(file, Loader=yaml.FullLoader)

        experiment_config = ExperimentConfig(path=config_path, **config_data)
        glob = {
            "__file__": config_path,
            **experiment_config.parameters,
        }

        return cls.extend(
            experiment_path=experiment_config.extend,
            base_path=experiment_config.base_path,
            namespace=experiment_config.namespace,
            glob=glob,
        )

    @classmethod
    def is_archive(cls, path: str) -> bool:
        """
        Returns whether or not a given absolute ``path`` represents a valid experiment archive folder or
        not.

        :param path: The absolute string path in question to be checked.

        :returns: bool
        """
        if not os.path.isdir(path):
            return False

        metadata_file_path = os.path.join(path, cls.METADATA_FILE_NAME)
        if not os.path.exists(metadata_file_path):
            return False

        # Finally we can load the information inside the metadata file and check if it is valid or not.
        # Part of this will also be checking if the experiment is actually done with the execution or not.
        # If the experiment is still executing, then we determine it technically not an archive yet.
        metadata: dict = cls.load_metadata(path)
        return metadata["status"] == "done"

    @classmethod
    def load_metadata(cls, path: str) -> dict:
        """
        Given the absolute string ``path`` to a valid experiment archive folder, this method will load only the
        metadata of this archived experiment from the metadata json file. This can be useful in scenarios where
        only the metadata is required and loading the entire information with the "load" function would be
        unnecessary.

        :param path: The absolute string path to the experiment archive folder.

        :returns: The metadata dict of the archived experiment
        """
        metadata_file_path = os.path.join(path, cls.METADATA_FILE_NAME)
        with open(metadata_file_path) as file:
            content = file.read()
            metadata = json.loads(content)
            return metadata

    @classmethod
    def load(cls, path: str):
        """
        This method can be used to load a previously executed experiment back into memory from an existing
        archive folder ``path``. This will return the Experiment instance which can be used to access the
        data and metadata of the experiment at the state in which the experiment ultimately terminated.

        :param path: The absolute path to the experiment archive folder.

        :returns: Experiment instance
        """
        # We need the path to the actual code file here to properly import that module. So only if the
        # path that we get is a file we interpret it as the code file, otherwise we assume that it is
        # the path to the archive folder and we need to append the code file name to it.
        if os.path.isfile(path):
            module = dynamic_import(path)
        else:
            path = os.path.join(path, cls.CODE_FILE_NAME)
            module = dynamic_import(path)

        # 28.04.23 - before this was implemented over a hardcoded variable name for an experiment, but
        # strictly speaking we can't assume that the experiment instance will always be called the same
        # this is just a soft suggestion.
        experiment = None
        for key in dir(module):
            value = getattr(module, key)
            if isinstance(value, Experiment):
                experiment = value

        folder_path = os.path.dirname(path)
        experiment.path = folder_path

        with open(experiment.metadata_path) as file:
            content = file.read()
            experiment.metadata = json.loads(content)

            for parameter, info in experiment.metadata["parameters"].items():

                if (
                    "value" in info
                    and isinstance(info["value"], str)
                    and ("<" in info["value"] and ">" in info["value"])
                ):
                    continue

                if "value" in info:
                    experiment.parameters[parameter] = info["value"]

        with open(experiment.data_path) as file:
            content = file.read()
            experiment.data = json.loads(content)

        return experiment


def find_experiment_in_module(module: t.Any) -> Experiment:
    """
    Given an imported module object, this function will return the *first* experiment object that is encountered to be
    known to the global scope of the given module.

    :returns: An Experiment object
    """
    if "__experiment__" in dir(module):
        experiment = module.__experiment__
        return experiment
    else:
        raise ModuleNotFoundError(
            f"You are attempting to get the experiment from the module {module.__name__}. "
            f"However, it seems like there is no Experiment object defined in that module!"
        )


def get_experiment(path: str) -> None:

    module = dynamic_import(path)
    experiment = find_experiment_in_module(module)
    return experiment


def run_experiment(path: str) -> None:
    """
    This function runs an experiment given the absolute path to the experiment module.

    :param path: The absolute string path to a valid experiment python module

    :returns: None
    """
    # This is a handy utilitiy function which just generically imports a python module given its absolute path in
    # the file system.
    module = dynamic_import(path)

    # This function will actually return the (first) Experiment object instance that is encountered to be defined
    # within the given module object.
    # It will raise an error if there is none.
    experiment = find_experiment_in_module(module)

    with SetArguments([sys.argv[0]]):
        # And now finally we can just execute that experiment.
        experiment.set_main()
        experiment.run_if_main()

    return experiment
