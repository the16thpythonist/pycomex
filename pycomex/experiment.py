"""
This is a module level docstring

Header
======

is this ok?

"""
import os
import sys
import time
import json
import shutil
import logging
import pathlib
import argparse
import tempfile
import traceback
import subprocess
from datetime import datetime
from typing import List, Type, Optional, Tuple, Dict

import jinja2 as j2

from pycomex.util import TEMPLATE_ENV, EXAMPLES_PATH
from pycomex.util import RecordCode
from pycomex.work import AbstractWorkTracker
from pycomex.work import NaiveWorkTracker


def run_example(example_name: str,
                parameters_path: Optional[str] = None
                ) -> Tuple[str, subprocess.CompletedProcess]:
    example_path = os.path.join(EXAMPLES_PATH, example_name)
    return run_experiment(
        experiment_path=example_path,
        parameters_path=parameters_path,
    )


def run_experiment(experiment_path: str,
                   parameters_path: Optional[str] = None
                   ) -> Tuple[str, subprocess.CompletedProcess]:
    with tempfile.NamedTemporaryFile(mode='w+') as out_path:

        command = f'{sys.executable} {experiment_path} -o {out_path.name}'
        if parameters_path is not None:
            command += f' -p {parameters_path}'

        completed_process = subprocess.run(command, shell=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)

        with open(out_path.name) as file:
            archived_path = file.read()

    return archived_path, completed_process


class NoExperimentExecution(Exception):
    def __call__(self):
        raise self


class PrintDescriptionAction(argparse.Action):

    def __init__(self, *args, description, **kwargs):
        self.description = description
        super(PrintDescriptionAction, self).__init__(*args, **kwargs, nargs=0)

    def __call__(self, parser, namespace, values, option_string=None):
        print(self.description)
        sys.exit(0)


class ExperimentArgParser(argparse.ArgumentParser):

    def __init__(self, name: str, path: str, description: str):
        self.experiment_namespace = name
        self.experiment_path = path
        self.experiment_description = description

        # fmt: off
        _description = (f'This python module contains the code for a computational experiment. By executing '
                        f'this module directly a new run of this experiment will be initiated. Please be '
                        f'patient, the execution of the experiment will likely take a long time.\n \n'
                        f'The results of the next run will be saved into this folder: \n'
                        f'{self.experiment_path}\n')
        super(ExperimentArgParser, self).__init__(
            prog=self.experiment_namespace,
            description=_description
        )

        self.add_argument('--description', dest='description', action=PrintDescriptionAction, required=False,
                          description=self.experiment_description, help='Print the experiment description',)
        self.add_argument('-o', '--out', dest='output_path', action='store', required=False, type=str,
                          help='Optional file path, into which the experiment destination folder path '
                               'should be written into')
        self.add_argument('-p', '--parameters', dest='parameters_path', action='store', required=False,
                          type=self.valid_params,
                          help='Optional file path pointing to an existing file which contains parameters '
                               'specifications that overwrite the experiment default parameters for the '
                               'execution of the experiment. Has to be either .json or .py file')

    @staticmethod
    def valid_params(value: str) -> str:
        if not os.path.exists(value):
            raise ValueError(f'The given parameter file path "{value}" does not exist!')

        param_suffixes = ['.json', '.py']
        if not any(value.endswith(suffix) for suffix in param_suffixes):
            raise ValueError(f'The given parameter file path "{value}" is none of the accepted file types: '
                             f', '.join(param_suffixes))

        return value


