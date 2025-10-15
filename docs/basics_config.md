# Experiment Configuration Files

Experiment configuration files provide a lightweight way to create parameter variations of existing experiments without duplicating code. Instead of creating new Python modules, you can define YAML configuration files that extend base experiments and override specific parameters.

## Why Use Configuration Files?

When conducting computational experiments, you often need to run the same experiment with different parameter values. Configuration files solve this problem elegantly:

- **Avoid Code Duplication**: No need to create new Python files for each parameter variation
- **Clear Parameter Management**: Parameters are explicitly defined in a human-readable format
- **Easy Comparison**: Multiple configurations can exist side-by-side for comparison
- **Version Control Friendly**: Small YAML files are easier to track and review than duplicated code
- **Rapid Experimentation**: Quickly test different parameter combinations without touching code

## Basic Structure

A PyComex configuration file is a YAML file with two required fields:

```yaml
extend: base_experiment.py
parameters:
  PARAMETER_NAME: value
```

### Required Fields

#### `extend`
The path to the base experiment Python module that this configuration extends. This can be:
- A relative path: `experiment.py` or `../base/experiment.py`
- An absolute path: `/path/to/experiment.py`

The base experiment must be a valid PyComex experiment module with an `Experiment` decorator.

#### `parameters`
A dictionary of parameter names and their values. These parameters override the default values defined in the base experiment. Only parameters that you want to change need to be specified here.

```yaml
parameters:
  NUM_ITERATIONS: 1000
  LEARNING_RATE: 0.001
  MODEL_NAME: "resnet50"
```

### Optional Fields

#### `name`
Custom name for this configuration. If not specified, defaults to the filename without extension.

```yaml
name: high_learning_rate_experiment
```

#### `description`
Documentation for this configuration. Supports multi-line strings using YAML's pipe `|` operator.

```yaml
description: |
  This configuration tests the model with a higher learning rate
  to evaluate convergence speed and stability.
```

#### `base_path`
Custom base path for the experiment archive. If not specified, uses the directory containing the config file.

```yaml
base_path: /data/experiments
```

#### `namespace`
Custom namespace for organizing experiment results. If not specified, defaults to `results/{config_name}`.

```yaml
namespace: results/parameter_sweeps/lr_variations
```

#### `pycomex`
A marker flag (typically set to `true`) that explicitly identifies this as a PyComex configuration file. This is optional but recommended for clarity.

```yaml
pycomex: true
```

## Environment Variable Interpolation

PyComex configuration files support environment variable interpolation, allowing you to inject dynamic values from your environment into your configuration. This is particularly useful for:

- **Sensitive Information**: Keeping API keys, passwords, and credentials out of version control
- **Environment-Specific Paths**: Different data paths for local development vs. production
- **Dynamic Configuration**: CI/CD pipelines that inject configuration values
- **Shared Configurations**: Team members using different local paths without modifying config files

### Basic Syntax

Use `${VARIABLE_NAME}` to reference environment variables:

```yaml
extend: experiment.py
parameters:
  DATA_PATH: ${DATA_ROOT}/training_data
  API_KEY: ${OPENAI_API_KEY}
  MODEL_NAME: "gpt-4"
```

When the configuration is loaded, PyComex will replace `${DATA_ROOT}` with the value of the `DATA_ROOT` environment variable and `${OPENAI_API_KEY}` with your API key.

### Default Values

Provide fallback values using the `${VARIABLE_NAME:-default}` syntax:

```yaml
extend: experiment.py
parameters:
  DATA_PATH: ${DATA_ROOT:-/tmp/data}
  BATCH_SIZE: ${BATCH_SIZE:-32}
  LOG_LEVEL: ${LOG_LEVEL:-INFO}
```

If the environment variable is not set, the default value after `:-` will be used. This makes configurations more portable and reduces the need to set every environment variable.

### Escaping Dollar Signs

If you need a literal dollar sign in your configuration, use `$$`:

```yaml
parameters:
  PRICE: $$50
  # Results in: "PRICE: $50"
```

### Usage Examples

**Development vs. Production:**

```yaml
# config.yml
extend: training.py
base_path: ${EXPERIMENT_BASE_PATH:-./experiments}
parameters:
  DATA_PATH: ${DATA_ROOT}/processed
  MODEL_CHECKPOINT: ${MODEL_DIR}/checkpoints
  NUM_WORKERS: ${NUM_WORKERS:-4}
```

