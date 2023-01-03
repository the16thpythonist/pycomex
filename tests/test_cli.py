"""
This module tests the command line interface (CLI) of pycomex, which is mainly contained within the
class ``pycomex.cli.ExperimentCLI``
"""
import unittest

from pycomex.util import EXAMPLES_PATH
from pycomex.cli import ExperimentCLI
from pycomex.testing import ArgumentIsolation
from click.testing import CliRunner

from .util import LOG


def test_construction_works():
    """
    If a new instance of ExperimentCLI can be constructed without issues
    """
    cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
    LOG.info(cli.experiment_modules.keys())

    assert 0 != cli.experiment_modules


def test_help_works():
    cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
    runner = CliRunner()

    result = runner.invoke(cli, ['--help'])
    LOG.info(result.output)
    assert result.exit_code == 0
    # cli.help is a string field of the cli instance which contains the string that should be displayed
    # when the --help option is given
    assert cli.help[:20] in result.output

    # Then there is also the option to include a custom help text when constructing the Cli instance.
    additional_help = 'My custom experiment'
    cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH, additional_help=additional_help)
    result = runner.invoke(cli, ['--help'])
    LOG.info(result.output)
    assert result.exit_code == 0
    assert additional_help in result.output


def test_version_works():
    version = '3.1.4'
    cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH, version='3.1.4')
    runner = CliRunner()

    result = runner.invoke(cli, ['--version'])
    LOG.info(result.output)
    assert version in result.output


def test_list_experiments_basically_works():
    cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(cli, ['list'], terminal_width=50)
    LOG.info(result.output, result.exit_code, result.exception)
    assert result.exit_code == 0


def test_experiment_info_basically_works():
    cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
    runner = CliRunner()

    result = runner.invoke(cli, ['info', '--help'])
    LOG.info(result.output)
    assert result.exit_code == 0

    result = runner.invoke(cli, ['info', 'basic'], terminal_width=100)
    LOG.info(result.output)
    assert result.exit_code == 0


def test_run_experiment_basically_works():
    cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
    runner = CliRunner()

    result = runner.invoke(cli, ['run', '--help'])
    LOG.info(result.output)
    assert result.exit_code == 0

    with ArgumentIsolation():
        result = runner.invoke(cli, ['run', 'quickstart'], terminal_width=100)
        LOG.info(result.output)
        assert result.exit_code == 0
