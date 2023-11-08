"""Console script for pycomex."""
import sys
import os
import textwrap
import importlib.util
from typing import Optional, Dict
import typing as t

import rich
import rich_click as click
from click.globals import get_current_context
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement

from pycomex.util import get_version
from pycomex.util import TEMPLATE_ENV
from pycomex.util import dynamic_import
from pycomex.functional.experiment import Experiment
from pycomex.functional.experiment import run_experiment


click.rich_click.USE_RICH_MARKUP = True


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
})


class RichExperimentParameterInfo:
    
    def __init__(self,
                 experiment: Experiment
                 ):
        self.experiment = experiment
        
    def __rich_console__(self, 
                         console: Console, 
                         options: ConsoleOptions
                         ) -> RenderResult:
        width = options.size.width
        
        num_parameters = len(self.experiment.metadata['parameters'])
        for index, (parameter, data) in enumerate(self.experiment.metadata['parameters'].items()):
            title = f'[cyan]{parameter}[/cyan]'
            if 'type' in data:
                title = title + f' - {data["type"]}'

            yield title
            
            if 'description' in data and len(data['description']) > 3:
                yield data['description']
            
            if index + 1 < num_parameters:
                yield ''
            
            
class RichExperimentHookInfo:
    
    def __init__(self,
                 experiment: Experiment
                 ):
        self.experiment = experiment
        
    def __rich_console__(self, 
                         console: Console, 
                         options: ConsoleOptions
                         ) -> RenderResult:
        width = options.size.width
        
        num_parameters = len(self.experiment.metadata['hooks'])
        for index, (hook, data) in enumerate(self.experiment.metadata['hooks'].items()):
            title = f'[magenta]{hook}[/magenta]'
            if 'type' in data:
                title = title + f' - {data["type"]}'

            yield title
            
            if 'description' in data and len(data['description']) > 3:
                yield data['description']
            
            if index + 1 < num_parameters:
                yield ''


class RichExperimentInfo:
    
    def __init__(self,
                 path: str,
                 experiment: Experiment
                 ):
        self.path = path
        self.experiment = experiment
        
        self.name = os.path.basename(self.path).split('.')[0]
        
    # ~ Implementing renderable
    # The following are magic methods which allow this object to produce the actual rich console 
    # output.
        
    def __rich_console__(self,
                         console: Console, 
                         options: ConsoleOptions,
                         ) -> RenderResult:
        width = options.size.width
        
        # ~ The header
        yield rich.panel.Panel(
            rich.align.Align(self.name, align='center'),
            box=rich.box.HEAVY,
            style="markdown.h1.border",
        )
        yield rich.panel.Panel(
            rich.markdown.Markdown(self.experiment.metadata['description']),
            title='description',
            title_align='left',
            border_style='bright_black',
        )
        yield rich.panel.Panel(
            RichExperimentParameterInfo(self.experiment),
            title='parmeters',
            title_align='left',
            border_style='bright_black', 
        )
        yield rich.panel.Panel(
            RichExperimentHookInfo(self.experiment),
            title='hooks',
            title_align='left',
            border_style='bright_black',
        )
        
    def __rich_measure__(self,
                         console: Console,
                         options: ConsoleOptions
                         ) -> Measurement:
        return Measurement(
            len(self.name) + 20, 
            options.max_width
        )
        
        
class RichExperimentList:
    
    def __init__(self,
                 experiments: t.List[Experiment]
                 ):
        self.experiments = experiments
    
    def __rich_console__(self, 
                         console: Console, 
                         options: ConsoleOptions
                         ) -> RenderResult:
        width = options.size.width
        
        num_experiments = len(self.experiments)
        for index, experiment in enumerate(self.experiments):
            name = experiment.metadata['name']
            title = f'[yellow]{name}[/yellow]'
            yield title
            
            description = experiment.metadata['short_description']
            yield description
            
            # parameters = experiment.metadata['parameters']
            # yield f'[bright_black]n.o. params: {len(parameters)}[/bright_black]'
            
            if index + 1 < num_experiments:
                yield ''