Set environment variables differently per environment:

```bash
# Development
export DATA_ROOT=/home/user/data
export MODEL_DIR=/home/user/models
pycomex run config.yml

# Production
export DATA_ROOT=/mnt/shared/data
export MODEL_DIR=/mnt/shared/models
export NUM_WORKERS=16
pycomex run config.yml
```

**Keeping Secrets Out of Version Control:**

```yaml
# config.yml
extend: api_experiment.py
parameters:
  API_KEY: ${OPENAI_API_KEY}
  DATABASE_URL: ${DB_CONNECTION_STRING}
  SECRET_TOKEN: ${AUTH_TOKEN}
```

Store secrets in a `.env` file (add to `.gitignore`):

```bash
# .env (NOT committed to version control)
OPENAI_API_KEY=sk-...
DB_CONNECTION_STRING=postgresql://...
AUTH_TOKEN=abc123...
```

Load environment variables before running:

```bash
source .env
pycomex run config.yml
```

**CI/CD Integration:**

```yaml
# ci_config.yml
extend: benchmark.py
parameters:
  DATA_PATH: ${CI_DATA_PATH}
  OUTPUT_DIR: ${CI_ARTIFACT_DIR}
  COMMIT_SHA: ${CI_COMMIT_SHA:-unknown}
  BUILD_NUMBER: ${CI_BUILD_NUMBER:-0}
```

### Error Handling

If you reference an environment variable without providing a default, and that variable is not set, PyComex will raise a clear error:

```
ConfigInterpolationError: Environment variable "DATA_ROOT" is not set and no default value provided.
Either set the environment variable or use ${DATA_ROOT:-default} syntax.
```

This helps catch configuration errors early before experiments start running.

## Examples

### Minimal Configuration

The simplest possible configuration file:

```yaml
extend: 02_basic.py
parameters:
  NUM_WORDS: 100
  REPETITIONS: 5
```

This extends the `02_basic.py` experiment and overrides just two parameters.

### Full Configuration

A comprehensive example using all available fields:

```yaml
# Marker to identify this as a PyComex config
pycomex: true

# Extend the base experiment
extend: training_experiment.py

# Configuration name
name: high_lr_experiment

# Base path for experiment archives
base_path: /data/ml_experiments

# Namespace for organizing results
namespace: results/learning_rate_sweep/high_lr

# Description of this configuration
description: |
  High learning rate configuration for the training experiment.

  This configuration tests model convergence with an elevated learning rate
  of 0.01 compared to the baseline of 0.001. We expect faster initial
  convergence but potentially less stable training.

  Related configurations:
  - low_lr.yml: Learning rate 0.0001
  - baseline.yml: Learning rate 0.001 (default)

# Parameter overrides
parameters:
  LEARNING_RATE: 0.01
  BATCH_SIZE: 32
  NUM_EPOCHS: 100
  MODEL_ARCHITECTURE: "resnet50"
  OPTIMIZER: "adam"
  __REPRODUCIBLE__: true
```

### Parameter Sweep Example

Create multiple configuration files for parameter sweeps:

**config_lr_001.yml:**
```yaml
extend: training.py
name: lr_0.001
parameters:
  LEARNING_RATE: 0.001
```

**config_lr_005.yml:**
```yaml
extend: training.py
name: lr_0.005
parameters:
  LEARNING_RATE: 0.005
```

**config_lr_010.yml:**
```yaml
extend: training.py
name: lr_0.010
parameters:
  LEARNING_RATE: 0.010
```

## Running Configuration Files

### Command Line Interface

Execute a configuration file using the `pycomex run` command:

```bash
pycomex run config.yml
```

You can also override parameters from the command line:

```bash
pycomex run config.yml --PARAMETER_NAME="new_value"
```

### VSCode Extension

If you have the PyComex VSCode extension installed, configuration files will display a green **Run** button in the top-right corner of the editor. Click this button to execute the experiment directly from VSCode.

The extension automatically recognizes PyComex configuration files by detecting the `extend:` and `parameters:` fields.

### Programmatic Execution

Load and run a configuration file from Python code:

```python
from pycomex.functional.experiment import Experiment

# Load experiment from config
experiment = Experiment.from_config(config_path="config.yml")

# Execute the experiment
experiment.run()
```

