"""
Utility functions for the CLI.
"""

from pycomex.utils import TEMPLATE_ENV


def section(string: str, length: int, padding: int = 2):
    """
    Create a section header with the given string centered between equals signs.

    :param string: The text to display in the section header
    :param length: The total width of the section header
    :param padding: The padding around the text

    :return: A formatted section header string
    """
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
    """
    Create a subsection header with the given string centered between dashes.

    :param string: The text to display in the subsection header
    :param length: The total width of the subsection header
    :param padding: The padding around the text

    :return: A formatted subsection header string
    """
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


# Register the helper functions with the template environment
TEMPLATE_ENV.globals.update(
    {
        "section": section,
        "subsection": subsection,
    }
)
