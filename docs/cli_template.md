# Template Commands

Code generation for creating experiments, configs, and analysis notebooks.

## pycomex template experiment

Create a new experiment module from template.

### Syntax

```bash
pycomex template experiment --name=NAME [--description=DESC]
```

### Example

```bash
pycomex template experiment \
  --name=neural_network \
  --description="Train a neural network classifier"
```

Creates `neural_network.py`:

```python
"""
Train a neural network classifier
"""

# === PARAMETERS ===
LEARNING_RATE: float = 0.001
EPOCHS: int = 10

from pycomex.functional.experiment import Experiment
from pycomex.util import Skippable

@Experiment(
    base_path='results',
    namespace='neural_network',
    glob=globals()
)
def run(e: Experiment):
    """Main experiment function."""
    # Your experiment code here
    pass

if __name__ == '__main__':
    run.run_if_main()
```

Ready to edit and run immediately.

## pycomex template extend

Create a sub-experiment by extending an existing experiment.

### Syntax

```bash
pycomex template extend --name=NAME --from=BASE_EXPERIMENT.py
```

### Example

```bash
# Create base experiment
pycomex template experiment --name=base_model

# Create variant
pycomex template extend \
  --name=optimized_model \
  --from=base_model.py
```

Creates `optimized_model.py`:

```python
"""
Extension of base_model
"""

from base_model import run as base_run

# === PARAMETERS ===
# Inherited from base_model
LEARNING_RATE: float = 0.001
EPOCHS: int = 10

# New parameters
OPTIMIZER: str = "adam"

from pycomex.functional.experiment import Experiment

@Experiment.extend(
    base_run,
    glob=globals()
)
def run(e: Experiment):
    """Extended experiment with optimizations."""
    pass

if __name__ == '__main__':
    run.run_if_main()
```

### Features

- **Inherits all parameters** from base experiment with current values
- **Hook stubs included** - All hooks from base with docstrings
- **Ready to customize** - Override parameters, add new ones, modify hooks

### Use Cases

```bash
# Create experiment variants
pycomex template extend --name=small_model --from=base.py
pycomex template extend --name=large_model --from=base.py

# Create dataset-specific versions
pycomex template extend --name=mnist_exp --from=generic_exp.py
pycomex template extend --name=cifar_exp --from=generic_exp.py
```

## pycomex template config

Generate a YAML config file from an experiment.

### Syntax

```bash
pycomex template config --name=CONFIG_NAME --from=EXPERIMENT.py
```

### Example

```bash
pycomex template config \
  --name=test_config \
  --from=neural_network.py
```

Creates `test_config.yml`:

```yaml
extend: neural_network.py

parameters:
  LEARNING_RATE: 0.001
  EPOCHS: 10
  BATCH_SIZE: 32
```

### Running Configs

```bash
# Run with config defaults
pycomex run test_config.yml

# Override config parameters
pycomex run test_config.yml --EPOCHS=50
```

### Use Cases

```bash
# Create configs for different scenarios
pycomex template config --name=dev_config --from=model.py
pycomex template config --name=prod_config --from=model.py

# Edit configs
# dev_config.yml: EPOCHS=5, small dataset
# prod_config.yml: EPOCHS=100, full dataset

# Run different configs
pycomex run dev_config.yml
pycomex run prod_config.yml
```

## pycomex template validate

Validate a config file for correctness.

### Syntax

```bash
pycomex template validate CONFIG_PATH [--verbose] [--warnings-as-errors]
```

### Example

```bash
# Basic validation
pycomex template validate test_config.yml

# Detailed output
pycomex template validate test_config.yml --verbose

# Strict mode (warnings fail validation)
pycomex template validate test_config.yml --warnings-as-errors
```

### Validation Checks

| Check | Description |
|-------|-------------|
| **File Exists** | Config file is readable |
| **YAML Syntax** | Valid YAML structure |
| **Required Fields** | Has `extend` and `parameters` |
| **Base Experiment** | Base experiment exists and is valid |
| **Parameter Names** | Match base experiment parameters |
| **Typo Detection** | Suggests corrections for mismatched names |
| **Mixins** | Mixin files exist and are valid |
| **Environment Variables** | Referenced env vars are available |
| **Path Fields** | No invalid characters in paths |

### Output Example

```
Validating: test_config.yml
✓ File exists and is readable
✓ Valid YAML syntax
✓ Required fields present
✓ Base experiment valid: neural_network.py
⚠ Parameter 'LERNING_RATE' not in base (did you mean 'LEARNING_RATE'?)
✓ All paths valid

Status: FAILED (1 warning, 0 errors)
```

### Typo Detection

Automatically suggests corrections:

```yaml
parameters:
  LERNING_RATE: 0.001  # Typo!
```

