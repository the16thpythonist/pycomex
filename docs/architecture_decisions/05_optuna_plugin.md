# Optuna Hyperparameter Optimization Plugin

## Status

Implemented

## Context

One common use case in the domain of computational experiments is *Hyperparameter optimization*. This is a process 
in which some kind of search is performed over a set of experiment parameters to optimize a given objective function - 
commonly the performance of a neural network, for example. Such hyperparameter optimization is already implemented 
in various third-party packages but would be nice to directly implement this in an experimentation framework as well.

## Decision

I've decided to use the **Optuna** package as the implementation for the hyperparameter optimization of the experiments.
From an implementation perspective this should be a *plugin* and not a core functionality, because optuna is another 
heavy dependency which I do not want to have in the core package that is supposed to be lightweight and more of a 
micro-framework.

## Plan

From a user perspective, the plugin should be part of the main pycomex package already but only available in the 
`full` installation suite:

```bash
uv pip install pycomex[full]
```

When creating an experiment module, this should be an opt-in thing that can easily be added on top of an already 
existing experiment. I imagine something like this.

```python
# experiment.py
from pycomex import Experiment, folder_path, file_namespace
from typing import Dict, Any
import optuna

LEARNING_RATE: float = 0.1
BATCH_SIZE: int: 32

experiment = Experiment(
    base_path=folder_path(__file__),
    file_namespace=file_namespace(__file__),
    glob=globals(),
)

@experiment.hook('__optuna_parameters__')
def optimize_parameters(e: Experiment, trial: optuna.Trial) -> dict[str, trial]:
    """
    This is a hook that is executed right after an experiment was constructed and which is 
    supposed to return a dictionary that determines the experiment parameters that are supposed 
    to be used as the inputs of the optimization.
    """
    return {
        'LEARNING_RATE': trial.suggest_float('LEARNING_RATE', 1e-4, 1e-2)
        'BATCH_SIZE': trial.suggest_int('BATCH_SIZE', 16, 64)
    }

@experiment.hook('__optuna_objective__')
def optimize_parameters(e: Experiment, ) -> Any:
    """
    This is a hook that is executed after the experiment is finished and which is supposed 
    to extract the objective value from the experiment storage.
    """
    return e['results/metrics/r2']

@experiment.hook('__optuna_sampler__', replace=True)
def optimize_sampler(e: Experiment, ) -> optuna.Sampler:
    """
    This is a hook that is executed when loading the Optuna study. This will do the optuna sampler
     
    """
    return optuna.samplers.TPESampler(
        constant_liar=True,
        n_startup_trials=25,
    )

@experiment
def experiment(e: Experiment):
    # do stuff...
    # Importantly - at this point the parameter values will have been replaced and no longer be 
    # the defaults but instead will be the values suggested by the trial!
```

### Command Line Interface

This plugin should also extend the command line interface with some custom commands.

Most importantly the `optuna run` command should be the special command that should be used to 
actually run the experiment with the intent of running the optuna optimization. So only when an 
experiment is started like this, the actual parameters should be replaced by the trial suggestions.

```bash
pycomex optuna run experiment.py
```

Then there should be one command which lists all of the studies that are currently available in 
the current experiment folder and some basic information about them such as the number of trials 
that are already part of it and the last execution date and so on.

```bash
pycomex optuna list
```

Then there should be one command which shows the details for one of the studies selected by the name 
that can also be seen in the list command. This command should show more details such as a table with 
all of the hyperparameter configs and the corresponding objective values and the currently best one 
marked in bold.

```bash
pycomex optune info "experiment"
```

### Plugin implementation

**Study Management.** The plugin should handle the management of the various `Study` objects and the 
corresponding databases automatically. Much like the caching information it should create and maintain a 
new folder ".optuna" which contains all of the databases as sqllite files with the corresponding names 
of the experiments from which they were created.

On the implementation perspective this should be handled in the

