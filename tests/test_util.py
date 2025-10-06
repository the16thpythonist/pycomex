import logging
import os
import sys
import typing as t
import unittest
from inspect import getframeinfo, stack

import numpy as np
import pytest
from prettytable import PrettyTable

from pycomex.util import (
    AnsiSanitizingFormatter,
    SetArguments,
    get_comments_from_module,
    get_dependencies,
    get_dist_path,
    get_version,
    is_dist_editable,
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
    assert string == "dict[str, int]"

    string = type_string(list[dict[bool, tuple[int, int]]])
    print(string)
    assert string == "list[dict[bool, tuple[int, int]]]"


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


def test_ansi_sanitizing_formatter():
    """
    Test that AnsiSanitizingFormatter correctly removes ANSI escape sequences
    from log messages while preserving the rest of the message content.
    """
    formatter = AnsiSanitizingFormatter("%(message)s")

    # Test various ANSI escape sequences commonly used by Rich
    test_cases = [
        # Basic color codes
        ("\x1b[31mRed text\x1b[0m", "Red text"),
        ("\x1b[32mGreen text\x1b[39m", "Green text"),

        # Rich Panel formatting (common sequences)
        ("\x1b[3m\x1b[1mBold Italic\x1b[22m\x1b[23m", "Bold Italic"),

        # Complex formatting with multiple escape sequences
        ("\x1b[1m\x1b[34mBlue Bold\x1b[0m normal text", "Blue Bold normal text"),

        # Cursor movement and other control sequences
        ("\x1b[2K\x1b[1ACleared line\x1b[0m", "Cleared line"),

        # Real Rich panel-like content
        ("\x1b[35m╭─\x1b[0m\x1b[35m Experiment Started \x1b[0m\x1b[35m─╮\x1b[0m", "╭─ Experiment Started ─╮"),

        # Text with no ANSI codes (should remain unchanged)
        ("Plain text message", "Plain text message"),

        # Empty string
        ("", ""),

        # Mixed content
        ("Start \x1b[31mRED\x1b[0m middle \x1b[32mGREEN\x1b[0m end", "Start RED middle GREEN end"),
    ]

    for ansi_input, expected_output in test_cases:
        # Create a log record with the ANSI-formatted message
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=ansi_input,
            args=(),
            exc_info=None
        )

        # Format the record using our formatter
        formatted_message = formatter.format(record)

        # Check that ANSI codes were removed
        assert formatted_message == expected_output, f"Failed for input '{ansi_input}': got '{formatted_message}', expected '{expected_output}'"

    print("✓ All ANSI sanitization tests passed!")


def test_ansi_sanitizing_formatter_with_timestamp():
    """
    Test that AnsiSanitizingFormatter works correctly when used with timestamp formatting,
    similar to how it's used in the experiment logging.
    """
    formatter = AnsiSanitizingFormatter("%(asctime)s - %(message)s")

    # Create a log record with ANSI formatting
    record = logging.LogRecord(
        name="experiment",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="\x1b[1mEXPERIMENT STARTED\x1b[0m",
        args=(),
        exc_info=None
    )

    # Format the record
    formatted_message = formatter.format(record)

    # Check that the message contains timestamp but no ANSI codes
    assert " - EXPERIMENT STARTED" in formatted_message
    assert "\x1b[" not in formatted_message
    assert formatted_message.endswith("EXPERIMENT STARTED")

    print("✓ ANSI sanitization with timestamp formatting test passed!")


