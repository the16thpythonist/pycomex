"""Utility classes used to implement the plugin system.

This module implements a very small plugin architecture which can be used to
extend the behaviour of an experiment by registering hook functions.  The hooks
are stored in an instance of :class:`PluginManager` which allows functions to be
registered under a specific hook name together with a priority.  When the hook
is applied all registered functions are executed in order of their priority.

The :class:`Plugin` base class offers a convenience wrapper around this system
and allows plugin implementations to simply define methods decorated with the
provided :func:`hook` decorator.  When such a plugin is instantiated the
``register`` method can be used to automatically register all hook methods with
the plugin manager.
"""

import os
from collections import defaultdict


def hook(hook_name: str, priority: int = 0) -> callable:
    """Decorator for marking a function as a hook.

    The returned decorator attaches the ``hook_name`` and ``priority`` attributes
    to the decorated function which allows the :class:`PluginManager` to
    recognise it as a hook implementation.  The decorated function itself is
    returned unmodified.

    :param hook_name: name of the hook under which the function should be
        registered.
    :param priority: optional priority value used when multiple functions are
        registered for the same hook.

    :returns: the original function with hook meta data attached.
    """

    def decorator(function: callable):

        function.__hook__ = hook_name
        function.__priority__ = priority
        return function

    return decorator


class StopHook(Exception):
    """Exception used to abort a hook chain.

    When raised from within a hook implementation the execution of the remaining
    hooks of the same name will be stopped.  The ``value`` of this exception will
    be returned by :meth:`PluginManager.apply_hook`.
    """

    def __init__(self, value, *args, **kwargs):
        self.value = value
        super().__init__(*args, **kwargs)


class Plugin:
    """Base class for all plugins.

    A plugin is constructed with a reference to the global configuration object
    which in turn contains the :class:`PluginManager`.  Derived classes simply
    implement methods decorated with :func:`hook` and then call ``register`` to
    register those methods with the manager.
    """

    def __init__(self, config: object, *args, **kwargs):
        """Create a new plugin instance.

        :param config: configuration object holding the plugin manager.
        """
        self.config = config

    def register(self) -> None:
        """Register all hook methods of this plugin."""

        for attribute_name in dir(self):
            attribute = getattr(self, attribute_name)
            if callable(attribute) and hasattr(attribute, "__hook__"):
                function = attribute
                self.config.pm.register_hook(
                    attribute.__hook__,
                    function,
                    attribute.__priority__,
                )

    def unregister(self) -> None:
        """Placeholder for unregistering hooks (not yet implemented)."""
        pass


class PluginManager:
    """Manager responsible for storing and executing hooks."""

    def __init__(self, config: object):
        """Create a new manager instance.

        :param config: configuration instance that will be forwarded to hook
            functions when they are executed.
        """
        self.config = config
        self.hooks: dict[str, list[callable]] = defaultdict(list)

    def hook(self, hook_name: str, priority: int = 0):
        """Return a decorator that registers a function as a hook."""

        def decorator(function):
            self.register_hook(hook_name, function, priority)
            return function

        return decorator

    def register_hook(
        self,
        hook_name: str,
        function: callable,
        priority: int = 0,
    ) -> None:
        """Register ``function`` under ``hook_name`` with optional priority."""

        # Mark the function so that it can be discovered automatically when
        # iterating over attributes of a plugin instance.
        if not hasattr(function, "__hook__"):
            function.__hook__ = hook_name

        if not hasattr(function, "__priority__"):
            function.__priority__ = priority

        # Store the function in the internal mapping for later execution.
        self.hooks[hook_name].append(function)

    def apply_hook(
        self,
        hook_name: str,
        **kwargs,
    ) -> None:
        """Execute all functions registered for ``hook_name``."""

        result = None
        # Execute all registered functions ordered by their priority.  A higher
        # priority value means the function is executed earlier.
        for func in sorted(
            self.hooks[hook_name],
            key=lambda x: x.__priority__,
            reverse=True,
        ):
            try:
                result = func(self.config, **kwargs)
            except StopHook as stop:
                result = stop.value
                break

        return result

    def __len__(self) -> int:
        """
        The length of the plugin manager is defined as the total number of hook callables that are
        currently registered with some hook name.
        """
        return sum([len(hooks) for hook_name, hooks in self.hooks.items()])
