"""
Sentinel and supporting classes for explicit parameter inheritance in sub-experiments.

When extending a parent experiment with ``Experiment.extend()``, a sub-experiment
can use the ``INHERIT`` sentinel to explicitly carry forward a parent's parameter
value, optionally applying a transformation function.

Example:

.. code-block:: python

    from pycomex import INHERIT

    PARAM_A = INHERIT                        # use parent's value as-is
    PARAM_B = INHERIT(lambda x: x * 2)      # use parent's value, doubled
    PARAM_C = "completely_new"               # override parent (existing behavior)

**Lifecycle overview:**

The INHERIT system hooks into the experiment parameter lifecycle at three points:

1. **Discovery** (``_discover_parameters``): Uppercase globals are scanned from the
   module's ``glob`` dict. Both ``PARAM = INHERIT`` and ``PARAM = INHERIT(fn)``
   end up in ``self.parameters`` as ``InheritBase`` instances.

2. **Processing** (``_process_inherited_parameters``): Called right after discovery
   in ``update_parameters()``. Converts bare ``INHERIT`` sentinels into ``Inherit``
   instances and captures the parent's parameter value (snapshotted *before*
   discovery overwrote it) into each ``Inherit`` object.

3. **Resolution** (``_resolve_inherited_parameters``): Called at the start of
   ``initialize()`` (i.e., when the experiment is about to run). Each ``Inherit``
   object is replaced with the concrete value returned by ``resolve()``. After
   this point, the parameter dict contains only plain values and the experiment
   proceeds normally.

**Design Rationale — why a separate singleton and value class:**

We separate the sentinel singleton (``_InheritSentinel``) from the value-carrying
object (``Inherit``) because:

- The singleton ``INHERIT`` is a module-level constant that users import and assign
  to parameters. It is shared across *all* parameters that use bare ``PARAM = INHERIT``.
  It cannot carry per-parameter state (like a specific parent value) because multiple
  parameters would overwrite each other.

- ``Inherit`` instances carry per-parameter state: the transform function and the
  captured parent value. Each ``PARAM = INHERIT(fn)`` call creates a fresh ``Inherit``
  instance. For bare ``PARAM = INHERIT``, ``_process_inherited_parameters`` converts
  the sentinel into a fresh ``Inherit(transform=None)`` instance so that per-parameter
  state can be attached.

Both share a common base class ``InheritBase`` so that all INHERIT-related objects
can be detected with a single ``isinstance(value, InheritBase)`` check.

**The import artifact problem:**

Because ``INHERIT`` is an uppercase name, ``from pycomex import INHERIT`` causes
the ``INHERIT`` variable itself to appear in the module's globals. Since PyComex
discovers parameters by scanning for uppercase global names, ``INHERIT`` gets
erroneously treated as a parameter. This is handled in two places:

- ``_process_inherited_parameters``: detects import artifacts via identity checks
  (the same ``InheritBase`` object in both parent and child parameters) and removes
  them from the parameters dict.

- ``_resolve_inherited_parameters``: as a second line of defense, removes any
  ``Inherit`` object whose ``parent_value`` is still ``_UNSET`` and which was NOT
  created from a user sentinel (i.e., lacking the ``_from_sentinel`` marker).

See the inline comments in ``experiment.py`` for the full explanation of this
mechanism.
"""
import typing as t


# Internal sentinel to distinguish "no parent value was captured" from a legitimate
# None parent value. We use object identity (``is _UNSET``) for the check, so
# this must be a unique object that nothing else can reference.
_UNSET = object()


class InheritBase:
    """
    Common base class for INHERIT-related objects.

    This exists solely so that ``isinstance(value, InheritBase)`` can detect
    both the bare ``INHERIT`` sentinel and ``Inherit`` instances carrying
    transforms. Code that needs to check whether a value is an unresolved
    inherited parameter should use ``isinstance(value, InheritBase)``.
    """
    pass


class InheritError(Exception):
    """
    Raised when an INHERIT parameter cannot be resolved.

    Common causes:

    - INHERIT used for a parameter name that does not exist in the parent experiment.
    - INHERIT used in a direct experiment (not created via ``Experiment.extend()``).
    """
    pass


