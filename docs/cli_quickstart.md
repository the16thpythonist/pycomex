# CLI Quick Start

PyComex provides command-line tools for creating, running, and managing computational experiments.

## Installation

Activate the virtual environment to use CLI commands:

```bash
source .venv/bin/activate
```

The main CLI is available as `pycomex` or `pycx` (shorthand).

## Your First Experiment

Create a new experiment:

```bash
pycomex template experiment --name=hello_world
```

This generates `hello_world.py`:

```python
# Parameters (uppercase variables are auto-detected)
MESSAGE: str = "Hello, World!"
REPEAT: int = 1

from pycomex.functional.experiment import Experiment
from pycomex.util import Skippable

@Experiment(
    base_path='results',
    namespace='hello_world',
    glob=globals()
)
def run(e: Experiment):
    for i in range(e.REPEAT):
        print(f"{i+1}: {e.MESSAGE}")

if __name__ == '__main__':
    run.run_if_main()
```

Run it:

```bash
# Direct execution
python hello_world.py

# Or via CLI
pycomex run hello_world.py

# Override parameters
pycomex run hello_world.py --MESSAGE="Hi there" --REPEAT=3
```

Results are saved to `results/hello_world/TIMESTAMP/`.

## Common Workflows

### Quick experimentation with debug mode

```python
# In your experiment file
__DEBUG__ = True  # Creates reusable "debug" folder instead of timestamp
```

```bash
# Run multiple times, overwrites debug folder
python experiment.py --PARAM1=value1
python experiment.py --PARAM1=value2
```

### Creating experiment variations

```bash
# Create base experiment
pycomex template experiment --name=base_model

# Create variant by extending
pycomex template extend --name=variant1 --from=base_model.py

# Or create config file
pycomex template config --name=test_config --from=base_model.py

# Validate config
pycomex template validate test_config.yml

# Run from config
pycomex run test_config.yml
```

### Viewing results

```bash
# List recent experiments
pycomex archive tail

# View statistics
pycomex archive overview

# List only successful experiments
pycomex archive list --select="m['status'] == 'done'"
```

### Cleaning up failed experiments

```bash
# See what will be deleted
pycomex archive list --select="m['status'] == 'failed'"

# Delete failed experiments
pycomex archive delete --select="m['status'] == 'failed'" --yes
```

### Reproducing experiments

```python
# In your experiment, enable reproducibility
__REPRODUCIBLE__ = True
```

```bash
# Run experiment
pycomex run experiment.py

# Later, reproduce exact environment and run
pycomex reproduce results/my_exp/TIMESTAMP
```

## Next Steps

- **[Running Experiments](cli_run.md)** - Learn about `run` and `reproduce` commands
- **[Templates](cli_template.md)** - Code generation for experiments and configs
- **[Archive Management](cli_archive.md)** - Organize and analyze results
- **[Quick Reference](cli_reference.md)** - Complete command list
