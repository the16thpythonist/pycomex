# PyComex ⋅ Computational Experiments

The `pycomex` package is a microframework for Python that simplifies the implementation, execution and management of *computational experiments*. The framework defines a natural way of implementing computational experiments in the form of individual Python scripts that automatically manage their own results, metadata, and artifacts.

**💡 Note.** Speaking in terms of other existing technologies, pycomex aims to be an opinionated alternative to [Hydra Configs](https://hydra.cc/docs/intro/) and a local version of [Weights & Biases](https://wandb.ai/), but with a focus on flexibility and extensibility.

## Installation

### Package Installation

Install the stable version from PyPI:

```bash
pip install pycomex
```

### Development Installation

For the latest development version, clone the repository:

```bash
git clone https://github.com/the16thpythonist/pycomex.git
cd pycomex
pip install -e .
```

Or using uv (recommended):

```bash
git clone https://github.com/the16thpythonist/pycomex.git
cd pycomex
uv pip install -e .
```

### Requirements

- Python 3.8 or higher
- Core dependencies are automatically installed with the package

## Quickstart

PyComex turns your computational experiments into structured, reproducible, and automatically archived processes. Here's how to get started:

### Basic Experiment Structure

Each experiment is a Python module with uppercase variables as parameters and a main function decorated with `@Experiment()`:

```python
# my_first_experiment.py
"""
This docstring describes what the experiment does and is saved as metadata.
"""

from pycomex.functional.experiment import Experiment
from pycomex.utils import file_namespace, folder_path

# Experiment parameters (uppercase variables are auto-detected)
LEARNING_RATE: float = 0.001
EPOCHS: int = 100
MODEL_NAME: str = "simple_nn"

# Enable debug mode to reuse the same archive folder
__DEBUG__ = True

@Experiment(
    base_path=folder_path(__file__),  # Results stored relative to this file
    namespace=file_namespace(__file__),  # Creates folder based on filename
    glob=globals(),  # Gives access to parameters
)
def experiment(e: Experiment) -> None:
    e.log("Starting training experiment...")

    # Store metadata (creates nested structure in JSON)
    e["config/learning_rate"] = LEARNING_RATE
    e["config/epochs"] = EPOCHS
    e["model/name"] = MODEL_NAME

    # Simulate training loop
    for epoch in range(EPOCHS):
        loss = 1.0 / (epoch + 1)  # Dummy loss that decreases

        # Track metrics over time
        e.track("metrics/loss", loss)
        e.track("metrics/epoch", epoch)

        if epoch % 20 == 0:
            e.log(f"Epoch {epoch}: Loss = {loss:.4f}")

    # Save final results
    e["results/final_loss"] = loss
    e.commit_raw("training_log.txt", f"Final loss: {loss}")

# Run the experiment when script is executed directly
experiment.run_if_main()
```

### Running Your Experiment

Execute your experiment by running the Python file:

```bash
python my_first_experiment.py
```

### Generated Archive Structure

PyComex automatically creates this organized structure:

```
my_first_experiment/
└── debug/  # or timestamped folder if __DEBUG__ = False
    ├── experiment_meta.json    # Experiment metadata
    ├── experiment_data.json    # All tracked data and metrics
    ├── experiment_out.log      # Complete execution log
    ├── experiment_code.py      # Snapshot of your experiment code
    ├── analysis.py            # Ready-to-run analysis code
    ├── training_log.txt       # Your committed artifacts
    └── tracked/               # Auto-generated visualizations
        └── metrics_loss.png   # Automatic plot of tracked metrics
```

### Command Line Interface

PyComex provides powerful CLI tools:

```bash
# List recent experiments
pycomex archive list

# View basic information about experiment archive
pycomex archive info

# Create new experiment from template
pycomex template experiment my_new_experiment.py
```

### Parameter Overrides

Override parameters from the command line without modifying code:

```bash
python my_first_experiment.py --LEARNING_RATE 0.01 --EPOCHS 50
```

### Key Features in Action

1. **Automatic Archiving**: Every run creates a complete record
2. **Metadata Tracking**: Store structured data with `e["path/key"] = value`
3. **Time Series Tracking**: Use `e.track()` for metrics that change over time
4. **Auto Visualization**: PyComex automatically plots tracked numerical data
5. **Reloadability**: Load any experiment back into memory for analysis
6. **Debug Mode**: Use `__DEBUG__ = True` for iterative development

### Next Steps

- Explore parameter inheritance and experiment composition
- Learn about hooks for custom behavior injection
- Discover advanced archiving and analysis features
- Check out plugin integrations (Weights & Biases, notifications)

This quickstart covers the essentials. PyComex's real power emerges as your experimental needs grow more complex—it scales from simple scripts to sophisticated experimental pipelines while maintaining the same clean, structured approach.