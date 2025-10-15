"""
Environment variable interpolation for PyComex configuration files.

This module provides utilities to interpolate environment variables into YAML
configuration files using the ${VAR} and ${VAR:-default} syntax.

Example:

.. code-block:: yaml

    extend: training.py
    parameters:
      DATA_PATH: ${DATA_ROOT}/experiments/data
      API_KEY: ${OPENAI_API_KEY}
      BATCH_SIZE: ${BATCH_SIZE:-32}  # defaults to 32 if not set

The interpolation happens before the config is parsed into an ExperimentConfig
object, allowing environment variables to be used in any string field.
"""

import os
import re
from typing import Any


class ConfigInterpolationError(Exception):
    """
    Exception raised when environment variable interpolation fails.

    This typically occurs when a required environment variable is not set
    and no default value is provided.
    """

    pass


def parse_env_var_reference(s: str) -> tuple[str, str | None]:
    """
    Parse an environment variable reference from ${VAR} or ${VAR:-default} syntax.

    This function extracts the variable name and optional default value from
    a string that contains an environment variable reference.

    Example:

    .. code-block:: python

        parse_env_var_reference("${HOME}")
        # Returns: ("HOME", None)

        parse_env_var_reference("${PORT:-8080}")
        # Returns: ("PORT", "8080")

    :param s: The string containing the environment variable reference

    :returns: A tuple of (variable_name, default_value). default_value is None
        if no default was specified.

    :raises ConfigInterpolationError: If the string doesn't match the expected format
    """
    # Pattern: ${VAR} or ${VAR:-default}
    # VAR must start with letter or underscore, followed by alphanumerics/underscores
    pattern = r'^\$\{([A-Za-z_][A-Za-z0-9_]*?)(?::-(.*?))?\}$'
    match = re.match(pattern, s)

    if not match:
        raise ConfigInterpolationError(
            f'Invalid environment variable reference format: "{s}". '
            f'Expected format: ${{VAR}} or ${{VAR:-default}}'
        )

    var_name = match.group(1)
    default_value = match.group(2) if match.group(2) is not None else None

    return var_name, default_value


def interpolate_string(s: str) -> str:
    """
    Interpolate environment variables in a single string.

    This function finds all ${VAR} and ${VAR:-default} references in a string
    and replaces them with the corresponding environment variable values.

    Supports:
    - ${VAR}: Replace with env var value, error if not set
    - ${VAR:-default}: Replace with env var value, or default if not set
    - $$: Escape sequence that becomes a single $ (not interpolated)

    Example:

    .. code-block:: python

        os.environ['HOME'] = '/home/user'
        interpolate_string("Path: ${HOME}/data")
        # Returns: "Path: /home/user/data"

        interpolate_string("Port: ${PORT:-8080}")
        # Returns: "Port: 8080" (if PORT not set)

        interpolate_string("Price: $$50")
        # Returns: "Price: $50"

    :param s: The string to interpolate

    :returns: The string with environment variables interpolated

    :raises ConfigInterpolationError: If a required environment variable is not set
    """
    if not isinstance(s, str):
        return s

    # First, handle escape sequences $$ -> temporary marker
    # We use a placeholder that's unlikely to appear in user strings
    ESCAPE_MARKER = "\x00DOLLAR_ESCAPE\x00"
    s = s.replace("$$", ESCAPE_MARKER)

    # Pattern to match ${VAR} or ${VAR:-default}
    pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*?)(?::-(.*?))?\}'

    def replacer(match):
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else None

        # Try to get the environment variable
        value = os.environ.get(var_name)

        if value is not None:
            return value
        elif default_value is not None:
            return default_value
        else:
            # Environment variable not set and no default provided
            raise ConfigInterpolationError(
                f'Environment variable "${var_name}" is not set and no default value provided. '
                f'Either set the environment variable or use ${{{var_name}:-default}} syntax.'
            )

    # Replace all environment variable references
    result = re.sub(pattern, replacer, s)

    # Replace escape markers back to single dollar signs
    result = result.replace(ESCAPE_MARKER, "$")

    return result


def interpolate_env_vars(data: Any) -> Any:
    """
    Recursively interpolate environment variables in a data structure.

    This function traverses dictionaries, lists, and other data structures,
    interpolating environment variables in any string values it encounters.

    Non-string values are left unchanged. This allows the function to be
    applied to the entire parsed YAML config before validation.

    Example:

    .. code-block:: python

        os.environ['DATA_PATH'] = '/mnt/data'
        os.environ['BATCH_SIZE'] = '64'

        config = {
            'extend': '${DATA_PATH}/experiment.py',
            'parameters': {
                'BATCH_SIZE': '${BATCH_SIZE}',
                'LEARNING_RATE': 0.001,  # Not a string, left unchanged
                'NESTED': {
                    'PATH': '${DATA_PATH}/nested'
                }
            }
        }

        result = interpolate_env_vars(config)
        # result['extend'] == '/mnt/data/experiment.py'
        # result['parameters']['BATCH_SIZE'] == '64'
        # result['parameters']['LEARNING_RATE'] == 0.001
        # result['parameters']['NESTED']['PATH'] == '/mnt/data/nested'

    :param data: The data structure to interpolate. Can be dict, list, str, or any other type.

    :returns: The data structure with all string values interpolated

    :raises ConfigInterpolationError: If a required environment variable is not set
    """
    if isinstance(data, dict):
        # Recursively interpolate all values in the dictionary
        return {key: interpolate_env_vars(value) for key, value in data.items()}

    elif isinstance(data, list):
        # Recursively interpolate all items in the list
        return [interpolate_env_vars(item) for item in data]

    elif isinstance(data, str):
        # Interpolate environment variables in the string
        return interpolate_string(data)

    else:
        # For all other types (int, float, bool, None, etc.), return as-is
        return data
