# PyComex Architecture Analysis: Guide for Optuna Integration Plugin

## Executive Summary

PyComex is a sophisticated microframework for managing computational experiments in Python. This analysis provides a comprehensive understanding of its architecture, focusing on key areas relevant for designing an Optuna integration plugin:

1. **Plugin System**: Hook-based architecture with priority scheduling
2. **Experiment Execution Model**: Decorator-based experiments with parameter discovery
3. **Parameter System**: Convention-based (uppercase globals) with actionable type annotations
4. **Archive System**: Nested folder structure with metadata/data serialization
5. **CLI Architecture**: Mixin-based command organization
6. **No native distributed/parallel execution**: Manual handling required

---

## 1. PLUGIN SYSTEM ARCHITECTURE

### 1.1 Core Plugin Classes

**Location**: `/media/ssd/Programming/pycomex/pycomex/plugin.py`

#### PluginManager Class
- **Purpose**: Central registry for hooks across the entire pycomex runtime
- **Key Methods**:
  - `register_hook(hook_name, function, priority)`: Register hook callbacks
  - `apply_hook(hook_name, **kwargs)`: Execute registered hooks in priority order (highest first)
  - `hook(hook_name, priority)`: Decorator for direct hook registration

#### Plugin Base Class
- **Purpose**: Convenience wrapper for plugin implementations
- **Key Methods**:
  - `register()`: Auto-discovers and registers all `@hook` decorated methods
  - `unregister()`: Placeholder for future implementation

### 1.2 Hook Decorator

```python
@hook(hook_name: str, priority: int = 0) -> callable
```

**Purpose**: Marks a method as a hook implementation with optional priority

**Features**:
- Higher priority values execute first
- Attached attributes: `__hook__`, `__priority__`
- Can stop execution chain with `StopHook` exception

### 1.3 Existing Plugin Examples

#### WeightsAndBiasesPlugin (`pycomex/plugins/weights_biases/main.py`)
```python
class WeightsAndBiasesPlugin(Plugin):
    @hook("experiment_constructed", priority=0)
    def experiment_constructed(self, config: Config, experiment: Experiment, **kwargs):
        # Checks for WANDB_PROJECT parameter and WANDB_API_KEY env var
        
    @hook("after_experiment_initialize", priority=0)
    def after_experiment_initialize(self, config: Config, experiment: Experiment, **kwargs):
        # Starts wandb run
        
    @hook("experiment_commit_fig", priority=0)
    def experiment_commit_fig(self, config: Config, experiment: Experiment, **kwargs):
        # Logs figure to wandb
        
    @hook("experiment_track", priority=0)
    def experiment_track(self, config: Config, experiment: Experiment, **kwargs):
        # Logs tracked metrics to wandb
        
    @hook("after_experiment_finalize", priority=0)
    def after_experiment_finalize(self, config: Config, experiment: Experiment, **kwargs):
        # Closes wandb run
```

#### NotifyPlugin (`pycomex/plugins/notify/main.py`)
```python
class NotifyPlugin(Plugin):
    @hook("before_experiment_parameters", priority=0)
    def before_experiment_parameters(self, config: Config, experiment: Experiment):
        # Adds __NOTIFY__ parameter
        
    @hook("after_experiment_finalize", priority=0)
    def after_experiment_finalize(self, config: Config, experiment: Experiment):
        # Sends desktop notification
```

#### PlotTrackedElementsPlugin (`pycomex/plugins/plot_track/main.py`)
```python
class PlotTrackedElementsPlugin(Plugin):
    @hook("after_experiment_finalize", priority=0)
    def after_experiment_finalize(self, config: Config, experiment: Experiment):
        # Visualizes tracked metrics
```

### 1.4 Plugin Lifecycle

```
Config.__init__()
  └─> load_plugins()
      ├─> Scan pycomex/plugins/ for main.py files
      ├─> Import modules
      ├─> Find Plugin subclasses
      ├─> Instantiate with config=self
      ├─> Call plugin.register()
      │   └─> Auto-discovers @hook decorated methods
      │       └─> pm.register_hook(hook_name, method, priority)
      └─> pm.apply_hook("after_plugins_loaded", ...)
```

### 1.5 Available Hooks in Experiment Lifecycle

**Experiment Construction Phase**:
- `before_experiment_parameters` - Before parameter discovery
- `experiment_constructed` - After Experiment.__init__
- `after_plugins_loaded` - After all plugins loaded

