# CLI Quick Reference

Complete command reference for PyComex CLI (`pycomex` or `pycx`).

## Main Commands

| Command | Description |
|---------|-------------|
| `pycomex run` | Execute an experiment |
| `pycomex reproduce` | Reproduce an experiment with environment recreation |
| `pycomex template` | Code generation commands |
| `pycomex archive` | Archive management commands |

## pycomex run

Execute an experiment from Python module or YAML config.

```bash
pycomex run PATH [--PARAM=value ...]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `PATH` | string | Path to `.py` or `.yml` file |
| `--PARAM=value` | varies | Override any parameter |

### Examples

```bash
pycomex run experiment.py
pycomex run experiment.py --LEARNING_RATE=0.01
pycomex run config.yml --BATCH_SIZE=64
```

## pycomex reproduce

Reproduce experiment with exact environment recreation.

```bash
pycomex reproduce PATH [OPTIONS] [--PARAM=value ...]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `PATH` | string | Archive folder or ZIP file |
| `--env-only` | flag | Create environment only, don't run |
| `--PARAM=value` | varies | Override parameters |

### Examples

```bash
pycomex reproduce results/exp/2024-01-15_10-30-45
pycomex reproduce experiment.zip --env-only
pycomex reproduce results/exp/timestamp --LEARNING_RATE=0.001
```

## pycomex template

Code generation commands.

### template experiment

Create new experiment from template.

```bash
pycomex template experiment --name=NAME [--description=DESC]
```

| Option | Required | Description |
|--------|----------|-------------|
| `-n, --name` | Yes | Experiment module name |
| `-d, --description` | No | Experiment description |

```bash
pycomex template experiment --name=my_exp
```

### template extend

Create sub-experiment by extending existing one.

```bash
pycomex template extend --name=NAME --from=EXPERIMENT.py
```

| Option | Required | Description |
|--------|----------|-------------|
| `-n, --name` | Yes | New experiment name |
| `--from` | Yes | Base experiment path |

```bash
pycomex template extend --name=variant --from=base.py
```

### template config

Generate YAML config from experiment.

```bash
pycomex template config --name=NAME --from=EXPERIMENT.py
```

| Option | Required | Description |
|--------|----------|-------------|
| `-n, --name` | Yes | Config file name |
| `--from` | Yes | Source experiment path |

```bash
pycomex template config --name=test_cfg --from=exp.py
```

### template validate

Validate config file.

