# Archive Management

Organize, analyze, and maintain experiment results archives.

## Common Options

Most archive commands support:

```bash
--path RESULTS_PATH  # Archive location (default: ./results)
--select "EXPRESSION"  # Filter experiments
```

## Selection Expressions

Filter experiments using Python boolean expressions with these variables:

| Variable | Alias | Description |
|----------|-------|-------------|
| `m` | `metadata` | Full metadata dictionary |
| `p` | `parameters`, `params` | Parameters dictionary |

### Examples

```bash
# By status
--select="m['status'] == 'done'"
--select="m['status'] == 'failed'"
--select="m['has_error'] == True"

# By parameter values
--select="p['LEARNING_RATE'] < 0.01"
--select="p['BATCH_SIZE'] == 32"
--select="p['EPOCHS'] > 50"

# Combined conditions
--select="m['status'] == 'done' and p['LEARNING_RATE'] > 0.01"
--select="m['duration'] > 100 and p['MODEL'] == 'resnet'"

# String matching
--select="'test' in m.get('name', '')"
--select="m['name'].startswith('debug')"

# Advanced
--select="m['duration'] > 60 and p['BATCH_SIZE'] in [32, 64]"
```

## pycomex archive list

List experiments with status and duration.

### Syntax

```bash
pycomex archive list [--select=EXPR]
```

### Example

```bash
# List all experiments
pycomex archive list

# List only successful
pycomex archive list --select="m['status'] == 'done'"

# List failed experiments
pycomex archive list --select="m['has_error'] == True"
```

### Output Format

```
✅ results/neural_net/2024-01-15_10-30-45 (2m 15s)
❌ results/neural_net/2024-01-15_11-20-10 (45s)
✅ results/neural_net/2024-01-15_12-05-30 (3m 42s)
⏳ results/neural_net/2024-01-15_13-00-00 (running)
```

Status indicators:
- ✅ - Success (`status == 'done'`)
- ❌ - Failed (`has_error == True`)
- ⏳ - Running (`status == 'running'`)

### Use Cases

```bash
# Quick status check
pycomex archive list

# Find long-running experiments
pycomex archive list --select="m['duration'] > 3600"

# Check specific parameter runs
pycomex archive list --select="p['LEARNING_RATE'] == 0.001"
```

## pycomex archive tail

Show details of the most recent experiments.

### Syntax

```bash
pycomex archive tail [-n NUM] [--select=EXPR]
```

### Options

- `-n, --num` - Number of experiments (default: 5)
- `--select` - Filter expression

### Example

```bash
# Last 5 experiments
pycomex archive tail

# Last 10 experiments
pycomex archive tail -n 10

# Last 5 successful experiments
pycomex archive tail --select="m['status'] == 'done'"
```

### Output Format

```
Experiment: neural_net
Status: done ✅
Started: 2024-01-15 10:30:45
Ended: 2024-01-15 10:32:30
Duration: 1m 45s
Description: Training neural network classifier with Adam optimizer...

────────────────────────────────────────

Experiment: neural_net
Status: failed ❌
...
```

Shows detailed information for each experiment:
- Name and status
- Start/end times
- Duration
- Description (truncated if long)

### Use Cases

```bash
# Quick check of recent work
pycomex archive tail

# Review recent failures
pycomex archive tail -n 20 --select="m['has_error'] == True"

# Check specific experiment runs
pycomex archive tail --select="p['MODEL'] == 'resnet50'"
```

## pycomex archive overview

Display comprehensive archive statistics.

### Syntax

```bash
pycomex archive overview [--select=EXPR]
```

### Example

```bash
# Full archive statistics
pycomex archive overview

# Statistics for specific subset
pycomex archive overview --select="p['MODEL'] == 'resnet'"
```

### Output Sections

#### 1. Overview
```
Total Experiments: 150
Successful: 120 (80.0%)
Failed: 25 (16.7%)
Running: 5 (3.3%)
Total Disk Space: 2.5 GB
```