def test_importlib_metadata_migration():
    """
    Test that the migration from pkg_resources to importlib.metadata works correctly.
    This test ensures that our modernized is_dist_editable() and get_dist_path() functions
    work properly with importlib.metadata.Distribution objects.
    """
    if sys.version_info >= (3, 8):
        from importlib.metadata import distributions
    else:
        from importlib_metadata import distributions

    # Get a few distributions to test with
    test_distributions = list(distributions())[:5]
    assert len(test_distributions) > 0, "No distributions found to test with"

    for dist in test_distributions:
        # Test is_dist_editable function
        editable_result = is_dist_editable(dist)
        assert isinstance(editable_result, bool), f"is_dist_editable should return bool, got {type(editable_result)}"

        # Test get_dist_path function for non-editable case
        path_result = get_dist_path(dist, editable=False)
        assert isinstance(path_result, str), f"get_dist_path should return str, got {type(path_result)}"

        # Test get_dist_path function for editable case
        editable_path_result = get_dist_path(dist, editable=True)
        assert isinstance(editable_path_result, str), f"get_dist_path(editable=True) should return str, got {type(editable_path_result)}"

        print(f"✓ Tested {dist.metadata.get('Name', 'unknown')}: editable={editable_result}")

    print("✓ All importlib.metadata migration tests passed!")


def test_get_dependencies_without_pkg_resources():
    """
    Test that get_dependencies() works correctly without using deprecated pkg_resources.
    This verifies that the function returns consistent results with our modernized helper functions.
    """
    deps = get_dependencies()

    # Basic structure tests
    assert isinstance(deps, dict), "get_dependencies should return a dict"
    assert len(deps) > 0, "Should find at least some dependencies"

    # Test structure of dependency info
    for dep_name, dep_info in list(deps.items())[:3]:  # Test first 3 for performance
        assert isinstance(dep_name, str), f"Dependency name should be string, got {type(dep_name)}"
        assert isinstance(dep_info, dict), f"Dependency info should be dict, got {type(dep_info)}"

        # Required fields
        required_fields = ['name', 'version', 'path', 'requires', 'editable']
        for field in required_fields:
            assert field in dep_info, f"Missing required field '{field}' in dependency info for {dep_name}"

        # Field type checks
        assert isinstance(dep_info['name'], str), f"name should be string for {dep_name}"
        assert isinstance(dep_info['version'], str), f"version should be string for {dep_name}"
        assert isinstance(dep_info['path'], str), f"path should be string for {dep_name}"
        assert isinstance(dep_info['requires'], list), f"requires should be list for {dep_name}"
        assert isinstance(dep_info['editable'], bool), f"editable should be bool for {dep_name}"

        print(f"✓ Verified dependency info for {dep_name}")

    print("✓ get_dependencies() works correctly without pkg_resources!")


def test_no_pkg_resources_import():
    """
    Test that our utility module no longer imports pkg_resources.
    """
    import pycomex.util as util_module

    # Check that pkg_resources is not in the module's namespace
    assert not hasattr(util_module, 'pkg_resources'), "pkg_resources should not be imported in util module"

    # Check the source code doesn't contain pkg_resources import
    import inspect
    source = inspect.getsource(util_module)
    assert 'import pkg_resources' not in source, "pkg_resources import should be removed from source"
    assert 'from pkg_resources' not in source, "pkg_resources import should be removed from source"

    print("✓ Confirmed pkg_resources is no longer imported!")


# === COMPREHENSIVE TESTS FOR render_latex_table ===


def test_render_latex_table_mixed_string_int():
    """
    Test render_latex_table with mixed string and integer values in the same table.
    This covers the edge case mentioned by the user.
    """
    table = PrettyTable()
    table.field_names = ["ID", "Name", "Score", "Category"]
    table.add_row([1, "Alice", 95, "Student"])  # Mixed types: int, str, int, str
    table.add_row([2, "Bob", 87, "Student"])
    table.add_row(["N/A", "Charlie", 92, "Alumni"])  # Mixed: str, str, int, str
    table.add_row([4, "Diana", "Incomplete", "Student"])  # Mixed: int, str, str, str

    latex_code = render_latex_table(table)

    # Verify the table contains our expected values
    assert "Alice" in latex_code
    assert "1.00" in latex_code  # Integer 1 should be formatted as float
    assert "95.00" in latex_code  # Integer 95 should be formatted as float
    assert "N/A" in latex_code  # String values should remain as strings
    assert "Incomplete" in latex_code  # String values should remain as strings
    assert "\\begin{tabular}" in latex_code
    assert "\\end{tabular}" in latex_code