```bash
pycomex template validate PATH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `PATH` | Config file path (required) |
| `-v, --verbose` | Detailed validation output |
| `--warnings-as-errors` | Fail on warnings |

```bash
pycomex template validate config.yml
pycomex template validate config.yml --verbose
```

### template analysis

Create analysis notebook.

```bash
pycomex template analysis [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-t, --type` | `jupyter` | Template type |
| `-o, --output` | `analysis` | Output path |

```bash
pycomex template analysis
pycomex template analysis -o my_analysis
```

## pycomex archive

Archive management commands. All accept `--path` to specify archive location.

### Common Options

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `./results` | Archive directory path |
| `--select` | None | Filter expression |

### archive list

List experiments with status.

```bash
pycomex archive list [--select=EXPR]
```

```bash
pycomex archive list
pycomex archive list --select="m['status'] == 'done'"
```

### archive tail

Show recent experiment details.

```bash
pycomex archive tail [-n NUM] [--select=EXPR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-n, --num` | `5` | Number of experiments |

```bash
pycomex archive tail
pycomex archive tail -n 10
pycomex archive tail --select="m['has_error']"
```

### archive overview

Display comprehensive archive statistics.

```bash
pycomex archive overview [--select=EXPR]
```

```bash
pycomex archive overview
pycomex archive overview --select="p['MODEL'] == 'resnet'"
```

### archive info

Display archive statistics (similar to overview).

```bash
pycomex archive info [--select=EXPR]
```

### archive delete

Delete experiments from archive.

```bash
pycomex archive delete [--select=EXPR | --all] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--select` | Selection expression (required unless `--all`) |
| `--all` | Select all experiments |
| `--yes` | Skip confirmation |
| `-v, --verbose` | Detailed output |

```bash
pycomex archive delete --select="m['status'] == 'failed'"
pycomex archive delete --all --yes
```

### archive compress

Compress experiments to ZIP.

```bash
pycomex archive compress [--select=EXPR | --all] [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--select` | None | Selection expression |
| `--all` | - | Select all |
| `--name` | `results.zip` | Output filename |
| `-v, --verbose` | - | Detailed output |

```bash
pycomex archive compress --all
pycomex archive compress --select="m['status'] == 'done'" --name=good.zip
```

### archive modify

Bulk modify parameters or metadata.

```bash
pycomex archive modify [--select=EXPR | --all] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--select` | Selection expression (required unless `--all`) |
| `--all` | Select all |
| `--modify-parameters` | Python code to modify `p` dict |
| `--modify-metadata` | Python code to modify `m` dict |
| `--dry-run` | Preview without saving |
| `-v, --verbose` | Detailed output |

```bash
pycomex archive modify --all --modify-parameters="p['LR'] *= 10"
pycomex archive modify --select="..." --modify-metadata="m['tag'] = 'v2'"
pycomex archive modify --all --modify-parameters="..." --dry-run
```

## Selection Expressions

Used with `--select` option in archive commands.

### Variables

| Variable | Alias | Description |
|----------|-------|-------------|
| `m` | `metadata` | Metadata dictionary |
| `p` | `parameters`, `params` | Parameters dictionary |

### Common Expressions

```bash
# Status
--select="m['status'] == 'done'"
--select="m['status'] == 'failed'"
--select="m['has_error'] == True"

# Parameters
--select="p['LEARNING_RATE'] < 0.01"
--select="p['BATCH_SIZE'] == 32"
--select="p['MODEL'] == 'resnet'"

# Time/Duration
--select="m['duration'] > 100"
--select="m['start_time'] > '2024-01-10'"

# Combined
--select="m['status'] == 'done' and p['LEARNING_RATE'] > 0.01"
--select="m['duration'] > 60 and p['BATCH_SIZE'] in [32, 64]"

# String operations
--select="'test' in m.get('name', '')"
--select="m['name'].startswith('debug')"
```

## Special Parameters

Parameters that control experiment behavior:

| Parameter | Type | Description |
|-----------|------|-------------|
| `__DEBUG__` | bool | Creates reusable `debug/` folder instead of timestamp |
| `__REPRODUCIBLE__` | bool | Saves environment for later reproduction |

### Usage

```python
# In experiment file
__DEBUG__ = True
__REPRODUCIBLE__ = True
```

```bash
# Or via CLI
pycomex run experiment.py --__DEBUG__=True --__REPRODUCIBLE__=True
```

## Parameter Override Format

### Syntax

```bash
--PARAMETER_NAME=value
```

### Type Examples

```bash
# String
--NAME="my_model"
--NAME=simple_name

# Integer
--EPOCHS=100
--BATCH_SIZE=32

# Float
--LEARNING_RATE=0.001
--MOMENTUM=0.9

# Boolean
--USE_CUDA=True
--DEBUG=False

# List (JSON)
--LAYERS="[64, 128, 256]"

# Dict (JSON)
--CONFIG='{"optimizer": "adam", "lr": 0.001}'
```

## Status Indicators

Used in `archive list` and `archive tail` output:

| Symbol | Meaning | Condition |
|--------|---------|-----------|
| ✅ | Success | `status == 'done'` |
| ❌ | Failed | `has_error == True` |
| ⏳ | Running | `status == 'running'` |
| ⚠ | Warning | Validation warnings |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Invalid arguments |
| `3` | Validation failed |

## Environment Variables

PyComex respects these environment variables:

| Variable | Description |
|----------|-------------|
| `PYCOMEX_BASE_PATH` | Default base path for results |
| `PYCOMEX_CONFIG` | Path to config file |

```bash
export PYCOMEX_BASE_PATH=/path/to/results
pycomex run experiment.py  # Uses PYCOMEX_BASE_PATH
```

## Common Patterns

### Quick Commands

```bash
# Run and view
pycomex run exp.py && pycomex archive tail

# Validate and run
pycomex template validate cfg.yml && pycomex run cfg.yml

# Backup and clean
pycomex archive compress --all && pycomex archive delete --select="..." --yes
```

### Batch Operations

```bash
# Run multiple configs
for cfg in configs/*.yml; do pycomex run "$cfg"; done

# Validate all configs
for cfg in configs/*.yml; do pycomex template validate "$cfg"; done

# Delete by pattern
pycomex archive delete --select="'debug' in m['path']" --yes
```

### Pipeline Integration

```bash
#!/bin/bash
set -e

# Validate
pycomex template validate production.yml --warnings-as-errors

# Run
pycomex run production.yml

# Archive successful run
pycomex archive compress \
  --select="m['name'] == 'production' and m['status'] == 'done'" \
  --name="production_$(date +%Y%m%d).zip"
```

## Help Commands

```bash
# General help
pycomex --help

# Command help
pycomex run --help
pycomex template --help
pycomex archive --help

# Subcommand help
pycomex template experiment --help
pycomex archive delete --help
```

## Aliases

| Full Command | Alias |
|--------------|-------|
| `pycomex` | `pycx` |

```bash
# These are equivalent
pycomex run experiment.py
pycx run experiment.py
```

## Version

```bash
# Show version
pycomex --version
```

## Further Reading

- **[Quick Start](cli_quickstart.md)** - Getting started guide
- **[Running Experiments](cli_run.md)** - Detailed `run` and `reproduce` docs
- **[Templates](cli_template.md)** - Code generation guide
- **[Archive Management](cli_archive.md)** - Archive operations guide
