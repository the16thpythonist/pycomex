# Hyperparameter Optimization with Optuna

PyComex includes built-in integration with [Optuna](https://optuna.readthedocs.io/), a powerful hyperparameter optimization framework. This integration allows you to automatically search for optimal parameter configurations for your experiments.

The integration works through experiment hooks that define which parameters to optimize and how to evaluate results. Your experiment code remains unchanged - parameter values are automatically replaced with trial suggestions during optimization runs.

## Installation

The Optuna plugin requires the full PyComex installation:

```bash
pip install pycomex[full]
```

## Quick Start

Here's a minimal example optimizing a learning rate parameter:

```python title="my_experiment.py"
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

# Parameters to optimize
LEARNING_RATE: float = 0.1

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial) -> dict:
    """Define which parameters to optimize and their ranges."""
    return {
        'LEARNING_RATE': trial.suggest_float('LEARNING_RATE', 1e-4, 1e-1, log=True)
    }

@experiment.hook('__optuna_objective__')
def extract_objective(e: Experiment) -> float:
    """Extract the metric to optimize (maximize by default)."""
    return e['results/accuracy']

@experiment
def run_experiment(e: Experiment):
    """Your experiment code uses the optimized parameters."""
    accuracy = train_model(learning_rate=e.LEARNING_RATE)
    e['results/accuracy'] = accuracy

experiment.run_if_main()
```

Run optimization trials:

```bash
# Run a single trial
pycomex optuna run my_experiment.py

# View results
pycomex optuna list
pycomex optuna info my_experiment
```

## Configuration File Support

The Optuna plugin supports both Python experiment modules (`.py`) and YAML configuration files (`.yml`/`.yaml`). This allows you to optimize parameter variations without duplicating code:

**Base experiment with Optuna hooks:**

```python title="training.py"
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

LEARNING_RATE: float = 0.001
BATCH_SIZE: int = 32

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial):
    return {
        'LEARNING_RATE': trial.suggest_float('LEARNING_RATE', 1e-5, 1e-2, log=True),
        'BATCH_SIZE': trial.suggest_int('BATCH_SIZE', 16, 128, step=16)
    }

@experiment.hook('__optuna_objective__')
def extract_objective(e: Experiment) -> float:
    return e['results/accuracy']

@experiment
def run_experiment(e: Experiment):
    accuracy = train_model(e.LEARNING_RATE, e.BATCH_SIZE)
    e['results/accuracy'] = accuracy

experiment.run_if_main()
```

**Config file extending the base:**

```yaml title="training_config.yml"
extend: training.py
parameters:
  NUM_EPOCHS: 50
  MODEL_NAME: "resnet50"
```

Run optimization with config file:

```bash
pycomex optuna run training_config.yml
```

This combines the benefits of experiment configuration files with Optuna optimization.

## Understanding the Hooks

### `__optuna_parameters__` - Define Search Space

This hook defines which parameters to optimize. It receives the Optuna trial object and returns a dictionary of parameter suggestions:

```python
@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial) -> dict:
    return {
        # Float with log scale (good for learning rates)
        'LEARNING_RATE': trial.suggest_float('LEARNING_RATE', 1e-5, 1e-1, log=True),

        # Integer with step
        'BATCH_SIZE': trial.suggest_int('BATCH_SIZE', 16, 128, step=16),

        # Categorical choice
        'OPTIMIZER': trial.suggest_categorical('OPTIMIZER', ['adam', 'sgd', 'rmsprop']),
    }
```

Common suggestion methods:
- `suggest_float(name, low, high, log=False)` - Continuous values
- `suggest_int(name, low, high, step=1)` - Discrete values
- `suggest_categorical(name, choices)` - Predefined options

See [Optuna's API reference](https://optuna.readthedocs.io/en/stable/reference/trial.html) for all available methods.

### `__optuna_objective__` - Extract Metric

This hook extracts the value to optimize from your experiment results. It's called after the experiment completes:

```python
@experiment.hook('__optuna_objective__')
def extract_objective(e: Experiment) -> float:
    """Return the metric to maximize."""
    return e['results/accuracy']
```

By default, Optuna **maximizes** the objective. To minimize instead:

```python
@experiment.hook('__optuna_direction__')
def optimization_direction(e: Experiment) -> str:
    return 'minimize'  # Default is 'maximize'
```

### Optional Customization

You can customize the optimization algorithm by providing a custom sampler:

```python
import optuna

@experiment.hook('__optuna_sampler__', replace=True)
def configure_sampler(e: Experiment):
    return optuna.samplers.TPESampler(n_startup_trials=10)
```

## Running Optimization

Execute optimization trials using the `pycomex optuna run` command:

```bash
# Single trial
pycomex optuna run my_experiment.py

# Multiple trials (run in a loop or script)
for i in {1..50}; do
    pycomex optuna run my_experiment.py
done
```

Each trial:
1. Receives parameter suggestions from Optuna
2. Runs your experiment with those parameters
3. Reports the objective value back to the study

All trials are stored in a SQLite database in the `.optuna` folder at your experiment base path.

## Managing Studies

### List Studies

View all optimization studies in the current directory:

```bash
pycomex optuna list
```

### View Study Details

Show detailed information about trials:

```bash
pycomex optuna info my_experiment
```

This displays:
- Study summary (best trial, best value)
- Best parameter configuration
- Table of all trials with their parameters and objectives

### Delete Studies

Clean up optimization studies:

```bash
# Delete specific study
pycomex optuna delete my_experiment

# Delete all studies (with confirmation)
pycomex optuna delete --all
```

## Example: Multi-Parameter Optimization

Here's a more complete example optimizing multiple hyperparameters:

```python title="neural_net.py"
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

# Parameters with sensible defaults
LEARNING_RATE: float = 0.01
BATCH_SIZE: int = 32
DROPOUT: float = 0.5
NUM_LAYERS: int = 3

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial) -> dict:
    return {
        'LEARNING_RATE': trial.suggest_float('LEARNING_RATE', 1e-5, 1e-2, log=True),
        'BATCH_SIZE': trial.suggest_int('BATCH_SIZE', 16, 128, step=16),
        'DROPOUT': trial.suggest_float('DROPOUT', 0.1, 0.7),
        'NUM_LAYERS': trial.suggest_int('NUM_LAYERS', 2, 5),
    }

@experiment.hook('__optuna_objective__')
def extract_objective(e: Experiment) -> float:
    return e['results/val_accuracy']

@experiment
def run_experiment(e: Experiment):
    """Train model with current hyperparameters."""
    e.log(f'Training with LR={e.LEARNING_RATE}, BS={e.BATCH_SIZE}')

    # Your training code here
    model = create_model(num_layers=e.NUM_LAYERS, dropout=e.DROPOUT)
    val_accuracy = train_and_evaluate(model, e.LEARNING_RATE, e.BATCH_SIZE)

    # Store results
    e['results/val_accuracy'] = val_accuracy
    e.log(f'Validation accuracy: {val_accuracy:.4f}')

experiment.run_if_main()
```

Run 100 optimization trials:

```bash
for i in {1..100}; do
    pycomex optuna run neural_net.py
done
```

Check the best configuration:

```bash
pycomex optuna info neural_net
```

## Key Points

- **Non-intrusive**: Add hooks to existing experiments without changing core logic
- **Persistent storage**: Studies are saved in `.optuna` SQLite databases
- **CLI integration**: Dedicated commands for running and inspecting optimizations
- **Standard Optuna**: Full access to Optuna's algorithms and features

For advanced optimization strategies (pruning, multi-objective, distributed optimization), refer to the [Optuna documentation](https://optuna.readthedocs.io/).