class Experiment:
    """

    **This has to be a heading**

    This is an example:

    .. code-block:: python

        import click
        print('hello world')

    :ivar str base_path: The absolute path to the base folder.

    :param str base_path: The thingy
            which is really important

    """
    DEFAULT_TEMPLATES = {
        'analysis.py': TEMPLATE_ENV.get_template('analysis.py.j2'),
        'annotations.rst': TEMPLATE_ENV.get_template('annotations.py.j2')
    }

    def __init__(
        self,
        base_path: str,
        namespace: str,
        glob: dict,
        debug_mode: bool = False,
        templates: Dict[str, j2.Template] = DEFAULT_TEMPLATES.copy(),
        work_tracker_class: Type[AbstractWorkTracker] = NaiveWorkTracker,
    ):
        self.base_path = base_path
        self.namespace = namespace
        self.glob = glob
        self.debug_mode = debug_mode
        self.work_tracker_class = work_tracker_class
        self.templates = templates

        self.data = {}
        self.meta = {}
        self.parameters = {}
        self.error: Optional[Exception] = None
        self.prevent_execution = False
        self.description: Optional[str] = None

        self.discover_parameters()
        self.path = self.determine_path()

        self.data_path = os.path.join(self.path, 'experiment_data.json')
        self.meta_path = os.path.join(self.path, 'experiment_meta.json')
        self.error_path = os.path.join(self.path, 'experiment_error.txt')
        self.log_path = os.path.join(self.path, 'experiment_log.txt')

        self.code_name = 'snapshot'
        self.code_path = os.path.join(self.path, f'{self.code_name}.py')

        self.logger: Optional[logging.Logger] = None
        self.work_tracker = self.work_tracker_class(0)

        self.analysis = RecordCode()

        # ~ Parsing command line arguments
        # TODO: I could introduce abstract base class and dependency inject this
        self.arg_parser = ExperimentArgParser(
            name=self.namespace,
            path=self.path,
            description=self.description
        )

    def read_parameters(self, path: str) -> None:
        with open(path, mode='r') as file:
            content = file.read()

        if path.endswith('.json'):
            self.load_parameters_json(content)

        if path.endswith('.py'):
            self.load_parameters_py(content)

    def load_parameters_json(self, content: str) -> None:
        data = json.loads(content)
        for key, value in data.items():
            if key in self.parameters:
                self.glob[key] = value
                self.parameters[key] = value

    def load_parameters_py(self, content: str) -> None:
        locals_dict = {}
        exec(content, self.glob, locals_dict)
        for key, value in locals_dict.items():
            if key in self.parameters:
                self.glob[key] = value
                self.parameters[key] = value

    def prepare_logger(self) -> None:
        """
        Creates the internal logger instance and registers all the appropriate handlers.

        Before this method :attr:`~.Experiment.logger` is ``None``. Only afterwards the logger is actually
        initialized. Afterwards all the necessary handlers are also attached.
        This method omits the file handler if the experiment is imported instead of executed.
        """
        self.logger = logging.Logger(self.namespace)
        formatter = logging.Formatter("%(asctime)s - %(message)s")

        # We will always use the stdout handler, but if we the experiment object is not explicitly created
        # for execution, we omit the file handler which would write to the log file, so that we dont
        # overwrite the already existing log file of the actual experiment execution
        handlers = [logging.StreamHandler(sys.stdout)]
        if not self.prevent_execution:
            handlers += [logging.FileHandler(self.log_path)]

        for handler in handlers:
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def determine_path(self) -> str:
        # ~ are we importing a snapshot file?
        # The first thing we do is to check whether this invocation of the experiment is the import of a
        # snapshot file (located in an already completed experiment record folder) or if this is actually
        # a new experiment.
        # We determine if it is a snapshot by checking if there is a "experiment_meta" file in the same
        # folder (which will *always* be the case for a completed experiment).
        folder_path = pathlib.Path(self.glob['__file__']).parent.absolute()
        meta_path = os.path.join(folder_path, 'experiment_meta.json')
        if os.path.exists(meta_path) and self.glob['__name__'] != '__main__':
            # In that case we obviously want to return the folder path of the very record folder the
            # snapshot file is inside of.
            return str(folder_path)

        # ~ resolving the namespace
        # ... otherwise, if it is a new experiment we need to determine the new record folder path that
        # will have to be created to hold all the experiment results.
        # "self.namespace" is a string which uniquely characterizes this very experiment in the broader
        # scope of the base path. It may contain slashes to indicate a nested folder structure.
        names: List[str] = self.namespace.split("/")

        path_list = names
        namespace_path = os.path.join(self.base_path, *path_list)

        if self.debug_mode:
            path_list.append("debug")

        elif not os.path.exists(namespace_path):
            path_list.append("000")

        else:
            contents = os.listdir(namespace_path)
            indices = []
            for path in contents:
                try:
                    name = os.path.basename(path)
                    indices.append(int(name))
                except ValueError:
                    pass
            if indices:
                index = max(indices) + 1
            else:
                index = 0

            path_list.append(f"{index:03d}")

        return os.path.join(self.base_path, *path_list)

    def prepare_path(self) -> None:
        # ~ Make sure the path exists
        # If the nested structure provided by "self.namespace" does not exist, we create it here
        current_path = ''
        for name in pathlib.Path(self.path).parts:
            current_path = os.path.join(current_path, name)
            if not os.path.exists(current_path):
                os.mkdir(current_path)

        # In debug mode always the same special folder path is being used and we need to make sure to
        # get rid of any potential remaining previous instance of this folder to start with a clean slate.
        if self.debug_mode and os.path.exists(current_path):
            shutil.rmtree(current_path)
            os.mkdir(current_path)

    def discover_parameters(self) -> None:
        for key, value in self.glob.items():
            if key.isupper():
                self.parameters[key] = value

        # ~ Detecting special parameters
        if "__doc__" in self.glob and isinstance(self.glob["__doc__"], str):
            self.data["description"] = self.glob["__doc__"]

        if "DEBUG" in self.glob and isinstance(self.glob["DEBUG"], bool):
            self.debug_mode = self.glob["DEBUG"]

    def __getitem__(self, key):
        keys = key.split("/")
        current = self.data
        for key in keys:
            if key in current:
                current = current[key]
            else:
                raise KeyError(f'The namespace "{key}" does not exist within the experiment data storage')

        return current

    def __setitem__(self, key, value):
        keys = key.split("/")
        current = self.data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}

            current = current[key]

        current[keys[-1]] = value

    def prepare(self):
        """
        This method *has to be called* as the very first thing within the experiment context like this:

        .. code-block:: python

            with Experiment(base_path, 'my_namespace', glob=globals()) as e:
                e.prepare()  # Very important!

        Only through this method it can be ensured that the experiment module can later be safely imported
        without actually causing the experiment to be executed again unintentionally.
        """
        if self.prevent_execution:
            # We need to call this or it would cause a bug
            self.prepare_logger()

            # By raising this special exception within the experiment context we are able to essentially
            # silently skip the entire body of the context, because we simply ignore this exception in
            # __exit__
            raise NoExperimentExecution()

    def open(self, name: str, mode: str = "w"):
        file_path = os.path.join(self.path, name)
        self.data['artifacts'][name] = file_path
        return open(file_path, mode=mode)

    def commit_raw(self, name: str, content: str) -> None:
        with self.open(name) as file:
            file.write(content)

    def commit_fig(self, name: str, fig: object, bbox_inches='tight', pad_inches=0.05) -> None:
        with self.open(name, mode='wb') as file:
            _, fig_format = name.split('.')
            fig.savefig(file, format=fig_format, bbox_inches=bbox_inches, pad_inches=pad_inches)

    def commit_json(self, name: str, data: dict, indent: int = 4) -> None:
        with self.open(name, mode='w') as file:
            json.dump(data, file, indent=4)

    def write_path(self, path: str) -> None:
        with open(path, mode='w') as file:
            file.write(self.path)

    def __enter__(self) -> 'Experiment':

        # At this point we check if the experiment is created in "execution" mode or in "analysis" mode.
        # The latter is always the case when the module is not explicitly directly executed.
        if self.glob["__name__"] != "__main__":
            # Setting this flag will signal to the "prepare" method to take the necessary steps to skip
            # the entire body of the experiment.
            self.prevent_execution = True
            return self

        self.args = self.arg_parser.parse_args()

        # If an output path is provided through the arguments then we create a new file at that path and
        # as the content we simply write the string experiment path
        if self.args.output_path:
            self.write_path(self.args.output_path)

        # If additional parameters are provided by the arguments then we try to parse those
        if self.args.parameters_path:
            self.read_parameters(self.args.parameters_path)

        self.prepare_path()
        self.prepare_logger()

        self.work_tracker.start()

        start_time = time.time()
        self.data["start_time"] = start_time
        self.data["path"] = self.path
        self.data["artifacts"] = {}

        # ~ logging the experiment start
        self.logger.info("=" * 80)
        self.logger.info("EXPERIMENT STARTED")
        self.logger.info(f"   namespace: {self.namespace}")
        self.logger.info(f'   start time: {datetime.fromtimestamp(self.data["start_time"])}')
        self.logger.info(f'   path: {self.data["path"]}')
        self.logger.info(f"   debug mode: {self.debug_mode}")
        self.logger.info("=" * 80)

        # ~ Creating meta file
        self.meta['running'] = True
        self.meta['start_time'] = start_time
        self.save_experiment_meta()

        return self

    def __exit__(self, exc_type, exc_value, exc_tb):

        if isinstance(exc_value, NoExperimentExecution):
            # "NoExperimentExecution" is a special exception which is always being risen if an experiment
            # file is being accessed without it being "__main__" aka without the explicit intent of actually
            # executing that experiment. In that case we check if we can load the artifacts of an already
            # executed experiment. This would be the case if the "snapshot.py" artifact from the experiment
            # records folder is being imported.
            self.load_records()
            return True

        self.data["end_time"] = time.time()
        self.data["elapsed_time"] = self.data["end_time"] - self.data["start_time"]

        if isinstance(exc_value, Exception):
            self.save_experiment_error(exc_value, exc_tb)
            self.error = exc_value

        # ~ Copy the actual code source file
        self.copy_source()

        # ~ Render all the templates
        self.render_templates()

        # ~ Saving data into file
        self.save_experiment_data()

        # ~ Updating meta file
        self.meta['running'] = False
        self.save_experiment_meta()

        # ~ logging the experiment end
        self.logger.info("=" * 80)
        self.logger.info("EXPERIMENT ENDED")
        self.logger.info(f'   end time: {datetime.fromtimestamp(self.data["end_time"])}')
        self.logger.info(f'   elapsed time: {self.data["elapsed_time"]/3600:.2f}h')
        self.logger.info(f"   error: {self.error}")
        self.logger.info("=" * 80)

        return True

    def load_records(self) -> None:
        if os.path.exists(self.data_path):
            with open(self.data_path) as json_file:
                self.data = json.load(json_file)

    def save_experiment_meta(self):
        with open(self.meta_path, mode="w") as json_file:
            json.dump(self.meta, json_file)

    def save_experiment_data(self):
        with open(self.data_path, mode="w") as json_file:
            json.dump(self.data, json_file)

    def save_experiment_error(self, exception_value, exception_traceback) -> None:
        with open(self.error_path, mode="w") as file:
            file.write(f"{exception_value.__class__.__name__.upper()}: {exception_value}")
            file.write("\n\n")
            tb = traceback.format_tb(exception_traceback)
            file.writelines(tb)

        self.info(f"saved experiment error to: {self.error_path}")
        self.info("\n".join(tb))

    def copy_source(self) -> None:
        # Since we have the globals() dict from the experiment file, we can access the __file__ global
        # value of that dict to get the file of the experiment code file.
        source_path = pathlib.Path(self.glob['__file__']).absolute()
        self.data['artifacts']['source'] = str(source_path)
        shutil.copy(source_path, self.code_path)

    def render_templates(self):
        self.data['artifacts']['templates'] = {}
        for file_name, template in self.templates.items():
            path = os.path.join(self.path, file_name)
            self.data['artifacts']['templates'][file_name] = path
            with open(path, mode='w') as file:
                content = template.render(experiment=self)
                file.write(content)

    @property
    def work(self) -> int:
        return self.work_tracker.total_work

    @work.setter
    def work(self, value: int) -> None:
        self.work_tracker.set_total_work(value)

    def info(self, message: str):
        self.logger.info(message)

    def update(self, n: int = 1, weight: float = 1.0, monitor_resources=True):
        self.work_tracker.update(n, weight)

        self.logger.info(
            f"({self.work_tracker.completed_work}/{self.work_tracker.total_work}) DONE - "
            f"ETA: {datetime.fromtimestamp(self.work_tracker.eta)} "
            f"(remaining time: {self.work_tracker.remaining_time/3600:.3f}h)"
        )

        if monitor_resources:
            pass


class ArchivedExperiment:

    def __init__(self):
        pass
