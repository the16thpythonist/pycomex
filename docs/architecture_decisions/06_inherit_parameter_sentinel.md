# INHERIT Parameter Sentinel

## Status

Implemented

## Context

PyComex supports experiment inheritance via `Experiment.extend()`, where a sub-experiment extends a base experiment and can override parameters and hook implementations. Previously, there were only two options for parameters in a sub-experiment:

1. **Implicit inheritance** — don't mention the parameter at all, and it silently carries over from the parent.
2. **Full override** — define the parameter with a new value, completely replacing the parent's value.

There was no way to explicitly reference the parent's value or to derive a new value from it. This made certain patterns awkward or impossible:

- Explicitly documenting that a parameter is intentionally inherited (not just forgotten).
- Doubling a learning rate from the base experiment: `LEARNING_RATE = parent_value * 2` required knowing the parent's value at write time.
- Extending a list parameter: `DATA_PATHS = parent_paths + ["/extra/path"]` required duplicating the parent's entire list.

## Decision

Introduce a special `INHERIT` sentinel value that sub-experiments can use to explicitly reference the parent's parameter value, with an optional transformation function:

```python
# sub_experiment.py
from pycomex import INHERIT

PARAM_A = INHERIT                              # explicit: use parent's value as-is
PARAM_B = INHERIT(lambda x: x * 2)            # double the parent's value
PARAM_C = INHERIT(lambda x: x + ["/extra"])    # extend the parent's list
PARAM_D = "completely_new"                     # full override (existing behavior)
```

### Key Design Decisions

**Singleton sentinel with `__call__`:** `INHERIT` is a module-level singleton (`_InheritSentinel`). Using it directly (`PARAM = INHERIT`) means "use parent's value as-is". Calling it (`PARAM = INHERIT(fn)`) returns an `Inherit` instance carrying the transform function. This provides a natural API where the simple case is simple and the complex case is a straightforward extension.

**Lazy resolution:** INHERIT values are not resolved during `extend()` but rather at the start of `initialize()` — right before the experiment archive is created and metadata is saved. This means parent parameter values can still be modified between `extend()` and `run()` (e.g., via CLI overrides or programmatic changes), and INHERIT will pick up the final values.

**Parent value capture via snapshot:** During `update_parameters()`, a snapshot of `self.parameters` is taken *before* `_discover_parameters()` overwrites them with child globals. After discovery, any INHERIT values are matched against this snapshot to capture the parent's value. This avoids losing the parent value during the glob merge.

**Generic transform only:** Rather than providing specialized methods for common operations (like `INHERIT.append()` for lists or `INHERIT.merge()` for dicts), only generic lambda transforms are supported. Users write `INHERIT(lambda x: x + [item])` for lists or `INHERIT(lambda x: {**x, "key": "val"})` for dicts. This keeps the API surface small and avoids hard-to-maintain convenience methods.

## Implementation

The INHERIT system is implemented across the following files:

- **`pycomex/functional/inherit.py`**: Contains the class hierarchy:
  - `InheritBase` — common base class for `isinstance` checks
  - `Inherit(InheritBase)` — carries `transform` and `parent_value`, with recursive `resolve()`
  - `_InheritSentinel(InheritBase)` — singleton class; `__call__(fn)` returns `Inherit(transform=fn)`
  - `InheritError` — raised when resolution fails
  - `INHERIT` — the module-level singleton instance

- **`pycomex/functional/experiment.py`**: Integration points:
  - `update_parameters()` — snapshots parent params, then calls `_process_inherited_parameters()`
  - `_process_inherited_parameters()` — converts sentinels to `Inherit` instances, attaches parent values
  - `_resolve_inherited_parameters()` — resolves all `Inherit` objects to concrete values
  - `initialize()` — calls `_resolve_inherited_parameters()` at the start
  - `__getattr__()` — guard against accessing unresolved INHERIT before `initialize()`
  - `save_metadata()` — defensive fallback for unresolved INHERIT during serialization

- **`pycomex/__init__.py`**: Exports `INHERIT` at the package level

### The Import Artifact Problem

A notable implementation challenge arose from PyComex's parameter discovery convention: any uppercase global variable is treated as a parameter. Since `INHERIT` is itself an uppercase name, `from pycomex import INHERIT` in a sub-experiment module causes the `INHERIT` *variable name* to be discovered as a parameter — which is not the user's intent.

This creates a particularly subtle bug in multi-level inheritance chains:

1. Child imports `INHERIT` and uses `PARAM = INHERIT(fn)`.
2. `_discover_parameters()` picks up both `PARAM` (correct) and `INHERIT` (artifact).
3. The `INHERIT` artifact becomes `Inherit(parent_value=_UNSET)` in the child's parameters.
4. When a grandchild extends the child, `_discover_parameters` reads the same Inherit object from the glob, and `parent_params` also has the same object. Setting `value.parent_value = parent_params[name]` would create `value.parent_value = value` — a self-referencing cycle that causes infinite recursion in `resolve()`.

This is solved with a two-tier detection mechanism:

- **Identity check** (multi-level): If `parent_params[name] is value` (the exact same object), it's an inherited artifact, not a new user assignment. Remove it from parameters.
- **`_from_sentinel` marker** (first-level): When a `_InheritSentinel` is converted to `Inherit`, it's marked with `_from_sentinel=True`. During resolution, `Inherit` objects with `_UNSET` parent values that lack this marker are import artifacts and are silently removed. Those WITH the marker are genuine user errors (INHERIT used for a parameter the parent doesn't have) and raise `InheritError`.

See the extensive inline comments in `_process_inherited_parameters()` and `_resolve_inherited_parameters()` for the full trace of each case.

## Consequences

### Advantages

**Explicit inheritance.** Sub-experiments can clearly communicate which parameters are intentionally carried over from the parent, making the experiment hierarchy more readable and self-documenting.

**Derived parameters.** The transform function enables computing parameter values relative to the parent, which is common in research workflows (e.g., scaling learning rates, extending dataset paths, multiplying batch sizes).

**Late binding.** Lazy resolution at `initialize()` means INHERIT correctly interacts with CLI overrides and other late parameter modifications — the user can override a parent's parameter value via the CLI and INHERIT-based children will pick up the override.

**Multi-level support.** INHERIT works across arbitrary levels of experiment inheritance. Each level can transform the value, and resolution correctly chains through all levels.

### Disadvantages

**Pre-run access limitation.** INHERIT parameters cannot be accessed via `experiment.PARAM` before the experiment runs. Attempting to do so raises a `RuntimeError` rather than returning the sentinel object (which would be confusing). Users who need early access must call `experiment._resolve_inherited_parameters()` explicitly.

**Import artifact complexity.** The `INHERIT` name being uppercase creates an unfortunate collision with the parameter discovery convention. The two-tier artifact detection mechanism (identity check + `_from_sentinel` marker) adds implementation complexity and is non-obvious. This is thoroughly documented in inline comments but remains a maintenance concern.

**No type safety.** The transform function is unchecked — a lambda that returns the wrong type won't be caught until the experiment runs. This is consistent with PyComex's general approach to parameters (no type enforcement at runtime) but means INHERIT transform errors surface late.
