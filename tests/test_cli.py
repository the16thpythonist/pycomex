import unittest

from pycomex.util import EXAMPLES_PATH
from pycomex.cli import ExperimentCLI
from click.testing import CliRunner

from .util import LOG


class TestExperimentCLI(unittest.TestCase):

    def test_construction_works(self):
        cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
        LOG.info(cli.experiment_modules.keys())
        self.assertNotEqual(0, len(cli.experiment_modules))

    def test_help_works(self):
        cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
        runner = CliRunner()

        result = runner.invoke(cli, ['--help'])
        LOG.info(result.output)
        self.assertEqual(0, result.exit_code)
        self.assertIn(cli.help[:20], result.output)

        # Then there is also the option to include a custom help text
        additional_help = 'My custom experiment'
        cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH, additional_help=additional_help)
        result = runner.invoke(cli, ['--help'])
        LOG.info(result.output)
        self.assertEqual(0, result.exit_code)
        self.assertIn(additional_help, result.output)

    def test_version_works(self):
        cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH, version='3.1.4')
        runner = CliRunner()

        result = runner.invoke(cli, ['--version'])
        LOG.info(result.output)
        self.assertIn('3.1.4', result.output)

    def test_list_experiments_basically_works(self):
        cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(cli, ['list'], terminal_width=50)
        LOG.info(result.output, result.exit_code, result.exception)
        self.assertEqual(0, result.exit_code)

    def test_experiment_info_basically_works(self):
        cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
        runner = CliRunner()

        result = runner.invoke(cli, ['info', '--help'])
        LOG.info(result.output)
        self.assertEqual(0, result.exit_code)

        result = runner.invoke(cli, ['info', 'basic'], terminal_width=100)
        LOG.info(result.output)
        self.assertEqual(0, result.exit_code)

    def test_run_experiment_basically_works(self):
        cli = ExperimentCLI(name='exp', experiments_path=EXAMPLES_PATH)
        runner = CliRunner()

        result = runner.invoke(cli, ['run', '--help'])
        LOG.info(result.output)
        self.assertEqual(0, result.exit_code)

        result = runner.invoke(cli, ['run', 'quickstart'], terminal_width=100)
        LOG.info(result.output)
        self.assertEqual(0, result.exit_code)
