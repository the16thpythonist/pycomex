"""
Utility methods
"""
import logging
import os
import json
import datetime
import pathlib
import textwrap
import typing as t
from typing import Optional, List, Callable
from inspect import getframeinfo, stack

import jinja2 as j2
import numpy as np


PATH = pathlib.Path(__file__).parent.absolute()
VERSION_PATH = os.path.join(PATH, 'VERSION')
TEMPLATE_PATH = os.path.join(PATH, 'templates')
EXAMPLES_PATH = os.path.join(PATH, 'examples')

TEMPLATE_ENV = j2.Environment(
    loader=j2.FileSystemLoader(TEMPLATE_PATH),
    autoescape=j2.select_autoescape()
)
TEMPLATE_ENV.globals.update({
    'os': os,
    'datetime': datetime,
    'len': len,
    'int': int,
    'type': type,
    'sorted': sorted,
    'modulo': lambda a, b: a % b,
    'key_sort': lambda k, v: k,
    'wrap': textwrap.wrap,
})

NULL_LOGGER = logging.Logger('NULL')
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


def dict_value_sort(data: dict,
                    key: Optional[str] = None,
                    reverse: bool = False,
                    k: Optional[int] = None):

    def query_dict(current_dict: dict, query: Optional[str]):
        if query is not None:
            keys = query.split('/')
            for current_key in keys:
                current_dict = current_dict[current_key]

        return current_dict

    items_sorted = sorted(data.items(), key=lambda t: query_dict(t[1], key), reverse=reverse)
    if k is not None:
        k = min(k, len(items_sorted))
        items_sorted = items_sorted[:k]

    return items_sorted


TEMPLATE_ENV.filters['dict_value_sort'] = dict_value_sort


def get_version():
    with open(VERSION_PATH) as file:
        return file.read().replace(' ', '').replace('\n', '')


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

    **CHANGES 12.09.2022**

    Previously this class worked like this: In the __enter__ method a frameinfo supplied the line number at
    which the context starts and then the same was done in __exit__ and with Python 3.8 this actually worked
    The two methods returned the correct line numbers. But as of Python 3.10, this no longer works because
    the __exit__ method now ALSO returns just the line number of where the context manager starts.

    But since we can still get the start line reliably, we just have to extract the code with some string
    processing now: With the starting line we know the indent of this context manager and can then record
    all the code which follows it in one level of indent deeper.
    """
    def __init__(self,
                 stack_index: int = 2,
                 initial_stack_index: int = 1,
                 skip=False):
        self.stack_index = stack_index

        # Getting the filename and actually the content of the file in the constructor already is an
        # improvement towards the previous version. Back then it was done in time when the enter method was
        # called, but the problem is if the file within the filesystem was changed in that time (which is
        # actually quite likely) then the data supplied by the frame info would be out of sync and the whole
        # process would fail.
        frame_info = getframeinfo(stack()[initial_stack_index][0])
        self.file_path = frame_info.filename
        with open(self.file_path, mode='r') as file:
            self.file_lines = file.readlines()

        self.enter_line: Optional[int] = None
        self.exit_line: Optional[int] = None

        self.enter_indent: int = 0
        self.code_indent: int = 0

        self.code_lines: List[str] = []
        self.code_string: str = ''

        # This is a flag, that if set to True signals this context manager to skip the execution of the
        # entire content.
        self.skip = skip

        # Callbacks can externally be added to these lists to have functions be executed at either the enter
        # or the exit. The first arg is this object itself, the second is the enter / end line index number
        # respectively
        self.enter_callbacks: List[Callable[['RecordCode', int], None]] = []
        self.exit_callbacks: List[Callable[['RecordCode', int], None]] = []

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
        print(exc_type, exc_value)
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

            self.code_lines.append(line[self.code_indent:])

        self.exit_line = i + 1

        # And now it just remains to put those lines into a string
        self.code_string = '\n'.join(self.code_lines)

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


def split_namespace(namespace: str) -> t.List[str]:
    """
    Given the namespace string of an experiment, this function will split that string into a list of
    individual path segments.

    :param str namespace: The string namespace definition for an experiment module
    :returns: A list containing the split, individual path segments
    """
    # TODO: We could extend this to raise errors if an invalid format is detected.

    if '/' in namespace:
        return namespace.split('/')
    # Technically we would discourage the usage of backslashes within the namespace specification, but there
    # is the real possibility that a deranged windows user tries this, so we might as well make it a feature
    # now already.
    elif '\\' in namespace:
        return namespace.split('\\')
    else:
        return [namespace]
