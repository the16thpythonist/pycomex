# Guide for AI Agents

## Overview

This project implements a microframework for defining and executing computational experiments using Python.
It is designed around the idea of representing experiments as individual python modules which can be executed independently. 
Inside each module a main experiment function is decorated with an instance of the Experiment class which will then 
handle a lot of the common operations such as the logging, storing the artifacts etc.

## Project Structure

- `/pycomex`: Python source files
    - `/pycomex/functional`: Source files for the new functional interface to the pycomex library
    - `/pycomex/examples`: Series of example modules which demonstrate the usage of the pycomex library to define 
    computational experiments.
    - `/pycomex/plugins`: Folders which implement the default plugins for the pycomex library that come shipped with the library itself.
    - `/pycomex/templates`: Jinja2 templates for various purposes such as plain strings or HTML strings.
- `/tests`: Pytest unit tests which are names "tests_" plus the name of the source python file
    - `/tests/assets`: Additional files etc. which are needed by some of the unittests
    - `/tests/artifacts`: Temp folder in which the tests save their results 

## Documentation

**General.** Type hints should be used wherever possible.
Every function/method should be properly documented by a Docstring using the **ReStructuredText** documentation style.
The doc strings should start with a brief summary of the function, followed by the parameters as illustrated by the example below. If necessary, the docstring may also include additional sections such as "Examples" or "Notes".

```python
def multiply(a: float, b: float) -> float:
    """
    Returns the product of ``a`` and ``b``.

    Example
    -------
    >>> multiply(2.0, 3.0)
    6.0

    :param a: first float input value
    :param b: second float input value
    
    :returns: The float result
    """
    return a * b
```

## Code Convention

1. functions with many parameters should be split like this:

```python
def function(arg1: List[int],
             arg2: List[float],
             **kwargs
             ) -> float:
    # ...

```

2. Strings that appear inside the code should use single quotes instead of double quotes, e.g. `'this is a string'`.

## Testing

Unittests use `pytest` in the `/tests` folder with this command

```bash
pytest -q -m "not localonly"
```

## Pull Requests / Contributing

Pull Requests should always start with a small summary of the changes and a list of the changed files.
Additionally a PR should contain a small summary of the tests results.