**Experiment Execution Phase**:
- `after_experiment_initialize` - After archive folder created
- `before_run` - Before user code execution
- `before_testing` - Before testing mode applied
- `after_run` - After user code completes
- `after_experiment_finalize` - After metadata/data saved
- `before_experiment_error` - Before error is re-raised

**Artifact Tracking**:
- `experiment_commit_fig` - When figure saved
- `experiment_commit_json` - When JSON committed
- `experiment_commit_raw` - When raw file committed
- `experiment_track` - When value tracked

---

## 2. EXPERIMENT EXECUTION MODEL

### 2.1 Experiment Decorator Pattern

**Location**: `/media/ssd/Programming/pycomex/pycomex/functional/experiment.py`

#### Core Structure
```python
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

# Parameters (uppercase globals are auto-discovered)
LEARNING_RATE: float = 0.001
BATCH_SIZE: int = 32

# Create experiment instance with decorator
experiment = Experiment(
    base_path=folder_path(__file__),      # Archive parent path
    namespace=file_namespace(__file__),   # Folder structure namespace
    glob=globals(),                        # Module globals for parameter discovery
    debug=False,                           # True = reuse "debug" folder
    name_format="{date}__{time}__{id}",   # Archive folder naming
    notify=True,                           # Enable notifications
    console_width=120,                     # Output formatting width
)

# Decorate main experiment function
@experiment
def run_experiment(e: Experiment) -> None:
    """Main experiment implementation"""
    e.log("Starting experiment...")
    e['results/accuracy'] = 0.95
    
    # Access parameters via e.PARAMETER_NAME
    print(e.LEARNING_RATE)

# Run if this module is executed directly
experiment.run_if_main()
```

### 2.2 Experiment Class Hierarchy

**ExperimentBase** (`pycomex/functional/base.py`)
├─> Parameters discovery: `_discover_parameters()`
├─> Hook system: `hook()`, `apply_hook()`, `merge_hook_map()`
└─> Module integration: `_register_in_globals()`

**Experiment** (`pycomex/functional/experiment.py`)
├─> Archive management: `prepare_path()`, `save_*()` methods
├─> Logging: `log()`, `log_parameters()`, `log_pretty()`
├─> Data storage: `[key]`, `__getitem__()`, `__setitem__()`
├─> Execution: `initialize()`, `execute()`, `finalize()`
├─> Special parameters: `__DEBUG__`, `__TESTING__`, `__REPRODUCIBLE__`, etc.
├─> Alternative constructors: `extend()`, `from_config()`, `import_from()`
├─> Metadata tracking: `metadata`, `parameters` dicts
└─> Hooks support for lifecycle extension

### 2.3 Experiment Execution Flow

```
experiment.run_if_main()
  └─> experiment.arg_parser.parse()  # Parse CLI args
      └─> experiment.execute()
          ├─> experiment.initialize()
          │   ├─> prepare_path()  # Create archive folder
          │   ├─> pm.apply_hook("after_experiment_initialize")
          │   ├─> save_dependencies()
          │   ├─> save_code()
          │   ├─> save_metadata()
          │   └─> save_analysis()
          │
          ├─> TRY:
          │   ├─> is_running = True
          │   ├─> apply_testing_if_possible()
          │   ├─> apply_hook("before_run")
          │   ├─> func(self)  # USER CODE EXECUTION
          │   └─> apply_hook("after_run")
          │
          ├─> EXCEPT Exception:
          │   └─> error = exception
          │
          ├─> experiment.finalize()
          │   ├─> metadata["end_time"] = now
          │   ├─> save_metadata()
          │   ├─> save_data()
          │   ├─> pm.apply_hook("after_experiment_finalize")
          │   └─> (if __REPRODUCIBLE__) finalize_reproducible()
          │
          ├─> pm.apply_hook("after_experiment_finalize")
          │
          └─> if error: raise error
```

### 2.4 Experiment Metadata Structure