#### 2. Timing Statistics
```
First Experiment: 2024-01-01 10:00:00
Last Experiment: 2024-01-15 15:30:00
Average Duration: 2m 15s
Maximum Duration: 15m 42s
Total Time: 5h 37m 30s
```

#### 3. Content Statistics
```
Parameters per Experiment:
  Min: 5
  Max: 15
  Average: 8.5

Assets per Experiment:
  Min: 2
  Max: 10
  Average: 5.3
```

#### 4. Error Analysis
```
Error Types:
  ValueError: 10 (40.0%)
  RuntimeError: 8 (32.0%)
  KeyError: 5 (20.0%)
  Other: 2 (8.0%)
```

### Use Cases

```bash
# Quick health check
pycomex archive overview

# Analyze subset performance
pycomex archive overview --select="p['OPTIMIZER'] == 'adam'"

# Check recent experiments
pycomex archive overview --select="m['start_time'] > '2024-01-10'"
```

## pycomex archive info

Display archive statistics (similar to overview).

### Syntax

```bash
pycomex archive info [--select=EXPR]
```

Functionally similar to `overview` command.

## pycomex archive delete

Delete experiments from archive.

### Syntax

```bash
pycomex archive delete [--select=EXPR | --all] [--yes] [-v]
```

### Options

- `--select` - Selection expression (required unless `--all`)
- `--all` - Select all experiments
- `--yes` - Skip confirmation prompt
- `-v, --verbose` - Show detailed deletion info

### Example

```bash
# Delete failed experiments (with confirmation)
pycomex archive delete --select="m['status'] == 'failed'"

# Delete without confirmation
pycomex archive delete --select="m['status'] == 'failed'" --yes

# Delete with verbose output
pycomex archive delete --select="m['duration'] < 10" --yes -v

# Delete all (dangerous!)
pycomex archive delete --all --yes
```

### Safety Features

- **Requires selection** - Must use `--select` or `--all`
- **Confirmation prompt** - Unless `--yes` is used
- **Preview count** - Shows number of experiments before deletion

### Confirmation Example

```
Selected 15 experiments for deletion.

Experiments to delete:
  results/model/2024-01-10_10-00-00
  results/model/2024-01-10_11-00-00
  ...

Delete these experiments? [y/N]:
```

### Use Cases

```bash
# Clean up failed runs
pycomex archive delete --select="m['has_error'] == True" --yes

# Remove old debug runs
pycomex archive delete --select="'debug' in m['path']" --yes

# Delete short-lived experiments (likely failed)
pycomex archive delete --select="m['duration'] < 5" --yes -v

# Clear specific parameter runs
pycomex archive delete --select="p['LEARNING_RATE'] > 0.5"
```

### Before Deleting

```bash
# Preview what will be deleted
pycomex archive list --select="m['status'] == 'failed'"

# Count experiments
pycomex archive overview --select="m['status'] == 'failed'"

# Then delete
pycomex archive delete --select="m['status'] == 'failed'" --yes
```

## pycomex archive compress

Compress experiments into a ZIP archive.

### Syntax

```bash
pycomex archive compress [--select=EXPR | --all] [--name=FILE] [-v]
```

### Options

- `--select` - Selection expression (required unless `--all`)
- `--all` - Select all experiments
- `--name` - ZIP filename (default: `results.zip`)
- `-v, --verbose` - Show detailed compression info

### Example

```bash
# Compress all experiments
pycomex archive compress --all

# Compress specific subset
pycomex archive compress \
  --select="m['status'] == 'done'" \
  --name=successful_runs.zip

# Compress with verbose output
pycomex archive compress \
  --select="p['MODEL'] == 'resnet'" \
  --name=resnet_experiments.zip \
  -v
```

### Output

```
Compressing 25 experiments...
Created: resnet_experiments.zip (145.2 MB)
```

### ZIP Structure

Maintains directory hierarchy:

```
resnet_experiments.zip
├── results/
│   └── neural_net/
│       ├── 2024-01-15_10-30-45/
│       │   ├── experiment_meta.json
│       │   ├── experiment_data.json
│       │   ├── experiment_out.log
│       │   └── model.pt
│       └── 2024-01-15_11-20-10/
│           └── ...
```