class ExperimentCLI(click.RichGroup):
    """
    This class implements a generic experiment click command line interface. It is "generic" in that 
    sense that it can be used to implement a distinct experiment CLI for each folder that contains experiment 
    modules. Given that experiment folder path, an instance of this class will expose a CLI that can 
    list experiments, show detailed experiment information and execute experiments.
    
    :param name: The string name of the experiment cli
    :param experiments_path: Absolute string path to the folder which contains the experiment modules
    :param experiments_base_path: Absolute string path to the folder that acts as the archive for those 
        experiments. This is usually called the "results" folder.
    :param version: A version string can optionally be supplied which will be printed for the 
        --version option of the CLI
    :param additional_help: This is a string which can be used to add additional information to the help 
        text of the CLI.
    """
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
        # This method will iterate through all the files in the given experiment folder, check which one of the 
        # files is (a) a python file and (b) actually implements an experiment. All those will then be used 
        # to populate the self.experiments dictionary so that this can then be used as the basis for all
        # the commands in the group.
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

    # -- commands
    # The following methods are actually the command implementations which are the specific commands 
    # that are part of the command group that is represented by the ExperimentCLI object instance itself.

    @click.command('list', short_help='Prints a list of all experiments in this package')
    @click.pass_obj
    def list_experiments(self):
        """
        Prints an overview of all the experiment modules which were discovered in this package.
        """
        experiment_list = RichExperimentList(
            experiments=list(self.experiments.values())
        )
        group = rich.console.Group(
            rich.panel.Panel(
                experiment_list,
                title='experiments',
                title_align='left',
                border_style='bright_black',
            )
        )
        rich.print(group)

    @click.command('info', short_help='Prints information about one experiment')
    @click.argument('experiment')
    @click.pass_obj
    def experiment_info(self, experiment: str, length: int = 100):
        """
        Prints detailed information about the experiment with the string identifier EXPERIMENT.
        """
        experiment_info = RichExperimentInfo(
            path=self.experiment_modules[experiment],
            experiment=self.experiments[experiment],
        )
        rich.print(experiment_info)

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

    # ~ click.Group implementation

    # This is the method that is actually executed when the CLI object instance itself is invoked!
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

    # ~ utility
    # The following methods implement some kind of utiltiy functions for this class

    def discover_experiments(self):
        """
        This method will iterate through all the files (only top level!) of the given self.experiment_path and 
        check each file if it is (1) a valid python module and (2) a valid experiment module. All the experiment 
        modules that are found are saved to the self.experiments dictionary.

        :returns None:
        """
        assert os.path.exists(self.experiments_path) and os.path.isdir(self.experiments_path), (
            f'The provided path "{self.experiments_path}" is not a valid folder path. Please provide the '
            f'path to the FOLDER, which contains all the experiment modules'
        )

        for root, folders, files in os.walk(self.experiments_path):
            for file_name in sorted(files):
                file_path = os.path.join(root, file_name)
                if file_path.endswith('.py'):
                    name, _ = file_name.split('.')

                    # Now just because it is a python file doesn't mean it is an experiment. To make sure we
                    # are going to import each of the python modules.
                    # 27.10.23 - Added the try-except block around this importing operation because previously, the 
                    # the construction of the entire CLI object would fail if there was any kind of python module in 
                    # the given experiment folder that contained a syntax error for example. With this we will now 
                    # simply ignore any modules that contain errors!
                    try:
                        module = dynamic_import(file_path)
                        if hasattr(module, '__experiment__'):
                            self.experiment_modules[name] = file_path
                            self.experiments[name] = getattr(module, '__experiment__')
                    except Exception as e: 
                        print(e)
            
            # We only want to explore the top level directory!
            break

        assert len(self.experiment_modules) != 0, (
            'No experiment modules were detected in the folder of '
        )


@click.group(invoke_without_command=True)
@click.option("-v", "--version", is_flag=True)
@click.pass_context
def cli(ctx: click.Context,
        version: bool
        ) -> None:
    """Console script for pycomex."""
    if version:
        version = get_version()
        click.secho(version)
        sys.exit(0)


if __name__ == "__main__":
    cli()  # pragma: no cover