All experiments create `experiment_meta.json` with:
```json
{
    "name": "experiment_name",
    "namespace": "results/namespace",
    "status": "done",  // or "running", "failed"
    "start_time": 1234567890.0,
    "end_time": 1234567899.0,
    "duration": 9.0,
    "has_error": false,
    "error_type": null,
    "base_path": "/path/to/base",
    "description": "Module docstring",
    "parameters": {
        "PARAMETER_NAME": {
            "name": "PARAMETER_NAME",
            "type": "str",
            "description": "Parameter description",
            "value": "actual_value",
            "usable": true  // Can be re-used in reproduction
        },
        // Special parameters:
        "__DEBUG__": {...},
        "__TESTING__": {...},
        "__REPRODUCIBLE__": {...},
        "__CACHING__": {...},
        "__PREFIX__": {...}
    },
    "hooks": {
        "hook_name": {
            "name": "hook_name",
            "num": 1,  // Count of implementations
            "description": "Hook description"
        }
    },
    "__track__": ["metric_name"]  // Tracked quantities
}
```

### 2.5 Experiment Inheritance (extend)

```python
# base_experiment.py
BASE_PARAM = 10
experiment = Experiment(...)

@experiment
def run_base(e):
    e.log("Base code")

# sub_experiment.py
from pycomex.functional.experiment import Experiment

# Extend base experiment with parameter override
experiment = Experiment.extend(
    experiment_path='base_experiment.py',
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

# Override parameter
experiment.BASE_PARAM = 20

# Add/override hooks
@experiment.hook("before_run")
def before_run(e):
    e.log("Sub-experiment before_run")

# Define main code
@experiment
def run_sub(e):
    e.log("Sub code")
```

---

## 3. PARAMETER SYSTEM: ActionableParameterType

### 3.1 Overview

**Location**: `/media/ssd/Programming/pycomex/pycomex/functional/parameter.py`

Parameters can be annotated with special types that intercept get/set operations:

```python
from pycomex.functional.parameter import ActionableParameterType, CopiedPath

# Define custom actionable parameter
class MyParameterType(ActionableParameterType):
    @classmethod
    def get(cls, experiment: Experiment, value: Any) -> Any:
        """Called when parameter is accessed via e.PARAM"""
        return processed_value
    
    @classmethod
    def set(cls, experiment: Experiment, value: Any) -> Any:
        """Called when parameter is assigned via e.PARAM = value"""
        return processed_value
    
    @classmethod
    def on_reproducible(cls, experiment: Experiment, value: Any) -> Any:
        """Called during finalize_reproducible() for archive packaging"""
        return value

# Use in experiment
MY_CUSTOM_PARAM: MyParameterType = "initial_value"
```

### 3.2 Built-in ActionableParameterType: CopiedPath

```python
class CopiedPath(ActionableParameterType):
    """
    Copies file/folder to archive in reproducible mode.
    Falls back to copy if original path doesn't exist.
    """
```

### 3.3 Parameter Discovery and Access

**Convention**: All uppercase globals are discovered as parameters

```python
PARAM1: int = 10          # Discovered and stored in experiment.parameters
Param2: str = "hello"     # NOT discovered (mixed case)
param3: float = 1.5       # NOT discovered (lowercase)

# Access patterns:
e.PARAM1                  # Returns 10 (may trigger ActionableParameterType.get)
e.PARAM1 = 20             # Sets value (may trigger ActionableParameterType.set)
e.parameters["PARAM1"]    # Direct dict access
```

### 3.4 Parameter Metadata

Each parameter has metadata stored in `experiment.metadata["parameters"][param_name]`:
```python
{
    "name": "PARAM_NAME",
    "type": "str",  # String representation of type or ActionableParameterType
    "description": "Extracted from comments",
    "value": "actual_value",
    "usable": true  # Can be re-used in reproduction
}
```

---

## 4. ARCHIVE SYSTEM

### 4.1 Archive Structure

```
base_path/
  namespace/  (e.g., "results/my_experiment")
    archive_name/  (e.g., "22_10_2025__14_26__XdtZ" or "debug")
      experiment_code.py          # Copy of source Python file
      experiment_meta.json        # Metadata (parameters, hooks, timing)
      experiment_data.json        # User data (from e['key'] = value)
      experiment_out.log          # Complete execution log
      analysis.py                 # Auto-generated analysis template
      experiment_config.yml       # (Optional) YAML config file
      .track/
        metric_name_001.png       # Tracked figure artifacts
        metric_name_002.png
      .cache/                     # (Optional) Experiment cache folder
        ...
      .venv/                      # (Optional) Reproducible mode virtualenv
      .sources/                   # (Optional) Reproducible mode source tarballs
      requirements.txt            # (Optional) Reproducible mode dependencies
      .dependencies.json          # (Optional) Reproducible mode full dependency snapshot
```

