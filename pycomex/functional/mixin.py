"""
Experiment Mixin System for PyComex.

This module provides the ExperimentMixin class, which allows for creating reusable
hook implementations that can be shared across multiple experiments without code
duplication. Unlike Experiment objects, mixins cannot be executed standalone - they
only provide hooks and optional parameter defaults.

Example:

.. code-block:: python

    # experiment_mixin.py
    from pycomex.functional.mixin import ExperimentMixin

    mixin = ExperimentMixin(glob=globals())

    @mixin.hook("before_run")
    def before_run(e):
        e.log("Mixin hook executed!")

    # sub_experiment.py
    from pycomex import Experiment
    from pycomex.utils import folder_path, file_namespace

    experiment = Experiment.extend(
        'base_experiment.py',
        base_path=folder_path(__file__),
        namespace=file_namespace(__file__),
        glob=globals(),
    )
    experiment.include('experiment_mixin.py')
"""

import os
import typing as t
from collections import defaultdict
from collections.abc import Callable

from pycomex.functional.base import ExperimentBase
from pycomex.utils import dynamic_import


class ExperimentMixin(ExperimentBase):
    """
    A mixin class that provides reusable hook implementations for experiments.

    ExperimentMixins are lightweight modules that bundle generic hook implementations
    which can be shared across multiple experiments. Unlike Experiment objects, mixins:

    - Cannot be executed standalone (no base_path, namespace, or execution methods)
    - Provide reusable hook implementations via the hook() decorator
    - Can optionally define parameter defaults (CAPS global variables)
    - Support composition - multiple mixins can be included in one experiment

    The main use case for mixins is to avoid code duplication when the same hook
    implementation is needed across different experiments. For example, a logging
    mixin, a notification mixin, or a data preprocessing mixin.

    Example:

    .. code-block:: python

        # Define a mixin
        from pycomex.functional.mixin import ExperimentMixin

        mixin = ExperimentMixin(glob=globals())

        @mixin.hook("before_run")
        def setup_logging(e):
            e.log("Enhanced logging enabled via mixin")

        # Use in an experiment
        experiment = Experiment.extend(...)
        experiment.include('my_mixin.py')

    :param glob: The globals() dictionary from the mixin module. This is used to
        discover parameters (uppercase global variables) defined in the mixin.
    """

    # Class attributes for hook system defaults (used by ExperimentBase)
    _HOOK_REPLACE_DEFAULT = False
    _HOOK_DEFAULT_DEFAULT = False

    def __init__(self, glob: dict) -> None:
        """
        Initialize an ExperimentMixin instance.

        :param glob: The globals() dictionary from the mixin module
        """
        # Initialize base class (sets up glob, parameters, hook_map)
        super().__init__(glob)

        # Discover any parameters (CAPS variables) defined in the mixin module
        self._discover_parameters()

        # Store reference to self in globals for discovery
        self._register_in_globals("__mixin__")

    # Note: _discover_parameters() and hook() methods are now inherited from ExperimentBase

    @classmethod
    def import_from(
        cls,
        mixin_path: str,
        glob: dict,
    ) -> "ExperimentMixin":
        """
        Import an ExperimentMixin from a Python module file.

        This method dynamically imports a mixin module and returns the ExperimentMixin
        instance defined within it. The method handles both relative and absolute paths.

        Example:

        .. code-block:: python

            mixin = ExperimentMixin.import_from('my_mixin.py', globals())

        :param mixin_path: The relative or absolute path to the mixin module file
        :param glob: The globals() dictionary from the calling module. Used to resolve
            relative paths.

        :returns: The ExperimentMixin instance from the imported module

        :raises AssertionError: If no ExperimentMixin object is found in the module
        :raises FileNotFoundError: If the mixin file cannot be found
        :raises ImportError: If the module cannot be imported
        """
        # Try to import the module, handling both absolute and relative paths
        try:
            module = dynamic_import(mixin_path)
        except (FileNotFoundError, ImportError):
            # If direct import fails, try relative to the calling module
            parent_path = os.path.dirname(glob["__file__"])
            mixin_path = os.path.join(parent_path, *os.path.split(mixin_path))
            module = dynamic_import(mixin_path)

        # Look for the ExperimentMixin instance in the module
        # We first check for the __mixin__ magic attribute that gets set in __init__
        if hasattr(module, "__mixin__"):
            return module.__mixin__

        # Fall back to scanning all module attributes
        mixin = None
        for key in dir(module):
            value = getattr(module, key)
            if isinstance(value, ExperimentMixin):
                mixin = value
                break

        assert (
            mixin is not None
        ), f'No ExperimentMixin object could be found in the module @ {mixin_path}'

        return mixin
