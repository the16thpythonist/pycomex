"""
Utility to fix experiment archives affected by the YAML config bug.

BUG DESCRIPTION:
================
Before the fix (2025-10-16), when running experiments from YAML config files,
the YAML file itself was copied to experiment_code.py instead of the actual
Python module or a proper stub. This caused import errors when trying to load
the experiment with Experiment.load().

This utility detects and fixes affected archives by:
1. Detecting experiment_code.py files that contain YAML content
2. Renaming them to experiment_config.yml
3. Generating a proper config stub as experiment_code.py
4. Validating the fix by attempting to load the experiment

USAGE:
======
    python -m pycomex.fix_config_bug --results-path /path/to/results

    # Dry run to see what would be fixed:
    python -m pycomex.fix_config_bug --results-path /path/to/results --dry-run

    # With verbose output:
    python -m pycomex.fix_config_bug --results-path /path/to/results --verbose
"""

import os
import shutil
import yaml
import click
from pathlib import Path
from typing import Tuple, Optional

from pycomex.functional.experiment import Experiment, TEMPLATE_ENV
from pycomex.utils import dynamic_import


@click.command()
@click.option(
    '--results-path',
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help='Path to the results folder containing experiment archives'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Show what would be fixed without making changes'
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Show detailed information about each archive'
)
@click.option(
    '--backup',
    is_flag=True,
    help='Create backups of experiment_code.py before fixing'
)
def fix_config_bug(results_path: str, dry_run: bool, verbose: bool, backup: bool):
    """
    Fix experiment archives affected by the YAML config bug.

    Scans the specified results folder recursively for experiment archives where
    experiment_code.py contains YAML content instead of Python code, and fixes
    them by generating proper config stubs.
    """
    results_path = Path(results_path).resolve()
    fixed_count = 0
    error_count = 0
    skipped_count = 0

    click.echo(f"Scanning {results_path} for affected archives...")
    if dry_run:
        click.echo(click.style("[DRY RUN MODE - No changes will be made]", fg='yellow', bold=True))
    click.echo()

    # Walk through all directories
    for root, dirs, files in os.walk(results_path):
        if 'experiment_code.py' in files:
            archive_path = Path(root)
            code_file = archive_path / 'experiment_code.py'

            # Check if this file is actually YAML
            is_yaml, config_data = is_yaml_file(code_file)

            if is_yaml:
                click.echo(click.style(f"{'[DRY RUN] ' if dry_run else ''}Found affected archive:", fg='cyan'))
                click.echo(f"  {archive_path}")

                if verbose:
                    click.echo(f"  Extended experiment: {config_data.get('extend', 'unknown')}")
                    params = config_data.get('parameters', {})
                    if params:
                        click.echo(f"  Parameters: {len(params)} defined")

                try:
                    if not dry_run:
                        # Create backup if requested
                        if backup:
                            backup_path = code_file.with_suffix('.py.backup')
                            shutil.copy2(code_file, backup_path)
                            if verbose:
                                click.echo(f"  Created backup: {backup_path.name}")

                        # Fix the archive
                        fix_archive(archive_path, code_file, config_data)
                        fixed_count += 1
                        click.echo(click.style(f"  ✓ Fixed successfully", fg='green'))

                        # Validate the fix
                        try:
                            exp = Experiment.load(str(archive_path))
                            click.echo(click.style(f"  ✓ Validation passed: Archive loads correctly", fg='green'))

                            if verbose:
                                click.echo(f"    Namespace: {exp.namespace}")
                                click.echo(f"    Parameters: {len(exp.parameters)}")
                        except Exception as e:
                            click.echo(click.style(f"  ⚠ Warning: Fixed but validation failed: {e}", fg='yellow'))
                    else:
                        fixed_count += 1
                        click.echo(click.style(f"  Would fix this archive", fg='yellow'))

                except Exception as e:
                    error_count += 1
                    click.echo(click.style(f"  ✗ Error fixing archive: {e}", fg='red'))
                    if verbose:
                        import traceback
                        click.echo(f"  {traceback.format_exc()}")

                click.echo()  # Blank line between archives

            elif verbose:
                # Archive is fine, optionally show it
                pass

    # Summary
    click.echo(click.style("=" * 60, fg='cyan'))
    click.echo(click.style(f"{'[DRY RUN] ' if dry_run else ''}Summary:", fg='cyan', bold=True))
    click.echo(f"  Archives {'that would be fixed' if dry_run else 'fixed'}: {click.style(str(fixed_count), fg='green', bold=True)}")

    if error_count > 0:
        click.echo(f"  Errors encountered: {click.style(str(error_count), fg='red', bold=True)}")

    if fixed_count == 0 and error_count == 0:
        click.echo(click.style("  No affected archives found!", fg='green'))


def is_yaml_file(file_path: Path) -> Tuple[bool, Optional[dict]]:
    """
    Check if a .py file actually contains YAML content.

    :param file_path: Path to the file to check

    :returns: Tuple of (is_yaml, config_data) where is_yaml is True if the file
              contains YAML config content, and config_data is the parsed config
              or None if not YAML
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Quick check: if it looks like Python code, skip YAML parsing
        # (optimization to avoid parsing every Python file)
        if content.strip().startswith(('import ', 'from ', 'def ', 'class ', '#!')):
            return False, None

        # Try to parse as YAML
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError:
            return False, None

        # Check if it has the structure of a config file
        # Config files should be dictionaries with 'extend' or 'parameters' keys
        if isinstance(parsed, dict) and ('extend' in parsed or 'parameters' in parsed):
            return True, parsed

        return False, None

    except Exception:
        # If we can't read the file, assume it's not YAML
        return False, None


def fix_archive(archive_path: Path, code_file: Path, config_data: dict):
    """
    Fix a single affected archive.

    Steps:
    1. Check if experiment_config.yml already exists
    2. Rename experiment_code.py to experiment_config.yml (or verify existing one)
    3. Generate proper stub as experiment_code.py

    :param archive_path: Path to the experiment archive directory
    :param code_file: Path to the experiment_code.py file (contains YAML)
    :param config_data: Parsed YAML configuration data

    :raises ValueError: If experiment_config.yml exists with different content
    :raises Exception: For other errors during fixing
    """
    config_file = archive_path / 'experiment_config.yml'

    # Read the current YAML content from experiment_code.py
    with open(code_file, 'r') as f:
        yaml_content = f.read()

    # Check if experiment_config.yml already exists
    if config_file.exists():
        # Compare content - if identical, just need to regenerate stub
        with open(config_file, 'r') as f:
            existing_config = f.read()

        if existing_config.strip() != yaml_content.strip():
            raise ValueError(
                f"experiment_config.yml already exists with different content. "
                f"Manual intervention required for {archive_path}"
            )

        # Config file is already correct, just need to regenerate stub
        # Remove the bad experiment_code.py
        code_file.unlink()
    else:
        # Rename experiment_code.py to experiment_config.yml
        code_file.rename(config_file)

    # Generate the stub
    template = TEMPLATE_ENV.get_template("config_stub.py.j2")

    # Get extended path from config
    extended_path = config_data.get('extend', 'unknown')

    # Get parameters (excluding special __ parameters for display)
    config_parameters = {
        key: value
        for key, value in config_data.get('parameters', {}).items()
        if not key.startswith('__')
    }

    # Render stub
    stub_content = template.render({
        'extended_path': extended_path,
        'config_parameters': config_parameters,
    })

    # Write the stub as experiment_code.py
    with open(code_file, 'w') as f:
        f.write(stub_content)


if __name__ == '__main__':
    fix_config_bug()