### 4.2 Archive Naming

```python
# Debug mode (reusable)
if debug:
    name = "debug"

# Named archive
elif name is not None:
    name = custom_name

# Auto-generated (default)
else:
    name = "{date}__{time}__{id}"
    # e.g., "22_10_2025__14_26__XdtZ"
    # Format customizable via name_format parameter
```

### 4.3 Data Storage APIs

#### Nested Dictionary Access
```python
# Automatic nesting creation
e['metrics/loss/train'] = 0.123
e['metrics/loss/test'] = 0.456

# Retrieval
loss = e['metrics/loss/train']
metrics = e['metrics']  # Returns nested dict

# Direct access
e.data['metrics']['loss']['train']
```

#### Tracked Values
```python
# Track numeric metrics (saves to list)
for epoch in range(100):
    e.track('loss', loss_value)

# Track figures
e.track('visualization', plt.figure())

# Result: e.data['loss'] = [0.5, 0.4, 0.3, ...]
# Metadata: e.metadata['__track__'] = ['loss', 'visualization']
```

#### File Commits
```python
# JSON data
e.commit_json('results.json', {'key': 'value'})

# Raw text
e.commit_raw('summary.txt', 'Results...')

# Matplotlib figure
e.commit_fig('plot.png', fig)

# Triggers: pm.apply_hook("experiment_commit_*", ...)
```

### 4.4 Checking and Loading Archives

```python
# Check if path is valid archive
if Experiment.is_archive("/path/to/archive"):
    # Archive is complete (status == "done")
    metadata = Experiment.load_metadata("/path/to/archive")
    experiment = Experiment.load("/path/to/archive")
```

---

## 5. CLI ARCHITECTURE

### 5.1 Structure

**Location**: `/media/ssd/Programming/pycomex/pycomex/cli/`

```
pycomex/cli/
├── main.py                # CLI, ExperimentCLI classes
├── display.py             # Rich display components
├── utils.py               # Helper functions
└── commands/
    ├── run.py             # RunCommandsMixin (run, reproduce, inspect)
    ├── template.py        # TemplateCommandsMixin (template ops)
    └── archive.py         # ArchiveCommandsMixin (archive mgmt)
```

### 5.2 CLI Using Mixin Pattern

```python
class CLI(RunCommandsMixin, TemplateCommandsMixin, ArchiveCommandsMixin, click.RichGroup):
    """Main PyComex CLI combining all command groups"""
    
class RunCommandsMixin:
    @click.command("run")
    def run_command(self, experiment_path, ...): ...
    
    @click.command("reproduce")
    def reproduce_command(self, experiment_path, ...): ...
    
    @click.command("inspect")
    def inspect_command(self, experiment_path, ...): ...
```

### 5.3 ExperimentCLI for Experiment Folders

```python
cli = ExperimentCLI(
    name="my_experiments",
    experiments_path="/path/to/experiments",
    experiments_base_path="/path/to/results",
    version="1.0.0"
)

# Auto-discovers experiments
# Provides list-experiments, experiment-info, run-experiment commands
```

### 5.4 CLI Entry Points

From `pyproject.toml`:
```toml
[project.scripts]
pycomex = "pycomex.cli:cli"
pycx = "pycomex.cli:cli"
```

---

## 6. CACHE SYSTEM

### 6.1 ExperimentCache Overview

**Location**: `/media/ssd/Programming/pycomex/pycomex/functional/cache.py`

Purpose: Cache expensive computations between experiment runs

```python
# Initialize cache
cache = ExperimentCache(
    path='/path/to/.cache',
    experiment=experiment,
)

# Cache function results
@cache.cached('model_training', scope=('preprocessing',))
def train_model(data):
    # Expensive computation
    return trained_model

# Results are cached and loaded from cache in subsequent runs
```

### 6.2 Cache Backends

- **PICKLE**: General Python objects
- **JOBLIB**: NumPy arrays and scikit-learn objects
- **JSON**: Human-readable, limited data types

### 6.3 Scoping

Cache can be organized hierarchically:
```python
@cache.cached('preprocessing', scope=('data', 'v1'))
def prep_v1(data): ...

@cache.cached('preprocessing', scope=('data', 'v2'))
def prep_v2(data): ...
```