def test_render_latex_table_mixed_types_same_column():
    """
    Test render_latex_table with mixed data types in the same column.
    """
    table = PrettyTable()
    table.field_names = ["Mixed Column", "Description"]
    table.add_row([42, "Integer value"])  # Real integer
    table.add_row([3.14, "Float value"])  # Real float
    table.add_row(["Text", "String value"])  # String
    table.add_row([0, "Zero"])  # Integer zero

    latex_code = render_latex_table(table)

    # Check that different types are handled appropriately
    assert "42.00" in latex_code  # Integer formatted as float
    assert "3.14" in latex_code  # Float value
    assert "Text" in latex_code  # String value
    assert "0.00" in latex_code  # Zero formatted as float


def test_render_latex_table_actual_mixed_types():
    """
    Test that the function now properly handles PrettyTable with real mixed types.
    """
    table = PrettyTable()
    table.field_names = ["Mixed", "Description"]
    # Add actual mixed types - this should now work
    table.add_row([42, "Integer input"])  # Real integer
    table.add_row(["text", "String input"])  # String
    table.add_row([3.14159, "Float input"])  # Real float
    table.add_row([True, "Boolean input"])  # Boolean

    # The function should now handle mixed types correctly
    latex_code = render_latex_table(table)

    assert "42.00" in latex_code  # Integer formatted as float
    assert "text" in latex_code
    assert "3.14" in latex_code  # Float formatted
    assert "True" in latex_code  # Boolean converted to string
    assert "Integer input" in latex_code
    assert "String input" in latex_code
    assert "Float input" in latex_code
    assert "Boolean input" in latex_code


def test_render_latex_table_boolean_values():
    """
    Test render_latex_table with actual boolean values.
    """
    table = PrettyTable()
    table.field_names = ["Feature", "Enabled"]
    table.add_row(["Authentication", True])  # Real boolean
    table.add_row(["Logging", False])  # Real boolean
    table.add_row(["Debug Mode", True])  # Real boolean

    latex_code = render_latex_table(table)

    # Boolean values should be converted to strings
    assert "True" in latex_code
    assert "False" in latex_code
    assert "Authentication" in latex_code


def test_render_latex_table_empty_table():
    """
    Test render_latex_table with an empty table (headers only, no rows).
    """
    table = PrettyTable()
    table.field_names = ["Column A", "Column B", "Column C"]
    # No rows added

    latex_code = render_latex_table(table)

    # Should still generate valid LaTeX table structure
    assert "\\begin{tabular}" in latex_code
    assert "\\end{tabular}" in latex_code
    assert "Column A" in latex_code
    assert "Column B" in latex_code
    assert "Column C" in latex_code
    # Should have header structure but no content rows
    assert "\\toprule" in latex_code
    assert "\\midrule" in latex_code
    assert "\\bottomrule" in latex_code


def test_render_latex_table_empty_string_values():
    """
    Test render_latex_table with empty string values.
    """
    table = PrettyTable()
    table.field_names = ["Name", "Value", "Description"]
    table.add_row(["", "123", "Empty name"])
    table.add_row(["Test", "", "Empty value"])
    table.add_row(["", "", "All empty"])
    table.add_row(["Normal", "456", "Normal row"])

    latex_code = render_latex_table(table)

    # Should handle empty strings properly
    assert "Empty name" in latex_code
    assert "Empty value" in latex_code
    assert "All empty" in latex_code
    assert "Normal" in latex_code
    assert "123.00" in latex_code  # Numeric value should be formatted
    assert "456.00" in latex_code


def test_render_latex_table_extreme_numbers():
    """
    Test render_latex_table with very large and very small numbers.
    """
    table = PrettyTable()
    table.field_names = ["Type", "Value"]
    table.add_row(["Very large", 1e15])  # Real float
    table.add_row(["Very small", 1e-10])  # Real float
    table.add_row(["Negative large", -1e12])  # Real float
    table.add_row(["Zero", 0])  # Real integer
    table.add_row(["Infinity string", "inf"])  # String representation
    table.add_row(["Scientific notation", 1.23e-5])  # Real float

    latex_code = render_latex_table(table)

    # Check that extreme numbers are handled
    assert "Very large" in latex_code
    assert "Very small" in latex_code
    assert "Negative large" in latex_code
    assert "0.00" in latex_code  # Zero should be formatted as float
    assert "inf" in latex_code  # String values should remain
    # Scientific notation numbers get formatted to 2 decimal places


