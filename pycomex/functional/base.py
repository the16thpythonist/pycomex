"""
Base classes for PyComex experiments.

This module provides the ExperimentBase class, which serves as the foundation for
both full Experiment objects and lightweight ExperimentMixin objects. It abstracts
common functionality including parameter discovery, hook registration and execution,
and module globals management.

The base class design enables code reuse while allowing subclasses to customize
behavior through class attributes and method overrides.
"""

import typing as t
from collections import defaultdict
from collections.abc import Callable


class ExperimentBase:
    """
    Base class providing common functionality for Experiment and ExperimentMixin.

    This class abstracts the shared infrastructure needed by both full computational
    experiments (Experiment class) and reusable hook containers (ExperimentMixin class).
    By consolidating this common functionality, we avoid code duplication and ensure
    consistent behavior across the experiment system.

    The base class handles three core responsibilities:

    1. **Parameter Discovery**: Automatically identifies experiment parameters by
       scanning the module's global variables for uppercase names (e.g., LEARNING_RATE,
       BATCH_SIZE). This convention-based approach eliminates boilerplate configuration.

    2. **Hook System**: Provides a flexible callback mechanism where functions can be
       registered to execute at specific lifecycle points. Hooks enable extending
       experiment behavior without modifying core code.

    3. **Module Integration**: Manages the relationship between the Python runtime
       object and its source module, including self-registration in the module's
       globals dictionary for discovery.

    Subclasses customize behavior through class attributes:

    - ``_HOOK_REPLACE_DEFAULT``: Default value for the ``replace`` parameter in hook()
    - ``_HOOK_DEFAULT_DEFAULT``: Default value for the ``default`` parameter in hook()
    - ``_GLOBALS_REGISTRATION_KEY``: Key used for self-registration (e.g., "__experiment__")

    Design Rationale:
        The decision to use a base class rather than composition or mixins (the irony!)
        was driven by the need for true inheritance and the ability to use isinstance()
        checks. The hook system and parameter discovery are fundamental to the identity
        of experiment objects, not just added capabilities.

    Example:

    .. code-block:: python

        # Subclasses inherit and customize
        class MyExperiment(ExperimentBase):
            _HOOK_REPLACE_DEFAULT = True
            _HOOK_DEFAULT_DEFAULT = True
            _GLOBALS_REGISTRATION_KEY = "__experiment__"

            def __init__(self, base_path, namespace, glob, **kwargs):
                super().__init__(glob)
                # ... additional initialization

    :param glob: The globals() dictionary from the module. This provides access to
        the module's namespace for parameter discovery and self-registration.
    """

    # Class attributes that subclasses should override to customize behavior
    _HOOK_REPLACE_DEFAULT: bool = False
    _HOOK_DEFAULT_DEFAULT: bool = False
    _GLOBALS_REGISTRATION_KEY: t.Optional[str] = None

    def __init__(self, glob: dict) -> None:
        """
        Initialize the base experiment object.

        This method sets up the core data structures needed by all experiment-like
        objects: the module globals reference, the parameters dictionary, and the
        hook registry. These form the foundation upon which subclasses build their
        specialized functionality.

        :param glob: The globals() dictionary from the module. This is typically
            passed as globals() from the calling module.

        :returns: None
        """
        self.glob = glob
        self.parameters: dict = {}
        self.hook_map: dict[str, list[Callable]] = defaultdict(list)

    def _discover_parameters(self) -> None:
        """
        Discover experiment parameters from the module's global variables.

        This method implements the convention-based parameter discovery mechanism
        that is central to PyComex's design philosophy. By scanning the module's
        globals for uppercase variable names, we can automatically identify
        experiment parameters without requiring explicit configuration.

        The convention is simple: any variable name that is entirely uppercase
        (e.g., LEARNING_RATE, NUM_EPOCHS, BATCH_SIZE) is considered a parameter
        and will be:

        1. Stored in the ``self.parameters`` dictionary
        2. Accessible via dot notation (e.g., ``experiment.LEARNING_RATE``)
        3. Included in experiment metadata and archives
        4. Overridable via command-line arguments (in Experiment subclass)

        This approach reduces boilerplate and makes experiment parameters
        immediately visible in the module's global scope, improving code
        readability.

        Design Note:
            We iterate through ``self.glob.items()`` rather than accessing
            ``__annotations__`` because parameters may be defined without type
            hints, and we want to discover them regardless of whether they're
            annotated. Type information is gathered separately through inspection
            in the Experiment class.

        :returns: None
        """
        for name, value in self.glob.items():
            if name.isupper():
                self.parameters[name] = value

    def hook(
        self,
        name: str,
        replace: t.Optional[bool] = None,
        default: t.Optional[bool] = None,
    ):
        """
        Register a function as a hook callback for the given hook name.

        The hook system is PyComex's primary extension mechanism, allowing custom
        behavior to be injected at specific lifecycle points without modifying
        core code. Hooks are particularly useful for:

        - Adding logging or monitoring
        - Sending notifications
        - Implementing testing mode overrides
        - Customizing experiment initialization/finalization
        - Integrating with external systems (e.g., Weights & Biases)

        This method returns a decorator that registers the decorated function as
        a callback for the specified hook name. When the hook is later executed
        via ``apply_hook()``, all registered callbacks are invoked in order.

        The behavior can be customized with two parameters:

        **replace**: If True, this hook replaces any previously registered hooks
        with the same name. If False, it appends to the list, allowing multiple
        hooks to execute in sequence. This is useful for composing behavior
        across base experiments and sub-experiments.

        **default**: If True, this hook only registers if no other hook with
        this name exists yet. This provides fallback behavior - useful for
        defining default implementations in base classes that can be overridden
        by subclasses.

        If ``replace`` or ``default`` are not provided, they default to class
        attributes ``_HOOK_REPLACE_DEFAULT`` and ``_HOOK_DEFAULT_DEFAULT``,
        allowing subclasses to set appropriate defaults.

        Hook Callback Signature:
            All hook callbacks receive the experiment object as their first
            positional argument, followed by any keyword arguments passed
            to ``apply_hook()``:

            .. code-block:: python

                @experiment.hook("before_run")
                def my_hook(e: Experiment, **kwargs):
                    e.log("Hook executing!")

        Example:

        .. code-block:: python

            @experiment.hook("before_run")
            def setup_logging(e):
                e.log("Experiment starting!")

            @experiment.hook("after_run", replace=False)
            def cleanup(e):
                e.log("Experiment finished!")

        :param name: The unique string identifier for this hook. Common hook names
            include "before_run", "after_run", "before_testing", etc.
        :param replace: If True, replace any existing hooks with this name. If False,
            append to existing hooks. If None, uses ``_HOOK_REPLACE_DEFAULT``.
        :param default: If True, only register if no hook exists for this name. If False,
            register regardless. If None, uses ``_HOOK_DEFAULT_DEFAULT``.

        :returns: A decorator function that registers the decorated function as a hook callback.
        """
        # Use class defaults if not explicitly provided
        if replace is None:
            replace = self._HOOK_REPLACE_DEFAULT
        if default is None:
            default = self._HOOK_DEFAULT_DEFAULT

        def decorator(func, *args, **kwargs):
            # Skip registration if default=True and hook already exists
            if default and name in self.hook_map:
                return func

            if replace:
                # Replace all existing hooks with this one
                self.hook_map[name] = [func]
            else:
                # Append to existing hooks
                self.hook_map[name].append(func)

            return func

        return decorator

    def apply_hook(
        self, name: str, default: t.Optional[t.Any] = None, **kwargs
    ) -> t.Any:
        """
        Execute all registered hook callbacks for the given hook name.

        This method is the counterpart to ``hook()`` - while ``hook()`` registers
        callbacks, ``apply_hook()`` executes them. When called, it iterates through
        all callbacks registered for the specified hook name and invokes them in
        the order they were registered.

        Each callback receives:
        1. The experiment object (self) as the first positional argument
        2. Any keyword arguments passed to apply_hook()

        The return value of the last executed callback is returned by apply_hook().
        If no callbacks are registered for the given hook name, the ``default``
        value is returned instead.

        This execution model enables several patterns:

        - **Sequential Processing**: Multiple hooks can be chained, each processing
          results from the previous one
        - **Side Effects**: Hooks can perform actions (logging, notifications) without
          returning values
        - **Value Transformation**: Hooks can modify and return data that subsequent
          hooks or the experiment itself will use

        Example:

        .. code-block:: python

            # Register hooks
            @experiment.hook("before_run")
            def log_start(e):
                e.log("Starting experiment")
                return "initialized"

            @experiment.hook("before_run", replace=False)
            def check_deps(e):
                e.log("Checking dependencies")
                return "ready"

            # Execute hooks
            result = experiment.apply_hook("before_run")
            # Both hooks execute in order
            # result == "ready" (return value of last hook)

        :param name: The unique string identifier of the hook to execute
        :param default: The default value to return if no hook callbacks are
            registered for this hook name. Defaults to None.
        :param kwargs: Arbitrary keyword arguments to pass to all hook callbacks

        :returns: The return value of the last executed hook callback, or the
            default value if no callbacks were registered.
        """
        result = default

        if name in self.hook_map:
            for func in self.hook_map[name]:
                result = func(self, **kwargs)

        return result

    def _register_in_globals(self, key: str) -> None:
        """
        Register this instance in the module's globals dictionary.

        This method implements the self-registration pattern used throughout PyComex
        to enable discovery of experiment objects within their defining modules.
        By adding the instance to the module's globals with a well-known key
        (e.g., "__experiment__" or "__mixin__"), we can later import the module
        and reliably find the experiment object without knowing the variable name
        the user chose.

        This is particularly important for:

        - The CLI discovering experiments to run
        - The ``import_from()`` classmethod finding experiments in modules
        - The ``extend()`` mechanism locating base experiments
        - The mixin ``include()`` system finding mixin objects

        The key used for registration is typically a "magic" double-underscore name
        like "__experiment__" or "__mixin__", which by convention indicates that
        it's set by the framework rather than the user.

        Subclasses should call this method during initialization with their
        appropriate registration key.

        Example:

        .. code-block:: python

            class Experiment(ExperimentBase):
                def __init__(self, ...):
                    super().__init__(glob)
                    self._register_in_globals("__experiment__")

        :param key: The string key to use for registration in the globals
            dictionary. Common values include "__experiment__" for Experiment
            instances and "__mixin__" for ExperimentMixin instances.

        :returns: None
        """
        self.glob[key] = self

    def merge_hook_map(
        self, source_hook_map: dict[str, list[Callable]], replace_behavior: bool = False
    ) -> None:
        """
        Merge hooks from another hook map into this object's hook map.

        This method provides intelligent hook merging that respects hook semantics.
        When merging hooks from mixins or base experiments, we need to handle the
        `replace` flag correctly to ensure proper hook execution order and behavior.

        The merging strategy considers hook metadata if available to determine whether
        a hook should replace existing hooks or append to them. This is particularly
        useful when including mixins that define hooks with specific replacement
        semantics.

        Merging Rules:
        1. If `replace_behavior` is True (default for including mixins with explicit
           replace semantics), hooks from the source will replace existing hooks with
           the same name
        2. If `replace_behavior` is False (default for normal composition), hooks are
           appended to maintain execution order
        3. Empty hook lists in the source are skipped to avoid clearing existing hooks

        This method is primarily used by:
        - The ``include()`` method when merging mixin hooks into experiments
        - The ``extend()`` method when composing experiment hierarchies

        Design Rationale:
            Proper hook merging is essential for maintainable experiment composition.
            Without respecting the `replace` flag, mixins cannot properly override
            base behavior, and experiments cannot control hook execution order. This
            method centralizes the merging logic to ensure consistent behavior across
            the entire experiment system.

        Example:

        .. code-block:: python

            # In Experiment.include() - merge mixin hooks
            mixin = ExperimentMixin.import_from('my_mixin.py', self.glob)
            self.merge_hook_map(mixin.hook_map, replace_behavior=False)

            # In a mixin with replace semantics
            @mixin.hook("before_run", replace=True)
            def override_setup(e):
                e.log("This replaces the base setup")

        :param source_hook_map: The hook map dictionary to merge from. This should
            be in the same format as self.hook_map: {hook_name: [callbacks]}
        :param replace_behavior: If True, hooks from source will replace existing
            hooks with the same name. If False, they will be appended.

        :returns: None
        """
        for hook_name, hook_funcs in source_hook_map.items():
            # Skip empty hook lists
            if not hook_funcs:
                continue

            if replace_behavior:
                # Replace mode: source hooks replace existing hooks entirely
                self.hook_map[hook_name] = list(hook_funcs)
            else:
                # Append mode: source hooks are added to existing hooks
                # This maintains execution order: existing hooks run first,
                # then newly merged hooks
                self.hook_map[hook_name].extend(hook_funcs)
