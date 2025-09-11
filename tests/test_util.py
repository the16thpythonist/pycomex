import os
import sys
import typing as t
import unittest
from inspect import getframeinfo, stack

import numpy as np
import pytest
from prettytable import PrettyTable

from pycomex.util import (
    SetArguments,
    get_comments_from_module,
    get_dependencies,
    get_version,
    parse_parameter_info,
    render_latex_table,
    render_string_table,
    set_file_extension,
    trigger_notification,
    type_string,
)

from .util import ARTIFACTS_PATH, ASSETS_PATH


def test_type_string():
    string = type_string(dict[str, int])
    print(string)
    assert string == "Dict[str, int]"

    string = type_string(list[dict[bool, tuple[int, int]]])
    print(string)
    assert string == "List[Dict[bool, Tuple[int, int]]]"


def test_parse_parameter_info_basically_works():
    """
    the "parse_parameter_info" is supposed to parse a specific format of additional parameter information
    from a string and return all the information as a dictionary.
    """
    string = (
        "Some random comment\n"
        ":param PARAMETER:\n"
        "       the first line.\n"
        "       the second line.\n"
        "Some random string\n"
    )
    result = parse_parameter_info(string)
    assert isinstance(result, dict)
    assert "PARAMETER" in result


def test_get_comments_from_module_basically_works():
    """
    The "get_comments_from_module" function should return a list with all the string comment lines
    for the absolute path of a given python module
    """
    module_path = os.path.join(ASSETS_PATH, "mock_functional_experiment.py")
    comments = get_comments_from_module(module_path)
    assert isinstance(comments, list)
    assert len(comments) != 0

    # Testing a single example comment from the list which we know is part of that module.
    assert "# testing comment - do not remove" in comments


def test_get_version():
    version_string = get_version()
    assert version_string != ""


@pytest.mark.localonly
def test_trigger_notification_basically_works():
    """
    The "trigger_notification" function should display a system notification with the given message
    """
    trigger_notification("Hello World, from unittesting!")
    assert True


class TestSetArguments:
    """
    A suite of tests for the SetArguments context manager which is provides a temporary emulation
    of a sys.argv list.
    """

    def test_sys_argv_structure(self):
        print(sys.argv)
        assert isinstance(sys.argv, list)

    def test_basically_works(self):
        """
        The class should act as a context manager that is able to change the sys.argv list only as
        long as the context is active and reset it to the previous state afterwards.
        """
        original = sys.argv.copy()

        with SetArguments(["python", "run.py", "--help"]):
            # only in the context manager should the args become exactly that
            assert sys.argv == ["python", "run.py", "--help"]

        # outside it should not be that but instead should be its original value
        assert sys.argv != ["python", "run.py", "--help"]
        assert len(sys.argv) != 0
        assert sys.argv == original

    def test_works_with_exception(self):
        """
        It is important that the sys.argv list is reset to its original state even if an exception
        is raised within the context manager.
        """
        original = sys.argv.copy()

        try:
            with SetArguments(["python", "run.py", "--help"]):
                # only in the context manager should the args become exactly that
                assert sys.argv == ["python", "run.py", "--help"]

                # raise an exception
                raise ValueError("Some random exception")
        except ValueError:
            pass
        finally:
            assert sys.argv != ["python", "run.py", "--help"]
            assert sys.argv == original


def test_get_dependencies():
    """
    The "get_dependencies" function should return a dictionary with all the dependencies of the current
    python runtime.
    """
    deps = get_dependencies()
    print(deps)

    assert isinstance(deps, dict)
    assert len(deps) != 0

    example_info = next(iter(deps.values()))
    assert isinstance(example_info, dict)
    assert "version" in example_info
    assert "name" in example_info
    assert "path" in example_info


def test_set_file_extension():

    # Test replacing an existing extension
    assert set_file_extension("/tmp/file.txt", "json") == "/tmp/file.json"
    # Test adding an extension to a file with no extension
    assert set_file_extension("/tmp/file", "txt") == "/tmp/file.txt"
    # Test adding an extension with a leading dot
    assert set_file_extension("/tmp/file", ".csv") == "/tmp/file.csv"
    # Test replacing an extension with a leading dot
    assert set_file_extension("/tmp/file.md", ".rst") == "/tmp/file.rst"
    # Test file with multiple dots
    assert set_file_extension("/tmp/archive.tar.gz", "zip") == "/tmp/archive.tar.zip"
    # Test empty extension
    assert set_file_extension("/tmp/file", "") == "/tmp/file."


def test_render_string_table_basic():
    # Basic test: no lists in rows
    columns = ["A", "B"]
    rows = [
        [1, 2],
        [3, 4],
    ]
    result = render_string_table(
        columns, rows, reduce_func=lambda l: f"{np.mean(l):.2f}±{np.std(l):.2f}"
    )
    assert "A" in result and "B" in result
    assert "1" in result and "2" in result
    assert "3" in result and "4" in result


def test_render_string_table_with_lists():
    columns = ["Name", "Scores"]
    rows = [
        ["Alice", [1, 2, 3]],
        ["Bob", [4, 5, 6]],
    ]

    def reduce_func(l):
        return f"{np.mean(l):.1f}±{np.std(l):.1f}"

    result = render_string_table(columns, rows, reduce_func=reduce_func)
    assert "Alice" in result and "Bob" in result
    assert "2.0±0.8" in result and "5.0±0.8" in result


def test_render_string_table_mixed_types():
    columns = ["ID", "Value"]
    rows = [
        [1, [10, 20]],
        [2, 30],
    ]

    def reduce_func(l):
        return f"{sum(l)}"

    result = render_string_table(columns, rows, reduce_func=reduce_func)
    assert "30" in result  # from sum([10, 20]) and the int 30
    assert "1" in result and "2" in result


def test_render_string_table_empty():
    columns = ["A", "B"]
    rows = []
    result = render_string_table(columns, rows, reduce_func=lambda l: str(l))
    assert "A" in result and "B" in result
    assert result.count("\n") > 0  # Table header and border


def test_render_latex_table_basically_works():
    """
    Checks the ``render_latex_table`` function which is supposed to render a latex table from
    a PrettyTable object instance.
    """

    table = PrettyTable()
    table.field_names = ["A", "B", "C"]
    table.add_row(["string 1", "12.2", "3.4"])
    table.add_row(["string 2", "5.6±9.0", "7.8"])
    table.add_row(["string 3", r"9.0\pm3.2", "1.2"])

    def transform(cell, rows):
        if "number" in cell and 3 <= cell["number"] <= 5:
            return {
                "string": f"\\textbf{{{cell['number']}}}",
            }
        if "number" in cell and 1 <= cell["number"] <= 2:
            return {
                "underline": True,
            }
        return cell

    latex_code = render_latex_table(table, transform_func=transform)
    print(latex_code)
