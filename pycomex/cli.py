"""Console script for pycomex."""
import sys
import os
import textwrap
import importlib.util
from typing import Optional, Dict

import click
from click.globals import get_current_context
from pycomex.util import get_version
from pycomex.util import TEMPLATE_ENV
from pycomex.experiment import Experiment
from pycomex.experiment import run_experiment
from pycomex.experiment import NamespaceFolder


def section(string: str, length: int, padding: int = 2):
    half = int((length - len(string)) / 2) - padding
    rest = (length - len(string)) % 2
    return '\n'.join([
        '=' * length,
        '=' * half + ' ' * padding + string.upper() + ' ' * padding + '=' * (half + rest),
        '=' * length
    ])


def subsection(string: str, length: int, padding: int = 2):
    half = int((length - len(string)) / 2) - padding
    rest = (length - len(string)) % 2
    return '\n'.join([
        '-' * half + ' ' * padding + string.upper() + ' ' * padding + '-' * (half + rest),
    ])


TEMPLATE_ENV.globals.update({
    'section': section,
    'subsection': subsection,
    'NamespaceFolder': NamespaceFolder
})


class ExperimentCLI(click.Group):

    def __init__(self,
                 name: str,
                 experiments_path: str,
                 experiments_base_path: Optional[str] = None,
                 version: str = '0.0.0',
                 additional_help: str = '',
                 **kwargs):
        super(ExperimentCLI, self).__init__(
            name=name,
            callback=self.callback,
            invoke_without_command=True,
            **kwargs
        )
        self.experiments_path = experiments_path
        self.base_path = experiments_base_path
        self.version = version

        version_option = click.Option(['--version'], is_flag=True)
        self.params.append(version_option)

        # ~ Loading all the experiments
        self.experiment_modules: Dict[str, str] = {}
        self.experiments: Dict[str, Experiment] = {}
        self.discover_experiments()

        # ~ Constructing the help string.
        # This is the string which will be printed when the help option is called.
        self.help = (
            f'Experiment CLI. Use this command line interface to list, show and execute the various '
            f'computational experiments which are contained in this package.\n'
            f'Experiment Modules: {experiments_path}'
        )
        if additional_help != '':
            self.help += '\n\n'
            self.help += additional_help

        self.context = None
        # ~ Adding default commands
        self.add_command(self.list_experiments)

        self.add_command(self.experiment_info)
        self.experiment_info.params[0].type = click.Choice(self.experiments.keys())

        self.add_command(self.run_experiment)
        self.run_experiment.params[0].type = click.Choice(self.experiments.keys())

    @click.command('list', short_help='Prints a list of all experiments in this package')
    @click.pass_obj
    def list_experiments(self):
        """
        Prints an overview of all the experiment modules which were discovered in this package
        """
        template = TEMPLATE_ENV.get_template('list_experiments.out.j2')
        string = template.render(experiments=self.experiments)
        if self.context.terminal_width is not None:
            string_lines = textwrap.wrap(
                string,
                width=self.context.terminal_width,
                replace_whitespace=False
            )
            string = '\n'.join(string_lines)

        click.secho(string)

    @click.command('info', short_help='Prints information about one experiment')
    @click.argument('experiment')
    @click.pass_obj
    def experiment_info(self, experiment: str, length: int = 100):
        """
        Prints detailed information about the experiment with the string identifier EXPERIMENT.
        """
        if self.context.terminal_width is not None:
            length = self.context.terminal_width

        template = TEMPLATE_ENV.get_template('experiment_info.out.j2')
        string = template.render(
            name=experiment,
            experiment=self.experiments[experiment],
            length=length - 1
        )

        if self.context.terminal_width is not None:
            string_lines = textwrap.wrap(
                string,
                width=self.context.terminal_width,
                replace_whitespace=False,
                drop_whitespace=False
            )
            string = ''.join(string_lines)

        click.secho(string)

    @click.command('run', short_help='Run an experiment')
    @click.argument('experiment')
    @click.pass_obj
    def run_experiment(self, experiment: str, length: int = 100):
        """
        Starts a new run of the experiment with the string identifier EXPERIMENT.
        """
        if self.context.terminal_width is not None:
            length = self.context.terminal_width

        click.secho(section(experiment, length))
        click.secho()

        experiment = run_experiment(
            self.experiment_modules[experiment],
        )

        click.secho(f'archive: {experiment.path}')

    def callback(self, version):

        # This is actually really important. If this is left out, all the commands which are implemented
        # as methods of this class will not work at all! Because the "self" argument which they all receive
        # is actually this context object! Thus it is also imperative that all the methods use the
        # "click.pass_obj" decorator.
        self.context = get_current_context()
        self.context.obj = self

        if version:
            print(self.version)
            sys.exit(0)

    def discover_experiments(self):
        assert os.path.exists(self.experiments_path) and os.path.isdir(self.experiments_path), (
            f'The provided path "{self.experiments_path}" is not a valid folder path. Please provide the '
            f'path to the FOLDER, which contains all the experiment modules'
        )

        for root, folders, files in os.walk(self.experiments_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if file_path.endswith('.py'):
                    name, _ = file_name.split('.')

                    # Now just because it is a python file doesn't mean it is an experiment. To make sure we
                    # are going to import each of the python modules.
                    spec = importlib.util.spec_from_file_location(name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, '__experiment__'):
                        self.experiment_modules[name] = file_path
                        self.experiments[name] = getattr(module, '__experiment__')

        assert len(self.experiment_modules) != 0, (
            'No experiment modules were detected in the folder of '
        )


@click.group(invoke_without_command=True)
@click.option("-v", "--version", is_flag=True)
@click.pass_context
def cli(ctx: click.Context, version: bool):
    """Console script for pycomex."""
    if version:
        version = get_version()
        click.secho(version)
        sys.exit(0)


if __name__ == "__main__":
    cli()  # pragma: no cover
