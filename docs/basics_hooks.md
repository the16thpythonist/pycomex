# Basic Hooks in PyComex

Hooks in PyComex are user-defined functions that execute at specific points during your experiment via `e.apply_hook()`. They provide a flexible way to inject custom functionality without modifying core experiment logic.

**Key characteristics:**
- Experiment-specific with decorator-based registration (`@experiment.hook()`)
- Executed on demand when called via `e.apply_hook()`
- Receive the experiment instance and additional parameters

## Hook Structure

```python
from pycomex.functional.experiment import Experiment
from pycomex.utils import file_namespace, folder_path

# Define experiment parameters
DATASET = "training_data.csv"

# Create experiment instance
experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

# Define hooks BEFORE the main experiment function
@experiment.hook("load_data")
def load_dataset(e: Experiment, dataset_name: str):
    e.log(f"Loading dataset: {dataset_name}")
    return f"data_from_{dataset_name}"

@experiment.hook("preprocess")
def clean_data(e: Experiment, data: str):
    e.log(f"Preprocessing: {data}")
    return data.upper()

# Main experiment function
@experiment
def main_experiment(e: Experiment):
    e.log("Starting experiment")
    raw_data = e.apply_hook("load_data", dataset_name=e.DATASET)
    processed_data = e.apply_hook("preprocess", data=raw_data)
    e["result"] = processed_data

experiment.run_if_main()
```

## Hook Registration Options

```python
@experiment.hook("hook_name", replace=True, default=True)
def my_hook(e: Experiment, **kwargs):
    pass
```

- `replace=True` (default): Replace existing hooks with same name
- `replace=False`: Append to existing hooks (executed in order)
- `default=True` (default): Only register if no other hooks exist
- `default=False`: Always register this hook

### Multiple Hooks Example

```python
# Register multiple hooks for the same point
@experiment.hook("validate", replace=False)
def check_format(e: Experiment, data):
    assert isinstance(data, str), "Data must be string"
    return data

@experiment.hook("validate", replace=False)
def check_length(e: Experiment, data):
    assert len(data) > 0, "Data cannot be empty"
    return data

@experiment
def main_experiment(e: Experiment):
    data = "sample_data"
    validated_data = e.apply_hook("validate", data=data)  # Both hooks execute
```


## Hook Documentation

PyComex automatically parses hook documentation from special comment syntax:

```python
@experiment
def documented_experiment(e: Experiment):
    # :hook preprocess_data:
    #       Preprocesses input data by applying normalization and cleaning.
    processed_data = e.apply_hook("preprocess_data", raw_data="input_data")
```

Descriptions are added to experiment metadata and viewable in the experiment archive.

## Experiment Inheritance with Hooks

Child experiments can override parent hooks:

```python
# Parent experiment: base_experiment.py
@experiment.hook("process_data")
def basic_processing(e: Experiment, data):
    return data.lower()

# Child experiment: advanced_experiment.py
experiment = Experiment.extend(
    experiment_path="base_experiment.py",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

@experiment.hook("process_data")  # Overrides parent hook
def advanced_processing(e: Experiment, data):
    return data.upper() + "!!!"
```

## Best Practices

### When to Use Hooks

Use hooks for experiment steps that:
1. Have clear interfaces with well-defined parameters and return values
2. Are potentially replaceable (different implementations)
3. Separate concerns (data loading, training, evaluation, etc.)
4. Are reusable across multiple experiments

### Common Use Cases

**Data Management:** Loading, preprocessing, validation, splitting
**Model Operations:** Creation, training, evaluation, persistence
**Visualization:** Plot generation, report creation, result comparison
**Flow Control:** Setup/teardown, checkpointing, error handling

### Design Guidelines

1. **Keep hooks focused** - Single responsibility per hook
2. **Use descriptive names** - Clear purpose (`validate_input_data` not `step1`)
3. **Handle parameters gracefully** - Provide defaults and validate inputs
4. **Document interfaces** - Specify expected parameters and return values
5. **Return appropriately** - Return processed data for transformations

```python
@experiment.hook("normalize_features")
def normalize_data(e: Experiment, data: np.ndarray, method: str = "standard"):
    """Normalize feature data using specified method."""
    if method not in ["standard", "minmax", "robust"]:
        e.log(f"Unknown method '{method}', using 'standard'")
        method = "standard"
    # Implementation here
    return normalized_data
```

### Anti-Patterns to Avoid

- **Don't make experiments depend on hooks** - Provide defaults for missing hooks
- **Don't use hooks for simple configuration** - Use experiment parameters instead
- **Don't make hooks interdependent** - Each hook should be independently functional

```python
# Good: Provide defaults
data = e.apply_hook("load_data", default=[1, 2, 3])

# Good: Use parameters for config
LEARNING_RATE = 0.01  # Not a hook
```

## Next Steps

- For more advanced hook usage and system-level plugin hooks, see [Advanced Hooks](advanced_hooks.md)
- For plugin development using hooks, see [Advanced Plugins](advanced_plugins.md)
- For experiment inheritance patterns, see the [inheritance example](../pycomex/examples/04_inheritance.py)