def test_render_latex_table_mean_std_variations():
    """
    Test render_latex_table with various mean±std patterns and edge cases.
    """
    table = PrettyTable()
    table.field_names = ["Test Case", "Value"]
    table.add_row(["Standard", "10.5±2.3"])
    table.add_row(["LaTeX format", r"15.2\pm3.1"])
    table.add_row(["No decimal", "20±5"])
    table.add_row(["Negative mean", "-5.5±1.2"])
    table.add_row(["Negative std", "8.0±-0.5"])  # This might be unusual but should work
    table.add_row(["Zero std", "12.0±0.0"])
    table.add_row(["Malformed", "not±valid"])  # Should be treated as string

    latex_code = render_latex_table(table)

    # Check that various mean±std patterns are recognized
    assert "Standard" in latex_code
    assert "LaTeX format" in latex_code
    assert "not±valid" in latex_code  # Malformed should remain as string
    assert "Zero std" in latex_code


def test_render_latex_table_whitespace_handling():
    """
    Test render_latex_table with various whitespace scenarios.
    """
    table = PrettyTable()
    table.field_names = ["Input", "Expected"]
    table.add_row(["  spaced  ", "Should trim"])
    table.add_row([" 123 ", "Number with spaces"])
    table.add_row([" 5.5 ± 1.2 ", "Mean std with spaces"])
    table.add_row(["	tab	", "Tab characters"])

    latex_code = render_latex_table(table)

    # Function should handle whitespace properly via strip() and replace()
    assert "spaced" in latex_code
    assert "Should trim" in latex_code
    assert "123.00" in latex_code  # Numeric value should be detected after stripping
    assert "tab" in latex_code


def test_render_latex_table_special_characters():
    """
    Test render_latex_table with LaTeX special characters that might need escaping.
    Note: The current implementation doesn't perform automatic escaping, but these
    tests document the current behavior and can be updated if escaping is added.
    """
    table = PrettyTable()
    table.field_names = ["Character", "Description"]
    table.add_row(["&", "Ampersand"])
    table.add_row(["%", "Percent"])
    table.add_row(["$", "Dollar"])
    table.add_row(["_", "Underscore"])
    table.add_row(["{", "Left brace"])
    table.add_row(["}", "Right brace"])
    table.add_row(["\\", "Backslash"])
    table.add_row(["#", "Hash"])
    table.add_row(["^", "Caret"])

    latex_code = render_latex_table(table)

    # These characters appear as-is in the current implementation
    # In a production system, these might need to be escaped
    assert "&" in latex_code
    assert "%" in latex_code
    assert "$" in latex_code
    assert "_" in latex_code
    assert "{" in latex_code
    assert "}" in latex_code
    assert "Ampersand" in latex_code
    assert "Percent" in latex_code


def test_render_latex_table_unicode_characters():
    """
    Test render_latex_table with Unicode characters.
    """
    table = PrettyTable()
    table.field_names = ["Symbol", "Name"]
    table.add_row(["α", "Alpha"])
    table.add_row(["β", "Beta"])
    table.add_row(["π", "Pi"])
    table.add_row(["∞", "Infinity"])
    table.add_row(["→", "Arrow"])
    table.add_row(["🚀", "Rocket"])  # Emoji
    table.add_row(["ñ", "N with tilde"])

    latex_code = render_latex_table(table)

    # Unicode characters should be preserved
    assert "α" in latex_code
    assert "β" in latex_code
    assert "π" in latex_code
    assert "∞" in latex_code
    assert "→" in latex_code
    assert "🚀" in latex_code
    assert "ñ" in latex_code
    assert "Alpha" in latex_code