## Creating Configuration Files

### Manual Creation

Simply create a new `.yml` file with the required fields:

```yaml
extend: base_experiment.py
parameters:
  PARAM1: value1
  PARAM2: value2
```

### Using the CLI Template Command

PyComex provides a command to generate configuration files from existing experiments:

```bash
pycomex template config -e experiment.py -n my_config
```

This will:
1. Analyze the base experiment to extract all parameters
2. Create a new `my_config.yml` file
3. Include all parameters with their default values
4. Add helpful comments and structure

You can then edit the generated file to modify only the parameters you want to change.

## Validating Configuration Files

PyComex provides a comprehensive validation command to check configuration files for errors before running experiments. This helps catch issues early and ensures your configurations are correct.

### Basic Validation

Validate a configuration file:

```bash
pycomex template validate config.yml
```

This will check:

- **File Existence**: Config file exists and is readable
- **YAML Syntax**: Valid YAML formatting
- **Required Fields**: Presence of `extend` and `parameters` fields
- **Base Experiment**: Extended experiment file exists and is importable
- **Parameter Names**: All parameters exist in the base experiment (with typo detection)
- **Mixins**: All included mixin files exist and are valid
- **Environment Variables**: Referenced environment variables are available
- **Path Fields**: No invalid characters in paths

### Validation Output

The validator provides clear, color-coded output:

```
╭─────────────────────────────────────────────────╮
│     Config Validation: config.yml               │
╰─────────────────────────────────────────────────╯

✓ File exists and is readable
✓ YAML syntax is valid
✓ Required fields present (extend, parameters)
✓ Base experiment found: training.py
⚠ 3 parameters checked (1 warnings)
    Parameter 'LEARNINNG_RATE' not found (did you mean 'LEARNING_RATE'?)
✓ No mixins specified
✓ All 2 environment variables available
✓ Path fields are valid

Validation: PASSED (1 warning(s))
```

### Verbose Mode

Get detailed information about all checks:

```bash
pycomex template validate config.yml --verbose
```

This shows details for all checks, including successful ones:

```
✓ File exists and is readable
    File path: /path/to/config.yml
    Size: 1.2 KB
✓ YAML syntax is valid
    Parsed successfully
✓ Required fields present (extend, parameters)
    Found: extend, parameters, name, description
...
```

### Warnings vs. Errors

The validator distinguishes between errors (must fix) and warnings (should review):

**Errors** (validation fails):
- File not found or unreadable
- Invalid YAML syntax
- Missing required fields
- Base experiment not found or not importable
- Invalid characters in path fields
- Mixin files not found

**Warnings** (validation passes with warnings):
- Unknown parameter names
- Missing environment variables (without defaults)
- Parameter values that aren't JSON-serializable

### Treating Warnings as Errors

For CI/CD pipelines or strict validation, treat warnings as errors:

```bash
pycomex template validate config.yml --warnings-as-errors
```

This will return a non-zero exit code if any warnings are present.

### Integration with CI/CD

Add validation to your CI pipeline:

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]

