"""
Utility methods
"""

import datetime
import importlib.util
import json
import logging
import os
import pathlib
import platform
import random
import re
import string
import subprocess
import sys
import textwrap
import tokenize
import traceback
import typing as t
from collections.abc import Callable
from importlib.metadata import distributions
from inspect import getframeinfo, stack
from pathlib import Path
from typing import Dict, List, Optional

import jinja2 as j2
import numpy as np
import pkg_resources
from prettytable import PrettyTable

# The modern "importlib.metadata" module is only available in Python 3.8 and later.
# to ensure backwards compatibility with Python 3.7 and earlier, we use the backport / previous
# version of this module, which is "importlib_metadata", if necessary
if sys.version_info >= (3, 8):
    from importlib.metadata import distributions
else:
    from importlib_metadata import distributions  # backport

# Contains a human readable string of the operating system name, e.g. "Linux" or "Windows"
OS_NAME: str = platform.system()
# Contains the absolute string path to the parent directory of this file
PATH = pathlib.Path(__file__).parent.absolute()
VERSION_PATH = os.path.join(PATH, "VERSION")
TEMPLATE_PATH = os.path.join(PATH, "templates")
EXAMPLES_PATH = os.path.join(PATH, "examples")
PLUGINS_PATH = os.path.join(PATH, "plugins")

TEMPLATE_ENV = j2.Environment(
    loader=j2.FileSystemLoader(TEMPLATE_PATH), autoescape=j2.select_autoescape()
)
TEMPLATE_ENV.globals.update(
    {
        "os": os,
        "datetime": datetime,
        "len": len,
        "int": int,
        "type": type,
        "sorted": sorted,
        "modulo": lambda a, b: a % b,
        "key_sort": lambda k, v: k,
        "wrap": textwrap.wrap,
    }
)

NULL_LOGGER = logging.Logger("NULL")
NULL_LOGGER.addHandler(logging.NullHandler())


class CustomJsonEncoder(json.encoder.JSONEncoder):
    """
    custom json encoder class which is used when encoding the experiment data into a persistent json file.

    This specific class implements the serialization of numpy arrays for example which makes it possible
    to commit numpy arrays to the experiment storage without causing an exception.
    """

    def default(self, value):

        if isinstance(value, np.ndarray):
            return value.tolist()
        elif isinstance(value, np.generic):
            return value.data

        return super().default(value)