def test_render_latex_table_mathematical_symbols():
    """
    Test render_latex_table with mathematical symbols and expressions.
    """
    table = PrettyTable()
    table.field_names = ["Expression", "Result"]
    table.add_row(["x² + y²", "25"])
    table.add_row(["√16", "4"])
    table.add_row(["∑(1,10)", "55"])
    table.add_row(["≤ 10", "True"])
    table.add_row(["≥ 5", "False"])
    table.add_row(["±3", "Range"])

    latex_code = render_latex_table(table)

    # Mathematical symbols should be preserved
    assert "x² + y²" in latex_code
    assert "√16" in latex_code
    assert "∑(1,10)" in latex_code
    assert "≤ 10" in latex_code
    assert "≥ 5" in latex_code
    assert "25.00" in latex_code  # Numeric result should be formatted


def test_render_latex_table_custom_extract_func():
    """
    Test render_latex_table with a custom extract_func for non-standard string processing.
    """
    table = PrettyTable()
    table.field_names = ["Raw", "Processed"]
    table.add_row(["STATUS:ACTIVE", "Normal"])
    table.add_row(["STATUS:INACTIVE", "Normal"])
    table.add_row(["123", "Normal"])  # This should still be detected as number

    def custom_extract(value):
        """Custom extract function that handles STATUS: prefixed values"""
        if isinstance(value, str) and value.startswith("STATUS:"):
            status = value.split(":")[1]
            return {
                "status": status,
                "string": f"\\textit{{{status.lower()}}}"  # Italicize status
            }
        return {"string": str(value)}

    latex_code = render_latex_table(table, extract_func=custom_extract)

    # Check that custom extraction worked
    assert "\\textit{active}" in latex_code
    assert "\\textit{inactive}" in latex_code
    assert "123.00" in latex_code  # Numbers should still be processed normally
    assert "Normal" in latex_code


def test_render_latex_table_custom_transform_func():
    """
    Test render_latex_table with a custom transform_func for post-processing cells.
    """
    table = PrettyTable()
    table.field_names = ["Value", "Category"]
    table.add_row([95, "High"])  # Real integer
    table.add_row([75, "Medium"])  # Real integer
    table.add_row([45, "Low"])  # Real integer
    table.add_row([100, "Perfect"])  # Real integer

    def custom_transform(cell, rows):
        """Transform function that highlights high values"""
        if "number" in cell:
            if cell["number"] >= 90:
                return {
                    "string": f"\\textbf{{\\textcolor{{green}}{{{cell['number']:.1f}}}}}",
                    "highlight": True
                }
            elif cell["number"] < 50:
                return {
                    "string": f"\\textcolor{{red}}{{{cell['number']:.1f}}}",
                    "lowlight": True
                }
        return {}  # Return empty dict to keep original cell data

    latex_code = render_latex_table(table, transform_func=custom_transform)

    # Check that transformations were applied
    assert "\\textbf{\\textcolor{green}" in latex_code  # High values highlighted
    assert "\\textcolor{red}" in latex_code  # Low values colored red
    assert "High" in latex_code
    assert "Perfect" in latex_code


def test_render_latex_table_combined_custom_functions():
    """
    Test render_latex_table with both custom extract_func and transform_func working together.
    """
    table = PrettyTable()
    table.field_names = ["Input", "Score"]
    table.add_row(["GRADE:A", "95"])
    table.add_row(["GRADE:B", "85"])
    table.add_row(["GRADE:F", "25"])
    table.add_row(["Regular", "75"])

    def custom_extract(value):
        """Extract grade information"""
        if isinstance(value, str) and value.startswith("GRADE:"):
            grade = value.split(":")[1]
            return {"grade": grade, "string": grade}
        return {"string": str(value)}

    def custom_transform(cell, rows):
        """Transform based on grade or score"""
        if "grade" in cell:
            if cell["grade"] in ["A", "B"]:
                return {"string": f"\\textbf{{{cell['grade']}}}", "bold": True}
            elif cell["grade"] == "F":
                return {"string": f"\\textcolor{{red}}{{{cell['grade']}}}", "fail": True}
        elif "number" in cell and cell["number"] >= 90:
            return {"string": f"\\textcolor{{blue}}{{{cell['number']:.0f}}}", "excellent": True}
        return {}

    latex_code = render_latex_table(table, extract_func=custom_extract, transform_func=custom_transform)

    # Check that both functions worked together
    assert "\\textbf{A}" in latex_code  # Grade A should be bold
    assert "\\textbf{B}" in latex_code  # Grade B should be bold
    assert "\\textcolor{red}{F}" in latex_code  # Grade F should be red
    assert "\\textcolor{blue}{95}" in latex_code  # High score should be blue
    assert "Regular" in latex_code


