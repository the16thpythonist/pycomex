# Parameter Inheritance with INHERIT

When extending a parent experiment with `Experiment.extend()`, sub-experiments can override parameters by defining them with new values. But sometimes you don't want to fully replace a parameter — you want to explicitly keep the parent's value, or derive a new value from it. The `INHERIT` sentinel makes this possible.

## The Problem

Without `INHERIT`, there are only two options for parameters in a sub-experiment:

1. **Don't mention the parameter** — it silently carries over from the parent. This works, but there's no way to tell whether the parameter was intentionally inherited or simply forgotten.

2. **Set a new value** — completely replaces the parent's value. This means you can't do things like "double the parent's learning rate" or "append an extra path to the parent's list" without knowing and hardcoding the parent's value.

```python
# sub_experiment.py — without INHERIT
LEARNING_RATE = 0.002  # What was the parent's value? Is this 2x? We can't tell.
DATA_PATHS = ["/data/a", "/data/b", "/data/extra"]  # Had to copy the parent's list manually.
```

If the parent's values change later, these hardcoded overrides silently go out of sync.

## Basic Usage

Import `INHERIT` from pycomex and assign it to any parameter in a sub-experiment:

```python
# sub_experiment.py
from pycomex.functional.experiment import Experiment
from pycomex import INHERIT
from pycomex.utils import file_namespace, folder_path

# Explicitly inherit from parent (self-documenting)
LEARNING_RATE = INHERIT

# Double the parent's value
BATCH_SIZE = INHERIT(lambda x: x * 2)

# Extend the parent's list
DATA_PATHS = INHERIT(lambda x: x + ["/data/extra"])

# Merge into the parent's dict
CONFIG = INHERIT(lambda x: {**x, "new_key": "new_value"})

# Regular override (existing behavior, unchanged)
MODEL_NAME = "resnet50"

experiment = Experiment.extend(
    experiment_path="base_experiment.py",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

@experiment
def run(e: Experiment):
    e.log(f"Learning rate: {e.LEARNING_RATE}")  # parent's original value
    e.log(f"Batch size: {e.BATCH_SIZE}")         # parent's value * 2
    e.log(f"Data paths: {e.DATA_PATHS}")          # parent's list + extra

experiment.run_if_main()
```

### `PARAM = INHERIT`

Use the parent's value as-is. This is functionally equivalent to not mentioning the parameter at all, but it explicitly documents that the inheritance is intentional.

### `PARAM = INHERIT(fn)`

Call `INHERIT` with a function that takes the parent's value and returns the derived value. The function can be any callable — a lambda, a named function, or even a class with `__call__`.

```python
# Lambda (most common)
PARAM = INHERIT(lambda x: x * 2)

# Named function (for complex transforms)
def scale_and_clip(x):
    return min(x * 2, 100)

PARAM = INHERIT(scale_and_clip)
```

## Multi-Level Inheritance

`INHERIT` works across arbitrary levels of experiment inheritance. Each level can transform the value, and the transforms chain together:

```python
# base.py
LEARNING_RATE = 0.01

# child.py — extends base.py
LEARNING_RATE = INHERIT(lambda x: x * 2)  # → 0.02

# grandchild.py — extends child.py
LEARNING_RATE = INHERIT(lambda x: x * 10)  # → 0.2 (0.02 * 10)
```

When the grandchild resolves `LEARNING_RATE`, it first resolves the child's INHERIT (producing `0.02`), then applies its own transform (`0.02 * 10 = 0.2`).

You can also pass through without transforming at any level:

```python
# grandchild.py — extends child.py
LEARNING_RATE = INHERIT  # → 0.02 (child's resolved value)
```

## When Resolution Happens

INHERIT values are resolved **lazily** — not when `extend()` is called, but at the start of `initialize()`, right before the experiment begins executing. This has an important consequence: CLI overrides and other late parameter modifications are correctly picked up.

For example, if a parent experiment defines `LEARNING_RATE = 0.01` and a child uses `LEARNING_RATE = INHERIT(lambda x: x * 2)`, running the child with:

```bash
python child_experiment.py --LEARNING_RATE=0.05
```