### 6.4 Cache Control

```python
# Disable cache loading (but still save)
experiment.__CACHING__ = False

# Enables dynamic cache invalidation without deleting cache files
```

---

## 7. SPECIAL PARAMETERS

PyComex provides built-in magic parameters (double underscore prefix):

### 7.1 Standard Magic Parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `__DEBUG__` | bool | False | Reuse "debug" folder; overwrite previous |
| `__TESTING__` | bool | False | Run with minimal runtime for testing |
| `__REPRODUCIBLE__` | bool | False | Save deps, source, lock environment |
| `__CACHING__` | bool | True | Enable cache loading (new saves still happen) |
| `__PREFIX__` | str | "" | Prefix experiment name in archive |
| `__NOTIFY__` | bool | True | Send desktop notification (plugin-provided) |

### 7.2 Setting via CLI

```bash
python experiment.py --__DEBUG__=True --PARAM=value
```

### 7.3 Setting via Config

```yaml
parameters:
  __DEBUG__: true
  PARAM: value
```

---

## 8. MIXINS: REUSABLE HOOK IMPLEMENTATIONS

### 8.1 ExperimentMixin Class

**Location**: `/media/ssd/Programming/pycomex/pycomex/functional/mixin.py`

Purpose: Share hook implementations across multiple experiments

```python
# logging_mixin.py
from pycomex.functional.mixin import ExperimentMixin

MIXIN_LOG_LEVEL: str = "INFO"

mixin = ExperimentMixin(glob=globals())

@mixin.hook("before_run", replace=False)
def setup_logging(e):
    e.log(f"Logging level: {e.MIXIN_LOG_LEVEL}")

@mixin.hook("after_run", replace=False)
def teardown_logging(e):
    e.log("Logging cleanup")
```

### 8.2 Using Mixins in Experiments

```python
# sub_experiment.py
experiment = Experiment.extend(
    experiment_path='base_experiment.py',
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

# Include one or more mixins
experiment.include('logging_mixin.py')
experiment.include(['logging_mixin.py', 'notification_mixin.py'])

# Mixin hooks and parameters are merged
# Hooks execute in order: base → mixin1 → mixin2 → current experiment
```

### 8.3 Hook Execution Order with Mixins

1. Base experiment hooks (from extend())
2. Mixin 1 hooks (first include())
3. Mixin 2 hooks (second include())
4. Current experiment hooks (defined last)

---

## 9. MISSING DISTRIBUTED/PARALLEL FEATURES

### Current State

PyComex does **NOT** provide native:
- SLURM integration
- Batch job submission
- Parallel/distributed execution
- Worker pool management
- Job queue systems

### Relevant Search Result

A grep for "slurm|distributed|parallel|queue|submit" in Python files returned:
- `/media/ssd/Programming/pycomex/pycomex/functional/cache.py` - Only mentions "parallel" in docstring examples
- `/media/ssd/Programming/pycomex/tests/assets/05_testing_mode.py` - Generic test content

### Implications for Optuna Integration

Optuna integration would need to handle:
1. **Parameter space definition** → Optuna trial creation
2. **Single-run execution** → Experiment execution per trial
3. **Objective function wrapping** → e.g., minimize loss or maximize accuracy
4. **Trial tracking** → Store trial info in experiment metadata
5. **Manual parallelization** → User responsible for distributed runs

---

## 10. CONFIG-BASED EXPERIMENTS

### 10.1 Experiment.from_config()

**Location**: `Experiment.from_config()` in `/media/ssd/Programming/pycomex/pycomex/functional/experiment.py:2113`

Create experiments from YAML configuration files:

```yaml
# experiment_config.yml
extend: base_experiment.py      # Path to base experiment module
base_path: ./results            # Archive base path
namespace: experiments/run_1    # Archive namespace
name: my_experiment             # (Optional) Custom archive name
description: "Config-based run" # (Optional) Custom description

parameters:
  LEARNING_RATE: 0.001
  BATCH_SIZE: 32
  MODEL_TYPE: "transformer"

include:  # (Optional) Mixin files to include
  - logging_mixin.py
  - notification_mixin.py
```

```python
# Load from config
experiment = Experiment.from_config('./experiment_config.yml')

# Environment variable interpolation supported
# ${VAR} or ${VAR:-default}
```