def test_render_latex_table_transform_with_row_context():
    """
    Test render_latex_table transform_func that uses the entire rows context for decisions.
    """
    table = PrettyTable()
    table.field_names = ["Name", "Score1", "Score2"]
    table.add_row(["Alice", "95", "90"])
    table.add_row(["Bob", "85", "88"])
    table.add_row(["Charlie", "92", "94"])

    def context_aware_transform(cell, rows):
        """Transform function that considers all rows to find the highest score"""
        if "number" in cell and cell["col_index"] in [1, 2]:  # Score columns
            # Find the maximum score across all rows for comparison
            all_scores = []
            for row in rows:
                for row_cell in row:
                    if "number" in row_cell and row_cell["col_index"] in [1, 2]:
                        all_scores.append(row_cell["number"])

            max_score = max(all_scores) if all_scores else 0

            # Highlight the maximum score(s)
            if cell["number"] == max_score:
                return {"string": f"\\textbf{{{cell['number']:.0f}}}", "max_score": True}
        return {}

    latex_code = render_latex_table(table, transform_func=context_aware_transform)

    # The highest score (95) should be highlighted
    assert "\\textbf{95}" in latex_code
    assert "Alice" in latex_code
    assert "Bob" in latex_code
    assert "Charlie" in latex_code


def test_render_latex_table_output_structure_validation():
    """
    Test that render_latex_table produces valid LaTeX table structure.
    """
    table = PrettyTable()
    table.field_names = ["A", "B", "C"]
    table.add_row([1, 2, 3])  # Real integers
    table.add_row([4, 5, 6])  # Real integers

    latex_code = render_latex_table(table)

    # Validate basic LaTeX table structure
    assert latex_code.startswith("\\begin{tabular}")
    assert latex_code.endswith("\\end{tabular}")
    assert "\\toprule" in latex_code
    assert "\\midrule" in latex_code
    assert "\\bottomrule" in latex_code

    # Count column specifications
    # Look for the pattern { lll } after \begin{tabular}
    import re
    pattern = r'\\begin\{tabular\}\{\s*([l\s]+)\s*\}'
    match = re.search(pattern, latex_code)
    assert match is not None, "Could not find tabular column specification"
    column_spec = match.group(1)
    # Should have 3 'l' characters for 3 columns
    assert column_spec.count('l') == 3

    # Validate that we have proper row endings (\\)
    lines = latex_code.split('\n')
    row_end_lines = [line for line in lines if line.strip() == '\\\\']
    # Should have row endings: one for header and one for each data row
    expected_row_endings = 1 + len(table._rows)  # header + data rows
    assert len(row_end_lines) >= expected_row_endings, f"Expected at least {expected_row_endings} row endings, found {len(row_end_lines)}"


def test_render_latex_table_malformed_mean_std():
    """
    Test render_latex_table behavior with malformed mean±std patterns.
    """
    table = PrettyTable()
    table.field_names = ["Test", "Value"]
    table.add_row(["Valid", "10.5±2.3"])
    table.add_row(["Missing number", "±2.3"])
    table.add_row(["Missing std", "10.5±"])
    table.add_row(["Double ±", "10.5±2.3±1.1"])
    table.add_row(["Letter in number", "a10.5±2.3"])
    table.add_row(["No numbers", "abc±def"])

    latex_code = render_latex_table(table)

    # Valid pattern should be processed
    assert "Valid" in latex_code

    # Malformed patterns should be treated as strings
    assert "±2.3" in latex_code  # Missing number case
    assert "10.5±" in latex_code  # Missing std case
    assert "abc±def" in latex_code  # No numbers case