### Use Cases

```bash
# Backup all results
pycomex archive compress --all --name=backup_$(date +%Y%m%d).zip

# Share successful experiments
pycomex archive compress \
  --select="m['status'] == 'done'" \
  --name=share_results.zip

# Archive before cleanup
pycomex archive compress \
  --select="m['status'] == 'failed'" \
  --name=failed_experiments.zip

pycomex archive delete --select="m['status'] == 'failed'" --yes

# Extract specific experiments
pycomex archive compress \
  --select="p['LEARNING_RATE'] == 0.001 and m['status'] == 'done'" \
  --name=lr_001_results.zip
```

### Reproduction from ZIP

Compressed archives can be used with `reproduce`:

```bash
# Compress experiment
pycomex archive compress \
  --select="m['name'] == 'best_model'" \
  --name=best_model.zip

# Share with colleague

# They can reproduce directly
pycomex reproduce best_model.zip
```

## pycomex archive modify

Bulk modify parameters or metadata of archived experiments.

### Syntax

```bash
pycomex archive modify [--select=EXPR | --all]
                      [--modify-parameters=CODE]
                      [--modify-metadata=CODE]
                      [--dry-run] [-v]
```

### Options

- `--select` - Selection expression (required unless `--all`)
- `--all` - Select all experiments
- `--modify-parameters` - Python code to modify parameters dict `p`
- `--modify-metadata` - Python code to modify metadata dict `m`
- `--dry-run` - Preview changes without saving
- `-v, --verbose` - Show detailed progress

### Requirements

- Must provide at least one modification type
- Must provide either `--select` or `--all`
- Code is syntax-validated before execution

### Examples

#### Modify Parameters

```bash
# Fix parameter typo
pycomex archive modify \
  --select="'LERNING_RATE' in p" \
  --modify-parameters="p['LEARNING_RATE'] = p.pop('LERNING_RATE')"

# Scale learning rates
pycomex archive modify --all \
  --modify-parameters="p['LEARNING_RATE'] *= 10"

# Update model names
pycomex archive modify \
  --select="p['MODEL'] == 'old_model'" \
  --modify-parameters="p['MODEL'] = 'new_model'"

# Multiple changes
pycomex archive modify --all \
  --modify-parameters="p['BATCH_SIZE'] *= 2; p['EPOCHS'] += 10"
```

#### Modify Metadata

```bash
# Add processing tag
pycomex archive modify --all \
  --modify-metadata="m['processed'] = True"

# Fix status
pycomex archive modify \
  --select="m.get('has_error') and m['duration'] > 0" \
  --modify-metadata="m['status'] = 'failed'"

# Add version info
pycomex archive modify --all \
  --modify-metadata="m['version'] = '2.0'"

# Update timestamps
pycomex archive modify \
  --select="m['name'] == 'test'" \
  --modify-metadata="m['archived'] = True; m['archive_date'] = '2024-01-15'"
```

#### Combined Modifications

```bash
# Update both parameters and metadata
pycomex archive modify \
  --select="m['status'] == 'done'" \
  --modify-parameters="p['LEARNING_RATE'] = round(p['LEARNING_RATE'], 4)" \
  --modify-metadata="m['reviewed'] = True"
```

### Dry Run

Preview changes before applying:

```bash
# See what would change
pycomex archive modify --all \
  --modify-parameters="p['LEARNING_RATE'] *= 10" \
  --dry-run
```

Output:
```
DRY RUN - No changes will be saved

Experiment: results/model/2024-01-15_10-30-45
  LEARNING_RATE: 0.001 → 0.01

Experiment: results/model/2024-01-15_11-20-10
  LEARNING_RATE: 0.01 → 0.1

Would modify 2 experiments.
```

### Available Variables

In your code:
- `p` - Parameters dictionary (mutable)
- `m` - Metadata dictionary (mutable)