class AnsiSanitizingFormatter(logging.Formatter):
    """
    Custom logging formatter that removes ANSI escape codes from log messages.

    This formatter is designed to be used with file handlers to ensure that
    log files contain clean text without ANSI color codes and formatting,
    while preserving the original formatting for console output.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Regex pattern to match ANSI escape sequences
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def format(self, record):
        # Get the formatted message from the parent formatter
        formatted_message = super().format(record)
        # Remove ANSI escape codes
        return self.ansi_escape.sub('', formatted_message)


# == CUSTOM JINJA FILTERS ==


def dict_value_sort(
    data: dict,
    key: str | None = None,
    reverse: bool = False,
    k: int | None = None,
):

    def query_dict(current_dict: dict, query: str | None):
        if query is not None:
            keys = query.split("/")
            for current_key in keys:
                current_dict = current_dict[current_key]

        return current_dict

    items_sorted = sorted(
        data.items(), key=lambda t: query_dict(t[1], key), reverse=reverse
    )
    if k is not None:
        k = min(k, len(items_sorted))
        items_sorted = items_sorted[:k]

    return items_sorted


TEMPLATE_ENV.filters["dict_value_sort"] = dict_value_sort


def pretty_time(value: int) -> str:
    date_time = datetime.datetime.fromtimestamp(value)
    return date_time.strftime("%A, %B %d, %Y at %I:%M %p")


TEMPLATE_ENV.filters["pretty_time"] = pretty_time


def file_size(value: str, unit: str = "MB"):
    unit_factor_map = {
        "KB": 1 / (1024**1),
        "MB": 1 / (1024**2),
        "GB": 1 / (1024**3),
    }

    size_b = os.path.getsize(value)
    size = size_b * unit_factor_map[unit]
    return f"{size:.3f} {unit}"


TEMPLATE_ENV.filters["file_size"] = file_size


def get_version():
    with open(VERSION_PATH) as file:
        return file.read().replace(" ", "").replace("\n", "")


class SkipExecution(Exception):
    pass


class Skippable:

    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> bool:
        # We will simply ignore the SkipExecution exceptions completely
        if isinstance(exc_value, SkipExecution):
            return True
        else:
            return False


# https://stackoverflow.com/questions/24438976
class RecordCode:

    INDENT_SPACES = 4

    """
    This class can be used as a context manager to record code.

    **CHANGELOG**

    12.09.2022

    Previously this class worked like this: In the __enter__ method a frameinfo supplied the line number at
    which the context starts and then the same was done in __exit__ and with Python 3.8 this actually worked
    The two methods returned the correct line numbers. But as of Python 3.10, this no longer works because
    the __exit__ method now ALSO returns just the line number of where the context manager starts.

    But since we can still get the start line reliably, we just have to extract the code with some string
    processing now: With the starting line we know the indent of this context manager and can then record
    all the code which follows it in one level of indent deeper.

    13.02.2023

    Added a logger as optional argument for the constructor. Also now if an error occurs inside the context
    the actual complete stack trace will be printed to the stream of that logger.
    """

    def __init__(
        self,
        stack_index: int = 2,
        initial_stack_index: int = 1,
        skip: bool = False,
        logger: logging.Logger = NULL_LOGGER,
    ):
        self.stack_index = stack_index
        self.logger = logger

        # Getting the filename and actually the content of the file in the constructor already is an
        # improvement towards the previous version. Back then it was done in time when the enter method was
        # called, but the problem is if the file within the filesystem was changed in that time (which is
        # actually quite likely) then the data supplied by the frame info would be out of sync and the whole
        # process would fail.
        frame_info = getframeinfo(stack()[initial_stack_index][0])
        self.file_path = frame_info.filename
        print(self.file_path)
        with open(self.file_path) as file:
            self.file_lines = file.readlines()

        self.enter_line: int | None = None
        self.exit_line: int | None = None

        self.enter_indent: int = 0
        self.code_indent: int = 0

        self.code_lines: list[str] = []
        self.code_string: str = ""

        # This is a flag, that if set to True signals this context manager to skip the execution of the
        # entire content.
        self.skip = skip

        # Callbacks can externally be added to these lists to have functions be executed at either the enter
        # or the exit. The first arg is this object itself, the second is the enter / end line index number
        # respectively
        self.enter_callbacks: list[Callable[["RecordCode", int], None]] = []
        self.exit_callbacks: list[Callable[["RecordCode", int], None]] = []

    def get_frame_info(self):
        frame_info = getframeinfo(stack()[self.stack_index][0])
        return frame_info

    def __enter__(self):
        if self.skip:
            raise SkipExecution()

        frame_info = self.get_frame_info()
        self.enter_line = frame_info.lineno

        for cb in self.enter_callbacks:
            cb(self, self.enter_line)

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> bool:
        # 13.02.2022
        # This fixes a big annoyance, where an error inside a code record is almost unfixable
        # because it doesn't actually show the stack trace.
        # Now, if an exception occurred within the code record, that exception with it's entire
        # stack trace will be printed to the logger.
        if exc_type is not None:
            exception_lines = traceback.format_exception(
                exc_type, exc_value, exc_traceback
            )
            exception_string = "".join(exception_lines)
            self.logger.error(
                f"[!] ERROR occurred within a {self.__class__.__name__} context"
            )
            self.logger.error(exception_string)

        # First of all we have to find out the indentation of the line at which we enter
        enter_line = self.file_lines[self.enter_line - 1]
        self.enter_indent = len(enter_line) - len(enter_line.lstrip())

        # Then we know that all the code content is at one indent level deeper
        self.code_indent = self.enter_indent + self.INDENT_SPACES

        # And then we simply iterate all lines until either the file ends or we detect an ident level
        # on the same level or above as the enter level, at which point we know the context has been left
        for i in range(self.enter_line, len(self.file_lines)):
            line = self.file_lines[i]
            indent = len(line) - len(line.lstrip())
            if indent <= self.enter_indent:
                break

            self.code_lines.append(line[self.code_indent :])

        self.exit_line = i + 1

        # And now it just remains to put those lines into a string
        self.code_string = "\n".join(self.code_lines)

        for cb in self.exit_callbacks:
            cb(self, self.exit_line)

        return True


class Empty:
    pass


class Singleton(type):
    """
    This is metaclass definition, which implements the singleton pattern. The objective is that whatever
    class uses this as a metaclass does not work like a traditional class anymore, where upon calling the
    constructor a NEW instance is returned. This class overwrites the constructor behavior to return the
    same instance upon calling the constructor. This makes sure that always just a single instance
    exists in the runtime!

    **USAGE**
    To implement a class as a singleton it simply has to use this class as the metaclass.
    .. code-block:: python
        class MySingleton(metaclass=Singleton):
            def __init__(self):
                # The constructor still works the same, after all it needs to be called ONCE to create the
                # the first and only instance.
                pass
        # All of those actually return the same instance!
        a = MySingleton()
        b = MySingleton()
        c = MySingleton()
        print(a is b) # true
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def split_namespace(namespace: str) -> list[str]:
    """
    Given the namespace string of an experiment, this function will split that string into a list of
    individual path segments.

    :param str namespace: The string namespace definition for an experiment module
    :returns: A list containing the split, individual path segments
    """
    # TODO: We could extend this to raise errors if an invalid format is detected.

    if "/" in namespace:
        return namespace.split("/")
    # Technically we would discourage the usage of backslashes within the namespace specification, but there
    # is the real possibility that a deranged windows user tries this, so we might as well make it a feature
    # now already.
    elif "\\" in namespace:
        return namespace.split("\\")
    else:
        return [namespace]