def test_render_latex_table_template_parameter_validation():
    """
    Test render_latex_table with different template parameters.
    """
    table = PrettyTable()
    table.field_names = ["Name", "Value"]
    table.add_row(["Test", "123"])

    # Test default template
    latex_code = render_latex_table(table)
    assert "\\begin{tabular}" in latex_code

    # Test with explicit template name (same as default)
    latex_code_explicit = render_latex_table(table, table_template="latex_table.tex.j2")
    assert latex_code_explicit == latex_code


def test_render_latex_table_numeric_precision():
    """
    Test render_latex_table numeric formatting precision.
    """
    table = PrettyTable()
    table.field_names = ["Value", "Description"]
    table.add_row([3.14159, "Pi"])  # Real float
    table.add_row([2.71828, "E"])  # Real float
    table.add_row([1.41421, "Sqrt(2)"])  # Real float
    table.add_row([1, "Integer"])  # Real integer
    table.add_row([0, "Zero"])  # Real integer

    latex_code = render_latex_table(table)

    # Check that numeric values are formatted to 2 decimal places by default
    assert "3.14" in latex_code  # Pi truncated to 2 decimals
    assert "2.72" in latex_code  # E truncated to 2 decimals
    assert "1.41" in latex_code  # Sqrt(2) truncated to 2 decimals
    assert "1.00" in latex_code  # Integer formatted with 2 decimals
    assert "0.00" in latex_code  # Zero formatted with 2 decimals


def test_render_latex_table_edge_case_values():
    """
    Test render_latex_table with edge case numeric values.
    """
    table = PrettyTable()
    table.field_names = ["Type", "Value"]
    table.add_row(["Negative zero", -0.0])  # Real float
    table.add_row(["Very small positive", 1e-100])  # Real float
    table.add_row(["Very small negative", -1e-100])  # Real float
    table.add_row(["Float max", float('inf')])  # Real float infinity
    table.add_row(["Float NaN", float('nan')])  # Real float NaN

    latex_code = render_latex_table(table)

    # Should handle extreme values gracefully
    assert "Negative zero" in latex_code
    assert "Very small positive" in latex_code
    assert "Very small negative" in latex_code
    # inf and nan get converted to strings
    assert "inf" in latex_code
    assert "nan" in latex_code


def test_render_latex_table_column_count_consistency():
    """
    Test that render_latex_table maintains consistent column count across rows.
    """
    table = PrettyTable()
    table.field_names = ["A", "B", "C", "D"]
    table.add_row([1, 2, 3, 4])  # Real integers
    table.add_row(["a", "b", "c", "d"])  # Strings
    table.add_row([10.5, "mixed", "12.3±1.1", 99])  # Mixed types

    latex_code = render_latex_table(table)

    # Verify column structure by counting ampersands in data section
    lines = latex_code.split('\n')
    # Find content rows (after \midrule but before \bottomrule)
    in_content = False
    ampersand_lines = []
    for line in lines:
        if '\\midrule' in line:
            in_content = True
            continue
        if '\\bottomrule' in line:
            break
        if in_content and '&' in line and not line.strip().startswith('%'):
            ampersand_lines.append(line)

    # Count total ampersands in content section
    # For a 4-column table with 3 rows, we expect:
    # Row 1: 3 ampersands (4 cells = 3 separators)
    # Row 2: 3 ampersands (4 cells = 3 separators)
    # Total: 6 ampersands in content section
    total_ampersands = sum(line.count('&') for line in ampersand_lines)

    # We have 3 data rows (including headers), each with 3 ampersands
    expected_ampersands = 3 * 3  # 3 rows × 3 ampersands per row
    assert total_ampersands == expected_ampersands, f"Expected {expected_ampersands} ampersands total, found {total_ampersands}"
