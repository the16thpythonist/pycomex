# Experiment Mixins

Experiment mixins solve a simple problem: reusing the same hook implementations across multiple experiments without copying code.

## The Problem

Imagine you want the same logging behavior in three different experiments. Without mixins, you'd copy the same hook code three times:

```python
# experiment1.py
@experiment.hook("before_run")
def log_start(e):
    e.log("Starting experiment...")

# experiment2.py
@experiment.hook("before_run")  # Duplicate code
def log_start(e):
    e.log("Starting experiment...")

# experiment3.py
@experiment.hook("before_run")  # Another duplicate
def log_start(e):
    e.log("Starting experiment...")
```

This violates DRY (Don't Repeat Yourself) and makes updates error-prone.

## The Solution: Mixins

Create the hook once in a mixin, then include it wherever needed:

```python
# logging_mixin.py
mixin = ExperimentMixin(glob=globals())

@mixin.hook("before_run", replace=False)
def log_start(e):
    e.log("Starting experiment...")

# experiment1.py, experiment2.py, experiment3.py
experiment.include('logging_mixin.py')  # One line, no duplication
```

**Key concept**: Mixins are reusable collections of hooks that can't run standalone but can be included in any experiment.

## Creating a Mixin

A mixin is a Python file with `ExperimentMixin` and hook definitions:

```python
# my_mixin.py
"""
Brief description of what this mixin provides.
"""
from pycomex.functional.mixin import ExperimentMixin

# Create the mixin instance
mixin = ExperimentMixin(glob=globals())

# Define hooks using replace=False so they append rather than replace
@mixin.hook("before_run", replace=False)
def my_hook(e):
    """What this hook does."""
    e.log("Mixin hook executing")
```

### Key Points

- **Import**: Use `from pycomex.functional.mixin import ExperimentMixin`
- **Instance**: Create with `mixin = ExperimentMixin(glob=globals())`
- **Hooks**: Use `@mixin.hook(name, replace=False)` - the `replace=False` ensures the hook appends
- **Parameters**: You can define optional parameters just like in experiments

### Simple Example

```python
# 11_experiment_mixin_mixin.py
"""
A simple logging mixin that adds start and end messages.
"""
from pycomex.functional.mixin import ExperimentMixin

mixin = ExperimentMixin(glob=globals())

@mixin.hook("before_run", replace=False)
def log_start(e):
    e.log("→ Mixin: Experiment starting...")

@mixin.hook("after_run", replace=False)
def log_end(e):
    e.log("→ Mixin: Experiment finished!")
```

That's it! This mixin can now be included in any experiment.

## Using Mixins

### In Python Experiments

Include mixins using `experiment.include()`:

```python
# 11_experiment_mixin.py
from pycomex import Experiment, file_namespace, folder_path

NUM_WORDS: int = 50
__DEBUG__: bool = True

experiment = Experiment.extend(
    "02_basic.py",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

# Include the mixin - this adds its hooks to your experiment
experiment.include("11_experiment_mixin_mixin.py")

# Your own hooks still work
@experiment.hook("after_run", replace=False)
def custom_summary(e):
    e.log("→ Custom: All done!")

experiment.run_if_main()
```

### In YAML Configuration

Use the `include` field:

```yaml
# 12_experiment_mixin.yml
pycomex: true
extend: 02_basic.py

# Include a single mixin
include: 11_experiment_mixin_mixin.py

# Or include multiple mixins
# include:
#   - logging_mixin.py
#   - validation_mixin.py

parameters:
  NUM_WORDS: 75
  __DEBUG__: true
```

### Multiple Mixins

Include multiple mixins by passing a list:

```python
# Python
experiment.include(['logging_mixin.py', 'validation_mixin.py', 'notification_mixin.py'])
```

```yaml
# YAML
include:
  - logging_mixin.py
  - validation_mixin.py
  - notification_mixin.py
```

## Hook Execution Order

When you use mixins, hooks execute in this order:

1. **Base experiment hooks** (from `Experiment.extend()`)
2. **First mixin hooks** (first `include()` call)
3. **Second mixin hooks** (second `include()` call)
4. **Current experiment hooks** (hooks defined in your experiment)

### Example

```python
# base_experiment.py
@experiment.hook("before_run", replace=False)
def base_hook(e):
    e.log("1. Base")

# logging_mixin.py
@mixin.hook("before_run", replace=False)
def mixin_hook(e):
    e.log("2. Mixin")

# my_experiment.py
experiment = Experiment.extend('base_experiment.py', ...)
experiment.include('logging_mixin.py')

@experiment.hook("before_run", replace=False)
def experiment_hook(e):
    e.log("3. Experiment")

# When the experiment runs:
# Output:
# 1. Base
# 2. Mixin
# 3. Experiment
```

## When to Use Mixins

### ✅ Use Mixins When:

- **Same hook needed in multiple experiments** - Standardized logging, notifications, validation
- **Functionality is generic** - Not specific to one experiment's domain logic
- **Behavior should be consistent** - You want identical behavior across experiments
- **Cross-project reuse** - The functionality makes sense in different research projects

### ❌ Don't Use Mixins When:

- **Hook is experiment-specific** - Tied to particular experiment logic
- **Used only once** - No duplication to avoid
- **Needs experiment context** - Depends on specific experiment implementation details
- **Complex interdependencies** - The hook relies on other experiment-specific hooks

### Alternative Approaches

**Use experiment inheritance** (`Experiment.extend()`) when:
- Building variations of a specific experiment
- Modifying parameters and a few hooks
- The logic is domain-specific

**Create a new experiment** when:
- Fundamentally different analysis
- Different research question
- Starting fresh without baggage

## Common Patterns

### Logging Enhancements

```python
# logging_mixin.py
@mixin.hook("before_run", replace=False)
def log_start(e):
    import datetime
    timestamp = datetime.datetime.now().isoformat()
    e.log(f"[{timestamp}] Starting: {e.metadata['name']}")

@mixin.hook("after_run", replace=False)
def log_end(e):
    import datetime
    timestamp = datetime.datetime.now().isoformat()
    duration = e.metadata['duration']
    e.log(f"[{timestamp}] Completed in {duration:.2f}s")
```

### Notifications

```python
# notification_mixin.py
@mixin.hook("after_run", replace=False)
def send_notification(e):
    from pycomex.utils import trigger_notification
    message = f"Experiment '{e.metadata['name']}' completed"
    trigger_notification(message)
```

### Data Validation

```python
# validation_mixin.py
@mixin.hook("validate_data", replace=False)
def check_data_size(e, data, min_size=10):
    if len(data) < min_size:
        e.log(f"Warning: Data has only {len(data)} items (minimum: {min_size})")
        return False
    return True
```

## Complete Working Example

See the `pycomex/examples/` directory for complete examples:

- **`11_experiment_mixin_mixin.py`** - Simple logging mixin
- **`11_experiment_mixin.py`** - Experiment using the mixin
- **`12_experiment_mixin.yml`** - YAML configuration with mixin

Run the example:

```bash
# Python version
python pycomex/examples/11_experiment_mixin.py

# YAML version
pycomex run pycomex/examples/12_experiment_mixin.yml
```

## Quick Reference

```python
# Creating a mixin
from pycomex.functional.mixin import ExperimentMixin
mixin = ExperimentMixin(glob=globals())

@mixin.hook("hook_name", replace=False)
def my_hook(e):
    pass

# Using a mixin
experiment.include('mixin.py')
experiment.include(['mixin1.py', 'mixin2.py'])
```

```yaml
# YAML configuration
include: mixin.py
# or
include:
  - mixin1.py
  - mixin2.py
```

## Related Documentation

- [Basic Hooks](basics_hooks.md) - Understanding PyComex hooks
- [Configuration Files](basics_config.md) - Using mixins in YAML configs
- [Advanced Hooks](advanced_hooks.md) - System-level plugin hooks