def dynamic_import(path: str):
    """
    Given the absolute string ``path`` to a python module, this function will dynamically import that
    module and return the module object instance that represents that module.

    :param path: The absolute string path to a python module

    :returns: A module object instance
    """
    module_name = path.split(".")[-2]
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)
    return module


def folder_path(
    file_path: str,
):
    return pathlib.Path(file_path).parent.absolute()


def file_namespace(file_path: str, prefix: str = "results") -> str:
    file_name = os.path.basename(file_path)
    if "." in file_name:
        file_name = os.path.splitext(file_name)[0]

    return os.path.join(prefix, file_name)


def random_string(
    length: int = 4,
    characters=string.ascii_lowercase + string.ascii_uppercase + string.digits,
) -> str:
    return "".join(random.choices(characters, k=length))


def get_comments_from_module(path: str) -> list[str]:
    comments = []
    with open(path) as file:
        tokens = tokenize.generate_tokens(file.readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comments.append(token.string)

    return comments


def parse_parameter_info(string: str) -> dict[str, str]:
    """
    Given a ``string`` that contains some multiline text, this function will parse and extract
    all the individual parameter descriptions that are contained in that string. These will be
    returned as a dictionary where the string keys are the names of the parameters and the
    string values are the corresponding descriptions.

    :param string: A multiline string which may contain parameter descriptions among other things

    :returns: dict
    """
    result = {}
    pattern = re.compile(r":param\s+(\w+):\n((?:(?:\t+|\s{4,}).*\n)*)")
    for name, description in pattern.findall(string):
        description_lines = description.split("\n")
        description = " ".join([line.lstrip(" ") for line in description_lines])
        result[name] = description

    return result


def parse_hook_info(string: str) -> dict[str, str]:
    """
    Given a ``string`` that contains some multiline text, this function will parse and extract
    all the individual hook descriptions that are contained in that string. These will be
    returned as a dictionary where the string keys are the names of the parameters and the
    string values are the corresponding descriptions.

    :param string: A multiline string which may contain hook descriptions among other things

    :returns: dict
    """
    result = {}
    pattern = re.compile(r":hook\s+(\w+):\n((?:(?:\t+|\s{4,}).*\n)*)")
    for name, description in pattern.findall(string):
        description_lines = description.split("\n")
        description = " ".join([line.lstrip(" ") for line in description_lines])
        result[name] = description

    return result


def type_string(type_instance: type) -> str:
    """
    Returns a human-readable string representation of a type annotation or type instance.

    This function recursively constructs a string that describes the given type, including generic types
    (such as List[int], Dict[str, float], etc.) and their arguments. If the type instance has an
    '__origin__' attribute (as is the case for many types from the 'typing' module), it will include the
    origin and its arguments. If the type does not have a '__name__' attribute, 'UnkownType' will be returned.

    Example
    -------
    >>> from typing import List, Dict
    >>> type_string(List[int])
    'list[int]'
    >>> type_string(Dict[str, float])
    'dict[str, float]'
    >>> type_string(int)
    'int'

    :param type_instance: The type or type annotation to be converted to a string.
    :returns: A string representation of the type.
    """

    string = ""
    if hasattr(type_instance, "__origin__"):
        if hasattr(type_instance, "__name__"):
            string = type_instance.__name__
        else:
            string = str(type_instance.__origin__)

        if hasattr(type_instance, "__args__"):
            string += (
                f'[{", ".join([type_string(arg) for arg in type_instance.__args__])}]'
            )

    else:

        # 24.06.2025
        # Added the check for __name__ here, because there were problems since some objects
        # passing through this function did not have a __name__ attribute.
        if hasattr(type_instance, "__name__"):
            string = type_instance.__name__
        else:
            string = "UnkownType"

    return string


def has_file_extension(
    file_path: str,
) -> bool:
    """
    Given the absolute string ``file_path`` to a file, this function checks whether that file has an
    extension or not. If it has an extension, it will return True, otherwise False.

    :param file_path: The absolute string path to a file

    :returns: bool
    """
    return os.path.splitext(file_path)[1] != ""


def set_file_extension(file_path: str, extension: str) -> str:
    """
    Given the absolute string ``file_path`` to a file, this function is supposed to set the
    file extension of that file to the given ``extension`` and return the result.

    If the file does not yet have an extension, it will simply append the given
    ``extension`` to the file name. If the file already has an extension, it will replace that
    extension with the given ``extension``.

    :param file_path: The absolute string path to a file
    :param extension: The string file extension to be set, e.g. "txt" or "json"
    :returns: The absolute string path to the file with the new extension
    """
    root, _ = os.path.splitext(file_path)
    if not extension.startswith("."):
        extension = "." + extension
    return root + extension


def is_experiment_archive(folder_path: str) -> bool:
    """
    Given the absolute string ``folder_path`` to a folder, this function checks whether that folder
    is an experiment archive or not.

    An experiment archive is defined as a folder that contains a file
    named "experiment.json" in it.

    :param folder_path: The absolute string path to a folder

    :returns: bool
    """
    return os.path.exists(os.path.join(folder_path, "experiment_meta.json"))


def render_string_table(
    column_names: list[str],
    rows: list[list[str | int | list]],
    reduce_func: lambda l: f"{np.mean(l):.2f}±{np.std(l):.2f}",
) -> str:
    """
    Given a list of ``column_names`` and a list of ``rows``, this function will render a string table
    where each row is a list of values. If a value in a row is a list, it will be reduced using the
    given ``reduce_func``. The resulting table will be returned as a string.

    :param column_names: A list of strings representing the column names
    :param rows: A list of lists, where each inner list represents a row in the table
    :param reduce_func: A function that takes a list and returns a string representation of the reduced value
    :returns: A string representation of the table
    """
    table = PrettyTable()
    table.field_names = column_names

    for row in rows:
        table.add_row(
            [reduce_func(cell) if isinstance(cell, list) else cell for cell in row]
        )

    return table.get_string()


def trigger_notification(
    message: str,
    duration: int = 3,
) -> None:
    """
    This method will trigger a system notification with the given string ``message`` which will
    be displayed for the given ``duration`` in seconds.

    :param message: The string message to be displayed
    :param duration: The integer duration in seconds

    :returns: None
    """

    if OS_NAME == "Linux":
        # On linux there is a native command that can be used to trigger a system notification!
        subprocess.run(["notify-send", message, "-t", str(duration * 1000)])

    elif OS_NAME == "Windows":

        return
        import winsound

        from win10toast import ToastNotifier

        # Display the notification on Windows
        toaster = ToastNotifier()
        toaster.show_toast("Notification", message, duration=duration, threaded=True)


def is_dist_editable(dist: pkg_resources.EggInfoDistribution) -> bool:
    location = dist.location

    pth_path = os.path.join(location, f"{dist.key}.pth")
    if os.path.exists(pth_path):
        return True

    direct_url_path = os.path.join(
        dist.location, f"{dist.key}-{dist.version}.dist-info", "direct_url.json"
    )
    if os.path.exists(direct_url_path):
        return True

    return False


def get_dist_path(
    dist: pkg_resources.EggInfoDistribution, editable: bool = False
) -> str:
    if editable:
        pth_path = os.path.join(dist.location, f"{dist.key}.pth")
        if os.path.exists(pth_path):
            with open(pth_path) as file:
                package_path = file.read().strip()
    else:
        package_path = os.path.join(dist.location, dist.key)

    return package_path


def get_dependencies() -> dict[str, dict]:
    """
    Retrieves information about all installed Python package dependencies.
    This function iterates over all installed distributions (packages) in the current Python environment
    and collects detailed metadata for each package. The information is returned as a dictionary where
    each key is the package name and the value is another dictionary containing metadata about the package.

    Notes
    -----
    - The function attempts to extract the package name from the distribution metadata, falling back to
      alternative fields if necessary.
    - If a package is installed in editable mode, the 'editable' field will be True; otherwise, it will be False.
    - The function is robust to missing metadata fields and will not raise exceptions in such cases.

    Examples
    --------
    >>> deps = get_dependencies()
    >>> for name, meta in deps.items():
    ...     print(f"{name}: {meta['version']} (editable: {meta['editable']})")

    :returns: A dictionary mapping package names to their metadata dictionaries. Each metadata dictionary contains:
        - 'name' (str): The name of the package.
        - 'version' (str): The installed version of the package.
        - 'path' (str): The filesystem path to the package's installation directory.
        - 'requires' (List[str]): A list of requirements (dependencies) for the package.
        - 'editable' (bool): Indicates if the package is installed in editable mode (PEP 610 origin info).
    """

    dependencies: dict[str, dict] = {}
    for dist in distributions():

        try:
            name = (
                dist.metadata["Name"]
                or dist.metadata["name"]
                or dist.metadata["Summary"]
            )
        except Exception:
            name = dist.metadata.get(
                "Name", dist.metadata.get("Name", dist.metadata.get("Summary", ""))
            )

        dependencies[name] = {
            "name": name,
            "version": dist.version,
            "path": str(dist.locate_file("")),
            "requires": list(dist.requires or []),
            # editable: PEP 610 origin info; falls back to False if not editable
            "editable": bool(getattr(dist, "origin", None)),
        }

    return dependencies


class SetArguments:
    """
    This class acts as a context manager that can be used to temporarily change the value of the sys.argv
    list of command line arguments. This can be useful for testing purposes where the command line arguments
    need to be changed for a specific test case.
    """

    def __init__(self, args: list[str]):
        self.args = args
        self.sys_args = None

    def __enter__(
        self,
    ) -> "SetArguments":
        self.sys_args = sys.argv
        sys.argv = self.args
        return self

    def __exit__(self, *args, **kwargs) -> None:
        sys.argv = self.sys_args


# === LATEX UTILS ===


def render_latex_table(
    table: PrettyTable,
    table_template: str = "latex_table.tex.j2",
    extract_func: Callable[[str], dict] = lambda v: {"string": v},
    transform_func: Callable[[dict, list], dict] = lambda cell, rows: cell,
) -> str:
    """
    Renders the given ``table`` as a Latex table string.
    """

    # --- extracting data from the table ---
    # At first we need to extract all the data from the PrettyTable instance
    # which we can then afterwards put back into the latex template.

    columns = table.field_names
    rows = []
    for row_index, _row in enumerate(table._rows):

        row: list[dict] = []

        # --- processing special cases ---
        # When iterating over the individual cells of the row we want to handle some
        # special cases. First of all we would like to be able to detect if a cell contains
        # only a single numeric value. If that is not the case we want to detect if it contains
        # two values separated by a "±" character. If that is the case we want to split
        # those two values and render them in a special way in latex.
        # If neither of the special cases apply we simply render the cell as a normal string.

        for col_index, value in enumerate(_row):

            value_clean = value.strip().replace(" ", "")
            info: dict = {
                "row_index": row_index,
                "col_index": col_index,
            }

            # check if value is numeric
            try:
                number = float(value_clean)
                info.update(
                    {
                        "number": number,
                    }
                )
                row.append(info)
                continue
            except ValueError:
                pass

            # Check if the value contains a "±" character (either normally or the latex version)
            # using a regex
            match = re.match(
                r"^([-+]?\d*\.?\d+)(?:\\pm|±)([-+]?\d*\.?\d+)$", value_clean
            )
            if match:
                mean = float(match.group(1))
                std = float(match.group(2))
                info.update(
                    {
                        "mean": mean,
                        "std": std,
                    }
                )
                row.append(info)
                continue

            # If neither of the special cases apply we apply the `extract_func` from the arguments
            # which implements the fallback version of how to extract the dict information from the given
            # cell string.
            info.update(extract_func(value))
            row.append(info)

        rows.append(row)

    # --- applying transformation ---
    # After having extracted the raw data from the table, we can now apply the transformation. It is possible
    # to supply a custom transformation function via the arguments which will determine how the cell info dict
    # is modified based on the individual cell and the entire table.
    for row in rows:
        for cell in row:
            cell.update(transform_func(cell, rows))

    # --- rendering the latex string ---
    # The latex string itself will be created from the information about the rows and columns but will
    # be rendered using a jinja2 template.

    template = TEMPLATE_ENV.get_template(table_template)
    string = template.render(
        {
            # A list of string column names
            "columns": columns,
            # A list of rows where each row is a list of dicts representing the content of the cell.
            "rows": rows,
        }
    )
    return string