Standard Python operations:
- Arithmetic: `p['VALUE'] *= 2`
- Dictionary ops: `p.pop()`, `p.update()`, `p.setdefault()`
- Conditionals: `p['X'] = 10 if p['Y'] > 5 else 20`
- Multiple statements: `p['A'] += 1; p['B'] *= 2`

### Use Cases

```bash
# Fix parameter naming
pycomex archive modify --all \
  --modify-parameters="p['learning_rate'] = p.pop('LEARNING_RATE')" \
  --dry-run

# Normalize parameter values
pycomex archive modify --all \
  --modify-parameters="p['LEARNING_RATE'] = round(p['LEARNING_RATE'], 6)"

# Add missing metadata
pycomex archive modify \
  --select="'version' not in m" \
  --modify-metadata="m['version'] = '1.0'"

# Batch update after experiment
pycomex archive modify \
  --select="m['status'] == 'done' and p['MODEL'] == 'resnet'" \
  --modify-metadata="m['analyzed'] = True; m['best_accuracy'] = 0.95"

# Convert parameter types
pycomex archive modify --all \
  --modify-parameters="p['EPOCHS'] = int(p['EPOCHS'])" \
  --verbose
```

### Safety Tips

1. **Always use `--dry-run` first**
```bash
# Preview
pycomex archive modify --all --modify-parameters="..." --dry-run

# If looks good, apply
pycomex archive modify --all --modify-parameters="..."
```

2. **Backup before bulk modifications**
```bash
# Backup
pycomex archive compress --all --name=backup.zip

# Modify
pycomex archive modify --all --modify-metadata="..."
```

3. **Test on small subset first**
```bash
# Test on one experiment
pycomex archive modify \
  --select="m['name'] == 'test'" \
  --modify-parameters="..."

# If successful, apply to all
pycomex archive modify --all --modify-parameters="..."
```

## Common Workflows

### Regular Cleanup

```bash
#!/bin/bash
# cleanup.sh - Regular archive maintenance

# Show current state
echo "=== Current Archive State ==="
pycomex archive overview

# Backup everything first
echo -e "\n=== Creating Backup ==="
pycomex archive compress --all --name="backup_$(date +%Y%m%d).zip"

# Delete failed experiments
echo -e "\n=== Removing Failed Experiments ==="
pycomex archive delete --select="m['status'] == 'failed'" --yes

# Show updated state
echo -e "\n=== Updated Archive State ==="
pycomex archive overview
```

### Selective Export

```bash
# Export successful experiments with specific parameters
pycomex archive compress \
  --select="m['status'] == 'done' and p['LEARNING_RATE'] < 0.01" \
  --name="good_lr_experiments.zip"

# Export recent experiments
pycomex archive compress \
  --select="m['start_time'] > '2024-01-10'" \
  --name="recent_experiments.zip"
```

### Bulk Analysis Preparation

```bash
# Tag experiments for analysis
pycomex archive modify \
  --select="m['status'] == 'done' and p['ACCURACY'] > 0.9" \
  --modify-metadata="m['for_analysis'] = True; m['high_accuracy'] = True"

# List tagged experiments
pycomex archive list --select="m.get('for_analysis', False)"

# Create analysis notebook
pycomex template analysis

# Export for sharing
pycomex archive compress \
  --select="m.get('for_analysis', False)" \
  --name="analysis_set.zip"
```

### Archive Migration

```bash
# Update parameter names in old experiments
pycomex archive modify --all \
  --modify-parameters="
if 'old_param' in p:
    p['new_param'] = p.pop('old_param')
" \
  --dry-run

# Add version metadata
pycomex archive modify --all \
  --modify-metadata="m['schema_version'] = '2.0'"

# Compress migrated archive
pycomex archive compress --all --name="migrated_archive.zip"
```

### Performance Analysis

```bash
# Find slow experiments
pycomex archive list --select="m['duration'] > 600"

# Analyze by parameter
pycomex archive overview --select="p['BATCH_SIZE'] == 32"
pycomex archive overview --select="p['BATCH_SIZE'] == 64"

# Export for comparison
pycomex archive compress \
  --select="m['duration'] > 600" \
  --name="slow_experiments.zip"
```
