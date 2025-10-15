# Special Parameters

Special parameters in PyComex are identified by double underscores (e.g., `__DEBUG__`) and control specific aspects of experiment behavior. These parameters can be set like regular experiment parameters, either in your experiment module or via command-line arguments.

## Parameter Reference

### `__DEBUG__`
**Type:** `bool`
**Default:** `False`

Creates a reusable "debug" folder instead of timestamped folders. When enabled, each experiment run overwrites the previous debug folder, making it ideal for rapid iteration during development.

```python
# In experiment file
__DEBUG__ = True
```

```bash
# Via CLI
python experiment.py --__DEBUG__=True
```

### `__TESTING__`
**Type:** `bool`
**Default:** `False`

Enables testing mode for minimal runtime testing. When enabled, the experiment executes with minimal resources to verify that all components work without running full computations. Implementation of testing behavior is optional and must be defined using the `@experiment.testing` decorator.

```python
# In experiment file
__TESTING__ = True

@experiment.testing
def testing(e):
    # Modify parameters for minimal runtime
    e.EPOCHS = 2
    e.BATCH_SIZE = 4
```

### `__REPRODUCIBLE__`
**Type:** `bool`
**Default:** `False`

Enables reproducible mode. When enabled, the experiment captures complete environment information at the end of execution, including Python version, all installed packages with versions, source code of editable packages, and environment variables. This information is stored in the experiment archive for later reproduction.

```python
# In experiment file
__REPRODUCIBLE__ = True
```

See [Architecture Decision: Reproducible Mode](architecture_decisions/02_reproducible_mode.md) for more details.

### `__PREFIX__`
**Type:** `str`
**Default:** `""`

A string prefix that will be prepended to the experiment archive folder name. This is useful for differentiating between different runs or variants of the same experiment. The prefix is added to the generated timestamp-based name.

```python
# In experiment file
__PREFIX__ = "ablation_study"

# Results in folder name like: ablation_study__15_01_2024__14_30__a3f2
```

### `__CACHING__`
**Type:** `bool`
**Default:** `True`

Controls whether the experiment cache system loads existing cached results. When `False`, cached results will not be loaded even if available, forcing recomputation. New results will still be saved to the cache unless explicitly configured otherwise in your cache usage.

```python
# In experiment file
__CACHING__ = False  # Force recomputation, ignore cached results
```

## Usage

Special parameters can be set in three ways:

1. **In the experiment module:**
   ```python
   __DEBUG__ = True
   __REPRODUCIBLE__ = True
   ```

2. **Via command-line arguments:**
   ```bash
   python experiment.py --__DEBUG__=True --__REPRODUCIBLE__=True
   ```

3. **In configuration files:**
   ```yaml
   extend: base_experiment.py
   parameters:
     __DEBUG__: true
     __REPRODUCIBLE__: true
   ```

## Notes

- Special parameters are automatically available in all experiments without explicit declaration
- They are processed during experiment initialization and may affect experiment behavior before the main experiment function runs
- Special parameters appear in experiment metadata and can be queried in the archive
- Like regular parameters, special parameters can be overridden in sub-experiments using `Experiment.extend()`