```
⚠ Parameter 'LERNING_RATE' not in base
  Did you mean: 'LEARNING_RATE'?
```

### Common Usage

```bash
# Validate before running
pycomex template validate config.yml && pycomex run config.yml

# Check all configs
for config in configs/*.yml; do
  pycomex template validate "$config"
done

# CI/CD validation (strict mode)
pycomex template validate config.yml --warnings-as-errors
```

## pycomex template analysis

Create analysis template (Jupyter notebook) for exploring results.

### Syntax

```bash
pycomex template analysis [-t TYPE] [-o OUTPUT]
```

### Options

- `-t, --type` - Template type (currently: `jupyter`)
- `-o, --output` - Output path (default: `analysis`)

### Example

```bash
# Create analysis notebook
pycomex template analysis

# Custom output name
pycomex template analysis -o my_analysis
```

Creates `analysis.ipynb` with boilerplate:

```python
# Cell 1: Load experiments
from pycomex.util import load_experiments

experiments = load_experiments('results/namespace')

# Cell 2: Explore
for exp in experiments:
    print(f"Status: {exp.metadata['status']}")
    print(f"Params: {exp.parameters}")

# Cell 3: Filter and sort
successful = [e for e in experiments if e.metadata['status'] == 'done']
sorted_exps = sorted(successful, key=lambda e: e.parameters['LEARNING_RATE'])

# Cell 4: Visualization
import matplotlib.pyplot as plt

# ... plotting code
```

### Use Cases

```bash
# After running experiments
pycomex run experiment.py --PARAM=value1
pycomex run experiment.py --PARAM=value2
pycomex run experiment.py --PARAM=value3

# Create analysis
pycomex template analysis

# Open in Jupyter
jupyter notebook analysis.ipynb

# Analyze results, create plots, compare parameters
```

## Common Patterns

### Experiment Hierarchy

```bash
# Create base
pycomex template experiment --name=base_model

# Create variants
pycomex template extend --name=model_v1 --from=base_model.py
pycomex template extend --name=model_v2 --from=base_model.py

# Create configs for each
pycomex template config --name=v1_dev --from=model_v1.py
pycomex template config --name=v2_dev --from=model_v2.py
```

### Config-Driven Workflow

```bash
# Create experiment
pycomex template experiment --name=model

# Create multiple configs
pycomex template config --name=small --from=model.py
pycomex template config --name=medium --from=model.py
pycomex template config --name=large --from=model.py

# Edit configs with different scales
# small.yml: HIDDEN_SIZE=64, LAYERS=2
# medium.yml: HIDDEN_SIZE=128, LAYERS=4
# large.yml: HIDDEN_SIZE=256, LAYERS=8

# Validate all
for cfg in small.yml medium.yml large.yml; do
  pycomex template validate "$cfg"
done

# Run all
pycomex run small.yml
pycomex run medium.yml
pycomex run large.yml
```

### CI/CD Integration

```bash
# In your CI pipeline
#!/bin/bash
set -e

# Validate all configs
for config in configs/*.yml; do
  echo "Validating $config"
  pycomex template validate "$config" --warnings-as-errors
done

# Run tests
pycomex run test_config.yml

echo "All validations passed!"
```

### Analysis Workflow

```bash
# Run experiment suite
for lr in 0.001 0.01 0.1; do
  pycomex run model.py --LEARNING_RATE=$lr
done

# Create analysis notebook
pycomex template analysis -o lr_analysis

# Analyze in Jupyter
jupyter notebook lr_analysis.ipynb

# Results: plots showing learning rate impact
```

## Best Practices

### Naming Conventions

```bash
# Clear, descriptive names
pycomex template experiment --name=bert_classifier
pycomex template extend --name=bert_large --from=bert_classifier.py

# Config names indicate purpose
pycomex template config --name=bert_dev --from=bert_classifier.py
pycomex template config --name=bert_prod --from=bert_classifier.py
```

### Validation Before Running

```bash
# Always validate configs before execution
validate_and_run() {
  if pycomex template validate "$1"; then
    pycomex run "$1"
  else
    echo "Validation failed: $1"
    exit 1
  fi
}

validate_and_run config.yml
```

### Organize Configs

```
project/
├── experiments/
│   ├── model.py
│   ├── model_v2.py
│   └── model_v3.py
├── configs/
│   ├── dev/
│   │   ├── model_dev.yml
│   │   └── model_v2_dev.yml
│   └── prod/
│       ├── model_prod.yml
│       └── model_v2_prod.yml
└── results/
```

```bash
# Validate all dev configs
pycomex template validate configs/dev/*.yml

# Run production configs
pycomex run configs/prod/model_prod.yml
```
