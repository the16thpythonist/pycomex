"""
Utility methods
"""

import ast
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
from prettytable import PrettyTable

# The modern "importlib.metadata" module is only available in Python 3.8 and later.
# to ensure backwards compatibility with Python 3.7 and earlier, we use the backport / previous
# version of this module, which is "importlib_metadata", if necessary
if sys.version_info >= (3, 8):
    from importlib.metadata import distributions, Distribution
else:
    from importlib_metadata import distributions, Distribution  # backport

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


def is_dist_editable(dist: Distribution) -> bool:
    """
    Check if a distribution is installed in editable mode.

    This function checks for editable installation by looking for:
    1. direct_url.json file (PEP 610 standard for direct installs)
    2. .pth files that indicate editable installs

    :param dist: The distribution to check
    :returns: True if the distribution is editable, False otherwise
    """
    # Check for direct_url.json (PEP 610 standard)
    try:
        direct_url_json = dist.read_text("direct_url.json")
        if direct_url_json and "editable" in direct_url_json:
            return True
    except (FileNotFoundError, AttributeError):
        pass

    # Check for .pth files in site-packages (alternative method)
    try:
        location = str(dist.locate_file(""))
        if location:
            pth_path = os.path.join(location, f"{dist.metadata['Name']}.pth")
            if os.path.exists(pth_path):
                return True
    except (AttributeError, KeyError):
        pass

    return False


def get_dist_path(
    dist: Distribution, editable: bool = False
) -> str:
    """
    Get the filesystem path to a distribution.

    :param dist: The distribution to get the path for
    :param editable: Whether to look for editable installation paths
    :returns: The filesystem path to the distribution
    """
    if editable:
        # For editable installs, check direct_url.json first
        try:
            direct_url_json = dist.read_text("direct_url.json")
            if direct_url_json:
                direct_url_data = json.loads(direct_url_json)
                if "url" in direct_url_data and direct_url_data["url"].startswith("file://"):
                    # Extract path from file:// URL
                    file_path = direct_url_data["url"][7:]  # Remove 'file://' prefix
                    return file_path
        except (FileNotFoundError, AttributeError, json.JSONDecodeError):
            pass

        # Fallback to .pth file method
        try:
            location = str(dist.locate_file(""))
            if location:
                pth_path = os.path.join(location, f"{dist.metadata['Name']}.pth")
                if os.path.exists(pth_path):
                    with open(pth_path) as file:
                        package_path = file.read().strip()
                        return package_path
        except (AttributeError, KeyError):
            pass

    # For non-editable or fallback case
    try:
        location = str(dist.locate_file(""))
        if location:
            package_path = os.path.join(location, dist.metadata['Name'])
            return package_path
    except (AttributeError, KeyError):
        pass

    # Final fallback - return empty string if we can't determine path
    return ""


