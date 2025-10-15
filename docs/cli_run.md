# Running Experiments

## pycomex run

Execute an experiment from a Python module or YAML config file.

### Syntax

```bash
pycomex run PATH [--PARAM1=value] [--PARAM2=value] ...
```

### Running from Python Files

```bash
# Basic execution
pycomex run my_experiment.py

# Override parameters
pycomex run my_experiment.py --LEARNING_RATE=0.001 --EPOCHS=50

# Multiple overrides
pycomex run neural_network.py \
  --MODEL="resnet50" \
  --BATCH_SIZE=64 \
  --LEARNING_RATE=0.01 \
  --USE_CUDA=True
```

### Running from Config Files

```bash
# Run YAML config
pycomex run config.yml

# Override config parameters
pycomex run config.yml --BATCH_SIZE=128
```

## Parameter Override System

### How It Works

1. **Parameters are detected automatically** - Uppercase module-level variables
2. **Types are inferred** - From type annotations
3. **CLI format** - `--PARAM_NAME=value`
4. **Type conversion** - Automatic based on annotations

### Example

```python
# In experiment file
LEARNING_RATE: float = 0.001
BATCH_SIZE: int = 32
MODEL_NAME: str = "resnet50"
USE_CUDA: bool = True
LAYER_SIZES: list = [128, 64, 32]
```

```bash
# Override any parameter
pycomex run experiment.py \
  --LEARNING_RATE=0.01 \
  --BATCH_SIZE=64 \
  --MODEL_NAME="vgg16" \
  --USE_CUDA=False \
  --LAYER_SIZES="[256, 128, 64]"
```

### Type Handling

```bash
# Strings (quotes optional if no spaces)
--NAME="my_model"
--NAME=my_model

# Numbers
--EPOCHS=100
--LEARNING_RATE=0.001

# Booleans
--USE_CUDA=True
--DEBUG=False

# Lists/dicts (JSON format)
--LAYERS="[64, 128, 256]"
--CONFIG='{"optimizer": "adam", "lr": 0.001}'
```

## Special Parameters

### __DEBUG__ - Reusable Debug Folder

Creates a fixed "debug" folder instead of timestamped folders. Overwrites on each run.

```python
# In experiment file
__DEBUG__ = True
```

```bash
# Each run overwrites results/namespace/debug/
python experiment.py --PARAM1=test1
python experiment.py --PARAM1=test2  # Overwrites previous
```

Use for rapid iteration during development.

### __REPRODUCIBLE__ - Enable Reproducibility

Captures environment details for exact reproduction later.

```python
# In experiment file
__REPRODUCIBLE__ = True
```

Saves:
- Python version
- All installed packages with versions
- Source packages (if editable installs)
- Environment variables
- OS and CUDA information

```bash
# Run reproducible experiment
pycomex run experiment.py

# Results saved with environment snapshot
# Later reproduction is possible even on different machines
```

## pycomex reproduce

Reproduce a previously executed experiment with exact environment recreation.

### Syntax

```bash
pycomex reproduce EXPERIMENT_PATH [--env-only] [--PARAM=value]
```

### Basic Reproduction

```bash
# Reproduce from archive folder
pycomex reproduce results/my_exp/2024-01-15_10-30-45

# Reproduce from ZIP archive
pycomex reproduce experiment_backup.zip
```

### Environment-Only Mode

Create the environment without running the experiment:

```bash
pycomex reproduce results/my_exp/timestamp --env-only
```

Useful for:
- Inspecting dependencies before running
- Creating environment for manual runs
- Debugging environment issues

### Override Parameters

```bash
# Reproduce with different parameters
pycomex reproduce results/my_exp/timestamp \
  --LEARNING_RATE=0.001 \
  --BATCH_SIZE=32
```

### How Reproduction Works

1. **Validates reproducibility** - Checks experiment was run with `__REPRODUCIBLE__=True`
2. **Detects Python version** - From saved dependencies
3. **Shows environment comparison** - Original vs current (OS, CUDA, env vars)
4. **Creates virtual environment** - Using `uv` with detected Python version
5. **Installs dependencies** - Exact versions from metadata
6. **Installs source packages** - From `.sources` folder if present
7. **Runs experiment** - With original (or overridden) parameters

### Environment Comparison

Before reproduction, you'll see:

```
Environment Comparison:
┌─────────────────┬──────────────┬──────────────┐
│ Property        │ Original     │ Current      │
├─────────────────┼──────────────┼──────────────┤
│ OS              │ Linux        │ Linux        │
│ Python          │ 3.10.12      │ 3.11.5       │
│ CUDA Available  │ True         │ True         │
│ CUDA_VERSION    │ 12.1         │ 12.2         │
└─────────────────┴──────────────┴──────────────┘
```

### Requirements

Experiments must be run with:
```python
__REPRODUCIBLE__ = True
```

Without this flag, reproduction is not possible.

### ZIP Archive Support

```bash
# Archive experiments for sharing
pycomex archive compress --select="m['name'] == 'my_exp'" \
  --name=my_exp.zip

# Share ZIP file with colleagues

# They can reproduce directly
pycomex reproduce my_exp.zip
```

ZIP archives are automatically extracted before reproduction.

## Common Patterns

### Development Workflow

```bash
# Use debug mode during development
python experiment.py  # __DEBUG__ = True in file

# When ready, run properly timestamped experiments
python experiment.py --__DEBUG__=False
```

### Parameter Sweep

```bash
# Run multiple configurations
for lr in 0.001 0.01 0.1; do
  pycomex run experiment.py --LEARNING_RATE=$lr
done

# Or use shell expansion
pycomex run experiment.py --LEARNING_RATE=0.001
pycomex run experiment.py --LEARNING_RATE=0.01
pycomex run experiment.py --LEARNING_RATE=0.1
```

### Production-Ready Experiments

```python
# In experiment file
__DEBUG__ = False          # Timestamped folders
__REPRODUCIBLE__ = True    # Capture environment
```

```bash
# Run and archive
pycomex run experiment.py --CONFIG="production"

# Backup for later
pycomex archive compress \
  --select="m['name'] == 'experiment' and m['status'] == 'done'" \
  --name=production_run.zip
```

### Reproduce and Modify

```bash
# Reproduce a successful experiment with tweaks
pycomex reproduce results/successful_exp/timestamp \
  --EPOCHS=100 \
  --BATCH_SIZE=64
```