---

## 11. TESTING MODE

### 11.1 Purpose

Run experiments with minimal overhead to validate code:

```python
# Enable via CLI
python experiment.py --__TESTING__=True

# Or in code
experiment.__TESTING__ = True
```

### 11.2 Implementation

```python
@experiment.testing
def setup_test_params(e):
    """Modify parameters for testing"""
    e.NUM_EPOCHS = 1  # Instead of 100
    e.DATA_SIZE = 100  # Instead of 1M
    e.BATCH_SIZE = 8   # Instead of 128
```

---

## 12. REPRODUCIBILITY MODE

### 12.1 Purpose

Save exact environment snapshot for later reproduction

```python
python experiment.py --__REPRODUCIBLE__=True
```

### 12.2 What Gets Saved

1. **Dependencies snapshot** (`.dependencies.json`)
   - All installed packages with versions
   - Python version info
   - Environment info

2. **Requirements file** (`requirements.txt`)
   - Standard pip requirements for easy reinstall

3. **Source distributions** (`.sources/`)
   - Tarballs of editable packages

4. **Local files** (`.sources/`)
   - Any local Python files imported by experiment

### 12.3 Reproduction

```bash
pycomex reproduce /path/to/archive/
```

This will:
1. Extract archive (if ZIP)
2. Create virtualenv with original Python version
3. Install all dependencies
4. Execute experiment with original parameters
5. Create new archive with results

---

## 13. TESTING PATTERNS IN CODEBASE

### 13.1 Mock Objects

**Location**: `/media/ssd/Programming/pycomex/pycomex/testing.py`

```python
from pycomex.testing import MockConfig, MockExperiment

config = MockConfig()
experiment = MockExperiment()
```

### 13.2 Test Asset Experiments

- `/tests/assets/mock_functional_experiment.py` - Basic experiment
- `/tests/assets/mock_functional_sub_experiment.py` - Extended experiment
- `/tests/assets/mock_mixin_simple.py` - Simple mixin
- `/tests/assets/mock_mixin_logging.py` - Logging mixin
- `/tests/assets/test_plugin/main.py` - Test plugin

### 13.3 Test Structure

```python
# tests/test_plugin.py
class TestPluginManager:
    def test_register_hook_basically_works(self):
        config = MockConfig()
        pm = PluginManager(config=config)
        
        def hook(config, **kwargs):
            config.data["hook"] = True
        
        pm.register_hook(hook_name="test_hook", function=hook)
        pm.apply_hook(hook_name="test_hook")
        
        assert config.data["hook"] is True
```

---

## 14. KEY FILE PATHS REFERENCE

### Core Classes
- `pycomex/plugin.py` - Plugin, PluginManager, hook decorator
- `pycomex/functional/base.py` - ExperimentBase
- `pycomex/functional/experiment.py` - Experiment class (main)
- `pycomex/functional/mixin.py` - ExperimentMixin
- `pycomex/functional/parameter.py` - ActionableParameterType
- `pycomex/functional/cache.py` - ExperimentCache
- `pycomex/config.py` - Config singleton, plugin loading

### CLI
- `pycomex/cli/main.py` - CLI, ExperimentCLI
- `pycomex/cli/commands/run.py` - RunCommandsMixin
- `pycomex/cli/commands/template.py` - TemplateCommandsMixin
- `pycomex/cli/commands/archive.py` - ArchiveCommandsMixin

### Plugins
- `pycomex/plugins/weights_biases/main.py` - W&B plugin (comprehensive example)
- `pycomex/plugins/notify/main.py` - Notification plugin
- `pycomex/plugins/plot_track/main.py` - Plot tracking plugin

### Testing
- `pycomex/testing.py` - MockConfig, MockExperiment
- `tests/test_plugin.py` - Plugin system tests
- `tests/test_functional_experiment.py` - Experiment tests
- `tests/assets/` - Mock experiments and mixins

---

## 15. DESIGN PATTERNS USED

### 15.1 Singleton Pattern
```python
class Config(metaclass=Singleton):
    """Global configuration instance"""
```

### 15.2 Decorator Pattern
```python
@Experiment(...) 
def run(e): ...

@experiment.hook("before_run")
def before_run(e): ...

@experiment.testing
def setup_tests(e): ...

@mixin.hook("hook_name")
def hook_impl(e): ...

@experiment.analysis
def analyze(e): ...
```