def get_cuda_version() -> Optional[str]:
    """
    Attempts to detect the installed CUDA version by running nvidia-smi.

    :returns: CUDA version string (e.g., "12.1") or None if not detected
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Try to get CUDA version from nvidia-smi
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse CUDA version from output (usually shows "CUDA Version: X.Y")
                import re
                match = re.search(r"CUDA Version:\s*(\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    return None


def get_environment_info() -> dict:
    """
    Collects comprehensive environment information including OS details,
    environment variables, and system libraries.

    :returns: Dictionary containing environment information with keys:
        - 'os': Operating system details (name, version, platform, architecture)
        - 'env_vars': Crucial environment variables
        - 'system_libraries': Detected system libraries (CUDA, etc.)
    """
    env_info = {
        "os": {
            "name": platform.system(),
            "version": platform.release(),
            "platform": sys.platform,
            "architecture": platform.machine(),
        },
        "env_vars": {},
        "system_libraries": {},
    }

    # Capture crucial environment variables
    crucial_env_vars = [
        "PATH",
        "PYTHONPATH",
        "LD_LIBRARY_PATH",
        "CUDA_HOME",
        "CUDA_PATH",
        "CUDNN_PATH",
        "HOME",
        "USER",
    ]

    for key in crucial_env_vars:
        if key in os.environ:
            env_info["env_vars"][key] = os.environ[key]

    # Detect system libraries
    cuda_version = get_cuda_version()
    if cuda_version:
        env_info["system_libraries"]["cuda"] = cuda_version

    return env_info


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
    - A special '__environment__' key contains system environment information (OS, env vars, libraries).

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
        - '__environment__' (dict): System environment information (special key).
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

    # Add environment information
    dependencies["__environment__"] = get_environment_info()

    return dependencies


def generate_requirements_txt(dependencies: dict[str, dict]) -> str:
    """
    Generate a requirements.txt format string from a dependencies dictionary.

    This function takes the dependencies dictionary (as returned by get_dependencies())
    and generates a requirements.txt format string with version-pinned dependencies.
    The function automatically filters out:
    - Special keys starting with '__' (__python__, __environment__)
    - Editable packages (these are handled separately in .sources/)

    The resulting string contains lines in the format 'package==version' and is
    sorted alphabetically for consistency.

    Example
    -------
    >>> deps = get_dependencies()
    >>> requirements_content = generate_requirements_txt(deps)
    >>> print(requirements_content)
    numpy==1.24.0
    requests==2.31.0
    scipy==1.11.0

    :param dependencies: Dictionary mapping package names to metadata dictionaries,
        as returned by get_dependencies().

    :returns: String content for a requirements.txt file with version-pinned dependencies.
    """
    requirements_lines = []

    for name, info in dependencies.items():
        # Skip special keys (like __python__, __environment__)
        if name.startswith("__"):
            continue

        # Skip editable packages (those are handled in .sources/)
        if info.get("editable", False):
            continue

        # Get version and create requirement line
        version = info.get("version", "")
        if version:
            requirements_lines.append(f"{name}=={version}")

    # Sort alphabetically (case-insensitive) by package name only for consistency
    # We need to extract the package name for sorting to avoid version numbers affecting order
    requirements_lines.sort(key=lambda line: line.split("==")[0].lower())

    # Join with newlines and add final newline
    return "\n".join(requirements_lines) + "\n"


def get_module_imports(file_path: str) -> list[tuple[str, str | None, bool]]:
    """
    Parse Python file using AST to extract all import statements.

    This function analyzes a Python source file and extracts information about all
    import statements (both `import` and `from ... import` forms). It identifies
    the module names being imported, whether they use relative imports, and which
    specific names are being imported from modules.

    The function handles:
    - Standard imports: `import os`, `import sys`
    - From imports: `from pathlib import Path`
    - Relative imports: `from . import module`, `from ..package import foo`
    - Multiple imports: `import os, sys, json`
    - Aliased imports: `import numpy as np` (returns base module name)

    Example
    -------
    .. code-block:: python

        # For a file containing:
        # import os
        # from pathlib import Path
        # from . import utils

        imports = get_module_imports("example.py")
        # Returns:
        # [
        #     ("os", None, False),
        #     ("pathlib", "Path", False),
        #     (".", "utils", True)
        # ]

    :param file_path: Absolute path to the Python file to parse.

    :returns: List of tuples (module_name, from_name, is_relative) where:
        - module_name: The module being imported (e.g., "os", ".", "..")
        - from_name: None for `import x`, specific name for `from x import y`
        - is_relative: True if the import uses relative syntax (starts with .)
    """
    imports = []

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            tree = ast.parse(file.read(), filename=file_path)
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError) as e:
        # If we can't parse the file, return empty list
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # Handle: import os, sys
            for alias in node.names:
                imports.append((alias.name, None, False))

        elif isinstance(node, ast.ImportFrom):
            # Handle: from module import name
            module = node.module if node.module else ""
            level = node.level  # 0 = absolute, 1 = ., 2 = .., etc.

            # Determine if this is a relative import
            is_relative = level > 0

            # For relative imports, construct the module string with dots
            if is_relative:
                if module:
                    # from ..package import foo -> ".." + "package"
                    module_name = "." * level + module
                else:
                    # from . import foo -> "."
                    module_name = "." * level
            else:
                module_name = module

            # Extract the names being imported
            for alias in node.names:
                from_name = alias.name
                imports.append((module_name, from_name, is_relative))

    return imports


def resolve_import_path(
    module_name: str,
    base_dir: str,
    is_relative: bool = False,
    current_file: str | None = None
) -> str | None:
    """
    Resolve an import statement to an absolute file path.

    This function attempts to determine if an import refers to a local Python file
    (which should be bundled with the experiment) or an external dependency (stdlib
    or installed package). It returns the absolute path for local files and None
    for external dependencies.

    The function handles:
    - Standard library modules (returns None)
    - Installed packages from site-packages (returns None)
    - Local Python files (returns absolute path)
    - Local packages with __init__.py (returns path to __init__.py)
    - Relative imports using current file context

    Resolution Strategy
    -------------------
    1. For relative imports, compute path relative to current_file or base_dir
    2. For absolute imports, use importlib to find the module spec
    3. Check if the resolved path is in the project directory (not site-packages)
    4. Return absolute path for local files, None for external dependencies

    Example
    -------
    .. code-block:: python

        # Stdlib module
        path = resolve_import_path("os", "/project", False)
        # Returns: None

        # Installed package
        path = resolve_import_path("numpy", "/project", False)
        # Returns: None

        # Local module in same directory
        path = resolve_import_path("utils", "/project", False, "/project/main.py")
        # Returns: "/project/utils.py"

        # Relative import
        path = resolve_import_path(".utils", "/project/src", True, "/project/src/main.py")
        # Returns: "/project/src/utils.py"

    :param module_name: The module name to resolve (e.g., "os", "mymodule", ".utils").
    :param base_dir: The base directory of the project for resolving local imports.
    :param is_relative: Whether this is a relative import (starts with .).
    :param current_file: Optional path to the file containing the import statement,
        used for resolving relative imports accurately.

    :returns: Absolute path to the local Python file if it's a local module,
        None if it's a stdlib module or installed package.
    """
    # Handle relative imports
    if is_relative:
        # Determine the reference directory for relative imports
        if current_file:
            ref_dir = os.path.dirname(os.path.abspath(current_file))
        else:
            ref_dir = os.path.abspath(base_dir)

        # Count the number of leading dots for parent directory traversal
        level = 0
        while level < len(module_name) and module_name[level] == '.':
            level += 1

        # Navigate up the directory tree based on level
        for _ in range(level - 1):
            ref_dir = os.path.dirname(ref_dir)

        # Extract the actual module path after the dots
        relative_module = module_name[level:] if level < len(module_name) else ""

        if relative_module:
            # Convert module path to file path (e.g., "package.module" -> "package/module")
            module_path = relative_module.replace('.', os.sep)
            candidate_path = os.path.join(ref_dir, module_path)
        else:
            # from . import something - no additional path component
            candidate_path = ref_dir

        # Check if it's a Python file
        if os.path.isfile(candidate_path + '.py'):
            return os.path.abspath(candidate_path + '.py')
        # Check if it's a package directory
        elif os.path.isdir(candidate_path):
            init_path = os.path.join(candidate_path, '__init__.py')
            if os.path.exists(init_path):
                return os.path.abspath(init_path)

        # If not found as file or package, might still be a valid import
        # (e.g., from . import module_name where module_name.py is in the same dir)
        return None

    # Handle absolute imports
    # First, check if it's a standard library module
    if sys.version_info >= (3, 10):
        if module_name in sys.stdlib_module_names:
            return None
    else:
        # For Python < 3.10, use a heuristic
        # Try to import and check if it's a builtin
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                # Builtin modules have no origin
                if spec.origin is None or spec.origin == 'built-in':
                    return None
        except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
            # Module not found via import system, will check as local file later
            pass

    # Try to find the module using importlib
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            # Module not found in import system, fall through to local file check
            raise ModuleNotFoundError(f"No module named '{module_name}'")

        if spec.origin is None or spec.origin == 'built-in':
            # Builtin module
            return None

        origin = spec.origin

        # Check if this is a local file within the project
        abs_base = os.path.abspath(base_dir)
        abs_origin = os.path.abspath(origin)

        # If the module is within the base directory, it's a local dependency
        if abs_origin.startswith(abs_base):
            return abs_origin

        # Check if it's in site-packages or dist-packages (installed package)
        if 'site-packages' in abs_origin or 'dist-packages' in abs_origin:
            return None

        # If we can't determine, be conservative and treat as external
        return None

    except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
        # Module not found - might be a local file that hasn't been imported yet
        # Try to find it as a local file
        module_path = module_name.replace('.', os.sep)
        candidate_path = os.path.join(base_dir, module_path)

        # Check if it's a Python file
        if os.path.isfile(candidate_path + '.py'):
            return os.path.abspath(candidate_path + '.py')
        # Check if it's a package directory
        elif os.path.isdir(candidate_path):
            init_path = os.path.join(candidate_path, '__init__.py')
            if os.path.exists(init_path):
                return os.path.abspath(init_path)

        return None


def find_all_local_dependencies(
    experiment_path: str,
    experiment_dependencies: list[str] | None = None
) -> set[str]:
    """
    Recursively find ALL local Python files imported by an experiment.

    This function performs a depth-first search through the import tree of a Python
    experiment to discover all local Python files that are imported either directly
    or transitively. It handles circular imports gracefully by tracking visited files
    and distinguishes between local modules (which should be bundled) and external
    dependencies (stdlib and installed packages, which should not be bundled).

    The search starts with:
    1. The experiment module itself (experiment_path)
    2. Any parent experiments from Experiment.extend() (experiment_dependencies)

    For each file, the function:
    1. Parses imports using get_module_imports()
    2. Resolves each import using resolve_import_path()
    3. If the import is a local file, adds it to the result set and recurses
    4. If the import is stdlib/installed package, skips it
    5. Handles circular imports by tracking visited files

    Algorithm Details
    -----------------
    - Uses depth-first search with explicit visited set
    - Base directory for resolution is derived from experiment_path's parent
    - Handles relative imports by passing current_file context
    - Gracefully handles parsing errors and missing files
    - Returns deduplicated set of absolute paths

    Example
    -------
    .. code-block:: python

        # Find all local dependencies for an experiment
        experiment_path = "/project/experiments/my_experiment.py"
        parent_experiments = ["/project/experiments/base_experiment.py"]

        deps = find_all_local_dependencies(experiment_path, parent_experiments)
        # Returns: {
        #     "/project/experiments/my_experiment.py",
        #     "/project/experiments/base_experiment.py",
        #     "/project/utils/helper.py",
        #     "/project/models/__init__.py",
        #     "/project/models/network.py",
        #     ...
        # }

    :param experiment_path: Absolute path to the main experiment Python file.
    :param experiment_dependencies: Optional list of absolute paths to parent
        experiments (from Experiment.extend()). These will be included in the
        dependency search.

    :returns: Set of absolute paths to all local Python files imported by the
        experiment (including the experiment itself and parent experiments).
    """
    if experiment_dependencies is None:
        experiment_dependencies = []

    # Set to store all discovered local dependencies
    local_files: set[str] = set()

    # Set to track which files we've already processed (prevents circular imports)
    visited: set[str] = set()

    # Determine the base directory for import resolution
    # Use the directory containing the experiment file
    base_dir = os.path.dirname(os.path.abspath(experiment_path))

    def process_file(file_path: str) -> None:
        """
        Recursively process a Python file to find all its local dependencies.

        :param file_path: Absolute path to the Python file to process.
        """
        # Normalize the path
        abs_file_path = os.path.abspath(file_path)

        # Skip if we've already processed this file (handles circular imports)
        if abs_file_path in visited:
            return

        # Mark as visited
        visited.add(abs_file_path)

        # Add this file to our result set
        local_files.add(abs_file_path)

        # Parse all imports from this file
        imports = get_module_imports(abs_file_path)

        # Process each import
        for module_name, from_name, is_relative in imports:
            # Resolve the import to a file path
            resolved_path = resolve_import_path(
                module_name=module_name,
                base_dir=base_dir,
                is_relative=is_relative,
                current_file=abs_file_path
            )

            # If it resolved to a local file, recursively process it
            if resolved_path is not None:
                # Only process if it's actually a file and exists
                if os.path.isfile(resolved_path):
                    process_file(resolved_path)

    # Start with the main experiment file
    process_file(experiment_path)

    # Process all parent experiments (from Experiment.extend())
    for parent_path in experiment_dependencies:
        process_file(parent_path)

    return local_files


def bundle_local_sources(
    experiment,  # Type: Experiment, but avoid circular import
    local_files: set[str]
) -> None:
    """
    Bundle all local Python source files into the experiment archive.

    This function copies all local Python files that are imported by an experiment
    into a `.local_sources/` directory within the experiment archive, preserving
    the directory structure relative to the base directory. It also generates a
    manifest file with metadata about each bundled file.

    The bundled files can be used to reproduce the experiment even if the original
    source files are modified or deleted after the experiment completes.

    Directory Structure Created
    ----------------------------
    .. code-block:: text

        experiment_archive/
        └── .local_sources/
            ├── .manifest.json         # Metadata about bundled files
            └── [files with preserved relative structure]

    Manifest Format
    ---------------
    The manifest is a JSON file with the following structure:

    .. code-block:: json

        {
            "base_dir": "/absolute/path/to/base",
            "experiment_file": "/absolute/path/to/experiment.py",
            "file_count": 5,
            "total_size": 12345,
            "files": {
                "relative/path/to/file.py": {
                    "absolute_path": "/absolute/path/to/file.py",
                    "size": 1234,
                    "modified_time": 1234567890.0
                }
            }
        }

    Example
    -------
    .. code-block:: python

        # In finalize_reproducible():
        local_files = find_all_local_dependencies(
            experiment_path=self.glob["__file__"],
            experiment_dependencies=self.dependencies
        )
        bundle_local_sources(self, local_files)

    :param experiment: The Experiment object whose archive will contain the bundled files.
    :param local_files: Set of absolute paths to local Python files to bundle.

    :returns: None
    """
    import shutil

    # Determine the base directory (directory containing the experiment file)
    experiment_path = experiment.glob["__file__"]
    base_dir = os.path.dirname(os.path.abspath(experiment_path))

    # Create .local_sources directory in the experiment archive
    local_sources_path = os.path.join(experiment.path, ".local_sources")
    os.makedirs(local_sources_path, exist_ok=True)

    # Manifest data to track what we bundled
    manifest = {
        "base_dir": base_dir,
        "experiment_file": experiment_path,
        "file_count": 0,
        "total_size": 0,
        "files": {}
    }

    # Copy each file while preserving directory structure
    for file_path in local_files:
        abs_file_path = os.path.abspath(file_path)

        # Skip files that don't exist (shouldn't happen, but be safe)
        if not os.path.isfile(abs_file_path):
            continue

        # Calculate relative path from base_dir
        try:
            rel_path = os.path.relpath(abs_file_path, base_dir)
        except ValueError:
            # If the file is on a different drive (Windows), we can't use relative path
            # In this case, we'll use a flattened structure with the full path encoded
            # This is an edge case and shouldn't happen in normal usage
            rel_path = abs_file_path.replace(os.sep, "_").replace(":", "_")

        # Create destination path preserving directory structure
        dest_path = os.path.join(local_sources_path, rel_path)
        dest_dir = os.path.dirname(dest_path)

        # Create parent directories if needed
        os.makedirs(dest_dir, exist_ok=True)

        # Copy the file (copy2 preserves metadata like timestamps)
        shutil.copy2(abs_file_path, dest_path)

        # Collect metadata for manifest
        file_stat = os.stat(abs_file_path)
        manifest["files"][rel_path] = {
            "absolute_path": abs_file_path,
            "size": file_stat.st_size,
            "modified_time": file_stat.st_mtime,
        }
        manifest["file_count"] += 1
        manifest["total_size"] += file_stat.st_size

    # Write manifest file
    manifest_path = os.path.join(local_sources_path, ".manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


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

            # Convert value to string to handle mixed types (int, float, bool, etc.)
            value_clean = str(value).strip().replace(" ", "")
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
            # cell string. Convert value to string to ensure compatibility.
            info.update(extract_func(str(value)))
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