will resolve to `0.1` (the CLI-overridden `0.05 * 2`), not `0.02`.

!!! warning "Accessing INHERIT parameters before run"
    Because resolution happens at `initialize()`, you cannot access an INHERIT parameter via `experiment.PARAM` before the experiment runs. Attempting to do so raises a `RuntimeError`:

    ```python
    experiment = Experiment.extend(...)
    print(experiment.LEARNING_RATE)  # RuntimeError: unresolved INHERIT
    ```

    If you need early access, call `experiment._resolve_inherited_parameters()` explicitly.

## Error Handling

### Missing Parent Parameter

If you use `INHERIT` for a parameter that doesn't exist in the parent experiment, an `InheritError` is raised when the experiment starts:

```python
# sub_experiment.py
NONEXISTENT_PARAM = INHERIT  # parent has no such parameter
```

```
pycomex.functional.inherit.InheritError: Cannot resolve INHERIT: no parent value
was captured. This parameter may not exist in the parent experiment, or INHERIT
was used in a direct experiment (not via extend()).
```

### Non-Callable Transform

Passing a non-callable to `INHERIT()` raises a `TypeError` immediately:

```python
PARAM = INHERIT(42)  # TypeError: INHERIT() expects a callable transform function
```

### Transform Errors

If your transform function raises an exception, it surfaces when the experiment starts. There is no type checking on the transform's return value — a lambda that returns the wrong type won't be caught until the experiment uses the value.

## Common Patterns

### Scaling Numeric Parameters

```python
LEARNING_RATE = INHERIT(lambda x: x * 0.1)    # reduce by 10x
BATCH_SIZE = INHERIT(lambda x: x * 2)          # double
NUM_EPOCHS = INHERIT(lambda x: x + 50)         # add 50 more
DROPOUT = INHERIT(lambda x: min(x + 0.1, 0.5)) # increase, capped at 0.5
```

### Extending Collections

```python
# Append to a list
DATA_PATHS = INHERIT(lambda x: x + ["/extra/dataset"])

# Prepend to a list
PREPROCESSING_STEPS = INHERIT(lambda x: ["normalize"] + x)

# Merge dictionaries
MODEL_CONFIG = INHERIT(lambda x: {**x, "dropout": 0.3, "hidden_size": 512})

# Add to a set (if stored as list)
TAGS = INHERIT(lambda x: list(set(x) | {"new_tag"}))
```

### Conditional Transforms

```python
# Only modify if condition met
BATCH_SIZE = INHERIT(lambda x: x * 2 if x < 64 else x)
```

## Using INHERIT in Configuration Files

`INHERIT` is a Python-level feature and cannot be used directly in YAML configuration files. Configuration files support only plain value overrides. If you need derived parameter values, use Python-based experiment inheritance with `Experiment.extend()`.

## API Reference

### `INHERIT`

The module-level singleton sentinel. Import from `pycomex` or `pycomex.functional.inherit`.

```python
from pycomex import INHERIT
```

- **`PARAM = INHERIT`** — inherit parent's value as-is
- **`PARAM = INHERIT(fn)`** — inherit with transform; `fn` receives the parent's value and returns the derived value

### `Inherit`

The value-carrying class returned by `INHERIT(fn)`. You don't typically create these directly.

- **`resolve()`** — resolve to a concrete value (called automatically during experiment initialization)
- **`transform`** — the transform function (or `None`)
- **`parent_value`** — the captured parent value (populated during `update_parameters()`)

### `InheritBase`

Common base class for both `INHERIT` and `Inherit` instances. Use for type checking:

```python
from pycomex.functional.inherit import InheritBase

if isinstance(value, InheritBase):
    # This is an unresolved INHERIT parameter
    ...
```

### `InheritError`

Exception raised when an INHERIT parameter cannot be resolved (e.g., missing parent parameter).

## Related Documentation

- [Hooks](basics_hooks.md) — experiment hooks and inheritance
- [Configuration Files](basics_config.md) — YAML-based parameter overrides
- [Mixins](basics_mixins.md) — reusable hook collections
- [Architecture Decision Record](architecture_decisions/06_inherit_parameter_sentinel.md) — detailed design rationale