**Experiment Init.** During the experiment init, the workflow should be like this:
1. Check if the experiment was run with the `optuna run` command (This should internally set a magic 
parameter `__OPTUNA__` to true which is then checked by this check). Only if that is the case do the 
following.
2. Try to find an existing study with the name of the experiment. if not create a new one. Use the 
result from the `__optuna_sampler__` hook for the sampler. (This hook should have a default implementation 
provided by the plugin.)
3. Extract the trial object from that and pass it to the `__optuna_parameters__` hook and then get 
the parameter dict and replace all the experiment parameter values with the values obtained from that.
4. Execute the experiment...

**Experiment Finalize.** Collect the objective value from the `__optuna_objective__` hook and then
update the corresponding study database with that.

## Implementation

The Optuna plugin was successfully implemented as specified with several key design decisions made during development:

### Core Components

**StudyManager Class** (`pycomex/plugins/optuna/main.py`): Manages Optuna studies and SQLite database storage in the `.optuna` folder. Provides methods for creating, loading, listing, and deleting studies. Each study is stored as a separate SQLite database file named after the experiment.

**OptunaPlugin Class** (`pycomex/plugins/optuna/main.py`): Main plugin implementation that registers hooks for experiment lifecycle integration and CLI command registration. Handles trial creation, parameter replacement, and objective reporting.

**Rich Display Classes** (`pycomex/plugins/optuna/display.py`): Provides formatted CLI output using Rich library components:
- `RichOptunaStudyList` - Table view of all studies
- `RichOptunaStudySummary` - Panel display of study information
- `RichOptunaStudyInfo` - Detailed trial table with best trial highlighting

### Key Design Decisions

**`__OPTUNA__` as Default Parameter**: Rather than requiring users to add `__OPTUNA__` to each experiment module, it was added to the default parameter set in `Experiment` class (alongside `__DEBUG__`, `__TESTING__`, etc.). This provides a cleaner user experience and automatic CLI argument parsing.

**`before_experiment_initialize` Hook**: A new system hook was introduced specifically for this plugin. This hook fires at the beginning of `Experiment.initialize()` after all parameter overrides (including CLI arguments) have been applied. This timing is critical for:
- Ensuring CLI-set parameters are available
- Allowing parameter replacement before archive folder creation
- Maintaining clean separation of concerns

This is more elegant than the original plan's approach of checking flags during `experiment_constructed` since that hook fires before CLI parameter parsing.

**Storage Architecture**: Studies are stored in a `.optuna` folder at the experiment base path (similar to `.cache`). Each study gets its own SQLite database file, providing:
- Isolation between different experiment optimizations
- Easy backup and transfer of individual studies
- No cross-study contamination

**CLI Display Style**: Tables use `rich.box.HORIZONTALS` for booktabs-style horizontal lines only, matching the core PyComex CLI aesthetic. Headers are bold white (not magenta) for consistency. Tables expand to full console width for better readability.

**Trial Flow**:
1. `before_experiment_initialize`: Check `__OPTUNA__` parameter, initialize study, create trial, replace parameters
2. Experiment runs normally with trial-suggested parameters
3. `after_experiment_finalize`: Extract objective via `__optuna_objective__` hook, report to study, complete trial

### Deviations from Original Plan

**Hook Timing**: Originally planned to use `experiment_constructed` and `after_experiment_initialize`. Implemented solution uses the new `before_experiment_initialize` hook for cleaner timing and better integration with CLI parameter overrides.

**Default Parameter**: The specification suggested checking a magic parameter set by the CLI. Implementation adds `__OPTUNA__` to default experiment parameters, providing better integration with PyComex's parameter system and automatic help generation.

**Display Architecture**: Added Rich display classes following PyComex's existing pattern (see `pycomex/cli/display.py`) rather than inline table construction. This improves code organization and reusability.

### Testing

Comprehensive test suite implemented (`tests/test_optuna_plugin.py`):
- 13 unit tests for StudyManager functionality
- 3 integration tests for plugin hooks
- 1 end-to-end integration test
- Test coverage includes: study creation, listing, deletion, parameter replacement, objective reporting, and error handling

### Documentation

Complete documentation added:
- Tutorial page in advanced section (`docs/advanced_optuna.md`)
- README feature mention
- This ADR updated with implementation details
- Inline docstrings following reStructuredText format throughout codebase
