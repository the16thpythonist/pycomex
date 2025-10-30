# YAML Config Bug Fix Utility

## Overview

This utility fixes experiment archives affected by a bug (fixed 2025-10-16) where YAML config files were incorrectly copied as `experiment_code.py` instead of the actual Python module.

## The Bug

**Before the fix:** When running experiments from YAML config files (`pycomex run config.yml`), the YAML file itself was copied to `experiment_code.py` in the archive, causing import errors when trying to load the experiment.

**After the fix:** A proper config stub is generated as `experiment_code.py` that:
- Is valid, importable Python code
- Documents the experiment came from a YAML config
- References the extended experiment and parameter overrides
- Can reload the experiment from the archived `experiment_config.yml`

## Usage

### Basic Usage

```bash
python -m pycomex.fix_config_bug --results-path /path/to/results
```

### Dry Run (Preview Changes)

```bash
python -m pycomex.fix_config_bug --results-path /path/to/results --dry-run
```

### With Backup

```bash
python -m pycomex.fix_config_bug --results-path /path/to/results --backup
```

This creates `experiment_code.py.backup` files before making changes.

### Verbose Output

```bash
python -m pycomex.fix_config_bug --results-path /path/to/results --verbose
```

Shows detailed information about each archive, including extended experiment path and parameter count.

## What It Does

For each affected archive, the utility:

1. **Detects** `experiment_code.py` files that contain YAML content
2. **Renames** `experiment_code.py` → `experiment_config.yml`
3. **Generates** a proper Python stub as `experiment_code.py`
4. **Validates** the fix by attempting to load the experiment

## Example Output

```
Scanning /path/to/results for affected archives...

Found affected archive:
  /path/to/results/test_experiment/20250101_120000
  Extended experiment: /path/to/base_experiment.py
  Parameters: 5 defined
  ✓ Fixed successfully
  ✓ Validation passed: Archive loads correctly

============================================================
Summary:
  Archives fixed: 3
```

## Safety Features

- **Dry-run mode**: Preview changes without modifying files
- **Backup mode**: Create backups before making changes
- **Validation**: Tests each fix by attempting `Experiment.load()`
- **Conflict detection**: Warns if `experiment_config.yml` already exists with different content

## Testing

The utility includes comprehensive tests in `tests/test_functional_utils.py`:

```bash
pytest tests/test_functional_utils.py::TestFixConfigBug -v
```

Test coverage includes:
- YAML detection in `.py` files
- Python file detection (should not trigger fixes)
- Complete fix workflow with validation
- Dry-run mode behavior
- Backup mode functionality
- Handling of already-fixed archives

## Technical Details

The utility uses the same Jinja2 template (`config_stub.py.j2`) that pycomex now uses for config-based experiments, ensuring consistency between new experiments and fixed archives.

### Generated Stub Structure

```python
"""
Experiment run from YAML configuration file.

Configuration File:
    experiment_config.yml (in this archive directory)

Extended Experiment:
    /path/to/base_experiment.py

Parameter Overrides:
    PARAM1: value1
    PARAM2: value2
"""

from pycomex.functional.experiment import Experiment
import os

ARCHIVE_DIR = os.path.dirname(os.path.abspath(__file__))

experiment = Experiment.from_config(
    config_path=os.path.join(ARCHIVE_DIR, "experiment_config.yml")
)

if __name__ == "__main__":
    experiment.run_if_main()
```

## Troubleshooting

**"experiment_config.yml already exists with different content"**
- Manual intervention required
- The archive may have been partially fixed before
- Check both files and resolve manually

**"Validation failed: No such file or directory: experiment_meta.json"**
- The archive may be incomplete or corrupted
- The fix was still applied correctly to `experiment_code.py`
- Check if other archive files exist

**No affected archives found**
- All archives are already correctly formatted
- Archives were created after the bug fix
- Or the results folder doesn't contain config-based experiments