### 15.3 Mixin Pattern
```python
class CLI(RunCommandsMixin, TemplateCommandsMixin, ArchiveCommandsMixin, ...):
    pass
```

### 15.4 Hook/Plugin Pattern
- `register_hook()` - Subscribe to events
- `apply_hook()` - Publish events
- Priority-based execution ordering

### 15.5 Convention over Configuration
- Uppercase globals → parameters
- Double underscore prefix → magic parameters
- Module path → archive namespace

---

## 16. BEST PRACTICES FROM EXISTING PLUGINS

### 16.1 From WeightsAndBiasesPlugin

1. **Check for prerequisites** in `experiment_constructed` hook
2. **Initialize external service** in `after_experiment_initialize`
3. **Log artifacts** on `experiment_commit_fig` and `experiment_track`
4. **Clean up** in `after_experiment_finalize`
5. **Handle errors gracefully** with try-except and debug logging

### 16.2 From NotifyPlugin

1. **Add custom parameters** in `before_experiment_parameters` hook
2. **Use metadata timing** for informative messages
3. **Access experiment data** during finalization hooks
4. **Use logger.debug()** for plugin-specific logging

### 16.3 From PlotTrackedElementsPlugin

1. **Process tracked data** in `after_experiment_finalize`
2. **Create visualizations** from tracked metrics
3. **Save artifacts** to experiment.path
4. **Handle failures gracefully** to not break experiment

---

## 17. OPTUNA INTEGRATION PLUGIN DESIGN SUGGESTIONS

### Key Integration Points

1. **Parameter Definition**: Translate Optuna `optuna.trial.Trial` parameters to experiment parameters
2. **Hook Points**:
   - `experiment_constructed`: Define study and add trial tracking parameters
   - `after_experiment_initialize`: Log trial info
   - `experiment_track`: Could feed metrics to Optuna for pruning
   - `after_experiment_finalize`: Report trial results to Optuna

3. **Data Storage**: Store trial information in metadata
4. **Archive Organization**: Use namespace to organize trials
5. **Metric Tracking**: Use `e.track()` for metrics, feed to Optuna

### Plugin Structure

```python
from pycomex.plugin import Plugin, hook
from pycomex.config import Config
from pycomex.functional.experiment import Experiment
import optuna

class OptunaPlugin(Plugin):
    @hook("experiment_constructed", priority=0)
    def experiment_constructed(self, config: Config, experiment: Experiment):
        # Initialize Optuna study, check for OPTUNA_STUDY parameter
        
    @hook("after_experiment_initialize", priority=0)
    def after_experiment_initialize(self, config: Config, experiment: Experiment):
        # Get trial from Optuna, store in metadata
        
    @hook("after_experiment_finalize", priority=0)
    def after_experiment_finalize(self, config: Config, experiment: Experiment):
        # Report trial result to Optuna
```

---

## 18. SUMMARY OF KEY CONCEPTS

| Concept | Location | Purpose |
|---------|----------|---------|
| Plugin | `pycomex/plugin.py` | Extend behavior via hooks |
| Experiment | `pycomex/functional/experiment.py` | Main decorator-based experiment class |
| ExperimentMixin | `pycomex/functional/mixin.py` | Reusable hook implementations |
| ActionableParameterType | `pycomex/functional/parameter.py` | Custom parameter get/set behavior |
| Archive | `base_path/namespace/{timestamp or debug}/` | Stores results and metadata |
| Hook | Throughout | Subscribe to experiment lifecycle events |
| Config (Singleton) | `pycomex/config.py` | Global plugin manager access |
| ExperimentCache | `pycomex/functional/cache.py` | Cache expensive computations |

---

## 19. EXTERNAL DEPENDENCIES WORTH NOTING

The codebase uses:
- **Click** (via rich_click) - CLI framework
- **Rich** - Terminal formatting/colors
- **Pydantic** - Data validation
- **YAML** - Config file parsing
- **Jinja2** - Template generation
- **UV** - Python package management (reproducibility)
- **Matplotlib** - Plotting
- **Joblib** - Serialization (cache)
- **Wandb** - W&B integration (plugin)
- **Desktop-notifier** - Notifications (plugin)

This is a well-architectured system designed for extensibility and clean separation of concerns.