class Inherit(InheritBase):
    """
    Carries the state for a single inherited parameter: an optional transform
    function and the captured parent value.

    Instances are created in two ways:

    1. By ``_InheritSentinel.__call__()`` when the user writes ``INHERIT(fn)``
    2. By ``Experiment._process_inherited_parameters()`` when it converts the
       bare ``INHERIT`` sentinel into ``Inherit(transform=None)``

    The ``parent_value`` attribute is populated during ``update_parameters()``
    by snapshotting the parent's parameter value before it gets overwritten
    by ``_discover_parameters()``.

    :param transform: An optional callable that takes the parent value and
        returns the derived value. If ``None``, the parent value is used as-is.
    :param name: The parameter name this instance is bound to. Set during
        ``_process_inherited_parameters()`` and used in error messages.
    """

    def __init__(self, transform: t.Optional[t.Callable] = None, name: t.Optional[str] = None):
        self.transform = transform
        self.name: t.Optional[str] = name
        self.parent_value: t.Any = _UNSET

    def resolve(self) -> t.Any:
        """
        Resolve this inherited parameter to its concrete value.

        If the parent value is itself an ``InheritBase`` instance (which happens
        in multi-level inheritance chains like Base -> Child -> Grandchild where
        both Child and Grandchild use INHERIT), it is resolved recursively first.
        Then, if a transform function was provided, it is applied to the
        resolved parent value.

        Example of a multi-level chain::

            Base:       PARAM = 10
            Child:      PARAM = INHERIT(lambda x: x * 2)   -> Inherit(parent_value=10)
            Grandchild: PARAM = INHERIT                    -> Inherit(parent_value=Inherit(...))

        When Grandchild resolves, it first resolves Child's Inherit (10 * 2 = 20),
        then returns 20 (no transform on Grandchild).

        :raises InheritError: If no parent value was captured (the parameter
            does not exist in the parent experiment).

        :returns: The concrete resolved value.
        """
        if self.parent_value is _UNSET:
            param_hint = f" for parameter '{self.name}'" if self.name else ""
            raise InheritError(
                f"Cannot resolve INHERIT{param_hint}: no parent value was captured. "
                "This parameter may not exist in the parent experiment, or "
                "INHERIT was used in a direct experiment (not via extend())."
            )

        # Recursive resolution for multi-level inheritance chains.
        # In a chain Base(10) -> Child(INHERIT(x*2)) -> Grandchild(INHERIT),
        # Grandchild's parent_value is Child's Inherit object. We must resolve
        # the inner Inherit first to get 20, then apply Grandchild's transform
        # (which is None, so 20 is returned as-is).
        value = self.parent_value
        if isinstance(value, InheritBase):
            value = value.resolve()

        if self.transform is not None:
            value = self.transform(value)

        return value

    def __repr__(self) -> str:
        # Avoid infinite recursion in repr: when parent_value is itself an Inherit
        # object (multi-level chains), we abbreviate it instead of recursing into
        # its repr, which would produce repr(parent.parent_value) ad infinitum.
        parent_repr = "INHERIT(...)" if isinstance(self.parent_value, InheritBase) else repr(self.parent_value)
        if self.transform is not None:
            return f"Inherit(transform={self.transform!r}, parent_value={parent_repr})"
        return f"Inherit(parent_value={parent_repr})"


class _InheritSentinel(InheritBase):
    """
    Module-level singleton that serves as the ``INHERIT`` marker.

    When used directly as a parameter value (``PARAM = INHERIT``), it signals
    that the parent's value should be used as-is.

    When called with a function (``PARAM = INHERIT(fn)``), it returns an
    ``Inherit`` instance carrying the transform.

    This is a singleton: ``_InheritSentinel()`` always returns the same object.
    This is important because identity checks (``parent_params[name] is value``)
    are used in ``_process_inherited_parameters`` to detect import artifacts.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __call__(self, transform: t.Callable) -> Inherit:
        """
        Create an ``Inherit`` instance with a transform function.

        :param transform: A callable that takes the parent value and returns
            the derived value.

        :raises TypeError: If ``transform`` is not callable.

        :returns: An ``Inherit`` instance with the given transform.
        """
        if not callable(transform):
            raise TypeError(
                f"INHERIT() expects a callable transform function, "
                f"got {type(transform).__name__}"
            )
        return Inherit(transform=transform)

    def __repr__(self) -> str:
        return "INHERIT"


# The module-level singleton. Users import this and use it as:
#   PARAM = INHERIT                     (explicit passthrough)
#   PARAM = INHERIT(lambda x: x * 2)   (transform)
INHERIT = _InheritSentinel()