jobs:
  validate-configs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install pycomex
      - name: Validate configurations
        run: |
          for config in configs/*.yml; do
            pycomex template validate "$config" --warnings-as-errors
          done
```

### Common Validation Errors

**Unknown Parameter:**

```
⚠ Parameter 'LEARNINNG_RATE' not found (did you mean 'LEARNING_RATE'?)
```

Fix: Correct the typo in your parameter name.

**Missing Environment Variable:**

```
⚠ Environment variable 'DATA_ROOT' is not set and no default value provided
```

Fix: Either set the environment variable or add a default value in the config:
```yaml
DATA_PATH: ${DATA_ROOT:-/tmp/data}
```

**Base Experiment Not Found:**

```
✗ Base experiment not found: ../experiments/training.py
    File does not exist: /path/to/../experiments/training.py
```

Fix: Check the relative path to your base experiment file.

**Invalid Path Characters:**

```
✗ Path validation failed
    name contains invalid characters: experiment/test
```

Fix: The `name` field should not contain path separators. Use `namespace` for hierarchical organization.

### Best Practices

1. **Validate Before Committing**: Run validation on all config files before committing to version control

2. **Automate in CI/CD**: Include config validation in your CI pipeline to catch errors early

3. **Use `--warnings-as-errors` in CI**: Enforce strict validation in automated environments

4. **Fix Typos Early**: The validator's typo detection helps catch parameter name mistakes before running experiments

5. **Check Environment Variables**: Validate with environment variables set to ensure they're available

6. **Validate After Generation**: Always validate after generating configs from templates

## Use Cases

### When to Use Configuration Files

Configuration files are ideal for:

- **Parameter Sweeps**: Testing multiple parameter combinations systematically
- **Ablation Studies**: Comparing variations with individual parameters changed
- **Environment-Specific Settings**: Different configurations for development vs. production
- **Collaborative Research**: Team members can share parameter variations without code changes
- **Reproducibility**: Documenting exact parameters used for specific results

### When to Use Experiment Inheritance

Use Python-based experiment inheritance (`Experiment.extend()`) when you need:

- **Custom Logic**: Adding or modifying hook implementations
- **Programmatic Parameter Computation**: Parameters derived from calculations
- **Code Reuse**: Sharing utility functions across related experiments
- **Complex Configurations**: Logic that goes beyond simple parameter overrides

### When to Create New Experiment Modules

Create a new standalone experiment when:

- **Fundamentally Different Logic**: The experiment does something conceptually different
- **New Analysis**: Requires different data collection or processing
- **Independent Research Direction**: Not a variation of existing work
- **Teaching/Examples**: Demonstrating a specific concept in isolation

## Best Practices

1. **Descriptive Names**: Use clear, meaningful names for configuration files
   - Good: `high_lr_baseline.yml`, `ablation_no_dropout.yml`
   - Bad: `config1.yml`, `test.yml`

2. **Documentation**: Always include a description explaining the purpose and any notable differences from the base experiment

3. **Minimal Overrides**: Only specify parameters that differ from the base experiment. This makes the changes explicit and easier to review.

4. **Organized Structure**: Group related configurations in subdirectories:
   ```
   configs/
   ├── parameter_sweeps/
   │   ├── lr_001.yml
   │   ├── lr_005.yml
   │   └── lr_010.yml
   └── ablations/
       ├── no_dropout.yml
       └── no_batch_norm.yml
   ```

5. **Version Control**: Commit configuration files to version control alongside your experiment code

6. **Special Parameters**: Configuration files support all special parameters like `__DEBUG__`, `__TESTING__`, and `__REPRODUCIBLE__`

## Example Workflow

Here's a typical workflow using configuration files:

1. **Create Base Experiment**: Write your experiment in a Python module (e.g., `training.py`)

2. **Generate Template Config**: Use the CLI to create a config template
   ```bash
   pycomex template config -e training.py -n baseline
   ```

3. **Create Variations**: Copy and modify the baseline config for different parameter sets
   ```bash
   cp baseline.yml high_lr.yml
   # Edit high_lr.yml to change LEARNING_RATE
   ```

4. **Run Experiments**: Execute each configuration
   ```bash
   pycomex run baseline.yml
   pycomex run high_lr.yml
   ```

5. **Analyze Results**: Compare the experiment archives created by each configuration
   ```bash
   pycomex archive list results/baseline
   pycomex archive list results/high_lr
   ```

## Technical Details

### Implementation

Under the hood, `Experiment.from_config()` works by:

1. Loading the YAML file and parsing it into an `ExperimentConfig` object
2. Using `Experiment.extend()` to inherit from the base experiment
3. Updating parameters with the values specified in the configuration
4. Maintaining all the metadata and functionality of the base experiment

This means configuration files have access to all the same features as programmatic experiment inheritance, including hooks, analysis functions, and special parameters.

### Parameter Types

Configuration files support all JSON-serializable parameter types:

- **Numbers**: `42`, `3.14`, `1e-5`
- **Strings**: `"text"`, `'single quotes'`
- **Booleans**: `true`, `false`
- **Lists**: `[1, 2, 3]`, `["a", "b", "c"]`
- **Dictionaries**: `{key: value, nested: {inner: value}}`
- **Null**: `null`

For complex Python objects (e.g., model instances), you'll need to use programmatic experiment inheritance instead.

## Related Documentation

- [Hooks](basics_hooks.md) - Learn about experiment hooks and how they work with inheritance
- [VSCode Extension](tools_vscode.md) - Using the VSCode extension to work with config files
- [Philosophy](philosophy.md) - Understanding PyComex's approach to experiment management
