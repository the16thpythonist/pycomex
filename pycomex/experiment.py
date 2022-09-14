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
import importlib.util
from datetime import datetime
from typing import List, Type, Optional, Tuple, Dict

import jinja2 as j2
import psutil

from pycomex.util import TEMPLATE_ENV, EXAMPLES_PATH
from pycomex.util import RecordCode
from pycomex.util import SkipExecution
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
    Context Manager to wrap the main business logic of a computational experiment.
    """
    DEFAULT_TEMPLATES = {
        'analysis.py': TEMPLATE_ENV.get_template('analysis.py.j2'),
        'annotations.rst': TEMPLATE_ENV.get_template('annotations.py.j2')
    }

    DATETIME_FORMAT = '%A, %d %b %Y  at %H:%M'

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

        self.analysis = RecordCode(initial_stack_index=2)
        self.analysis.exit_callbacks.append(lambda rc, i: self.render_template('analysis.py'))

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
        # "execution" mode is only when the module is directly executed and analysis mode is if the module
        # is imported by another module for example. In that case we want to skip the entire experiment
        # content!
        if self.glob["__name__"] != "__main__":
            self.prevent_execution = True
            self.analysis.skip = True

            # Even if we are in analysis mode, we still want to be able to log status messages through the
            # experiment so we need to at least prepare the console logger.
            self.prepare_logger()

            # Here comes a bit of the magic: In analysis mode, we assume that the experiment is already done
            # and an artifacts folder already exists. This method will load all of the experiment data,
            # which is saved as a JSON file in that folder back into this object, so that even if this
            # object is only imported we can still interact with it as if it was just at the end of the
            # experiment execution!
            self.load_records()

            # This exception will be caught by the "Skippable" context manager which always has to precede
            # the experiment manager, effectively skipping the entire context body.
            raise SkipExecution()

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
        self.data["monitoring"] = {}

        # ~ logging the experiment start
        template = TEMPLATE_ENV.get_template('experiment_started.text.j2')
        self.info_lines(template.render(experiment=self))

        # ~ Creating meta file
        self.meta['running'] = True
        self.meta['start_time'] = start_time
        self.status(log=False)
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

        self.data['end_time'] = time.time()
        self.data['elapsed_time'] = self.data['end_time'] - self.data['start_time']
        self.data['duration'] = self.data['elapsed_time']

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
        self.meta['end_time'] = self.data['end_time']
        self.meta['duration'] = self.data['duration']
        self.save_experiment_meta()

        # ~ logging the experiment end
        template = TEMPLATE_ENV.get_template('experiment_ended.text.j2')
        self.info_lines(template.render(experiment=self))

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

    def render_template(self, file_name):
        template = self.templates[file_name]
        path = os.path.join(self.path, file_name)
        self.data['artifacts']['templates'][file_name] = path
        with open(path, mode='w') as file:
            content = template.render(experiment=self)
            file.write(content)

    def render_templates(self):
        self.data['artifacts']['templates'] = {}
        for file_name in self.templates.keys():
            self.render_template(file_name)

    # -- EXPERIMENT STATUS --

    @property
    def work(self) -> int:
        return self.work_tracker.total_work

    @work.setter
    def work(self, value: int) -> None:
        self.work_tracker.set_total_work(value)

    def update(self, n: int = 1, weight: float = 1.0, monitor_resources=True):
        self.work_tracker.update(n, weight)

        self.logger.info(
            f"({self.work_tracker.completed_work}/{self.work_tracker.total_work}) DONE - "
            f"ETA: {datetime.fromtimestamp(self.work_tracker.eta)} "
            f"(remaining time: {self.work_tracker.remaining_time/3600:.3f}h)"
        )

        if monitor_resources:
            pass

    def update_monitoring(self) -> dict:
        ts = time.time()
        mem = psutil.virtual_memory()
        store = psutil.disk_usage(self.path)
        update = {
            'ts': ts,
            'cpu': psutil.cpu_percent(0.1),
            'memory': {
                'total': mem.total / 1024**3,
                'free': mem.free / 1024**3,
            },
            'storage': {
                'total': store.total / 1024**3,
                'free': store.free / 1024**3,
            }
        }
        self.data['monitoring'][ts] = update

        return update

    def status(self,
               log: bool = True
               ) -> None:
        """
        This function primarily updates the metadata of the experiment such as the total runtime up to
        that point as well as some hardware information such as the CPU and RAM usage.

        Optionally also prints this information as an INFO type log message

        :returns: None
        """
        # Updating all the hardware monitoring
        monitoring = self.update_monitoring()

        self.meta['elapsed_time'] = time.time() - self.meta['start_time']
        self.meta['monitoring'] = monitoring

        if log:
            template = TEMPLATE_ENV.get_template('experiment_status.text.j2')
            self.info_lines(template.render(experiment=self))

        self.save_experiment_meta()

    # -- LOGGING --

    def info(self, message: str) -> None:
        """
        Logs the given ``message`` string as an "INFO" level log message.

        :param str message: The string message to be printed as a log.
        :returns: None
        """
        self.logger.info(message)

    def info_lines(self, message: str) -> None:
        """
        Logs each line of the given multiline ``message`` string as an "INFO" level log message.

        :param str message: The string message to be printed as a log
        :returns: None
        """
        lines = message.split('\n')
        for line in lines:
            self.logger.info(line)

    # -- UTILITY --

    @property
    def start_time_pretty(self) -> str:
        start_datetime = datetime.fromtimestamp(self.data['start_time'])
        return start_datetime.strftime(self.DATETIME_FORMAT)

    @property
    def end_time_pretty(self) -> str:
        if 'end_time' not in self.data:
            raise AttributeError('The experiment appears to still be running, which means there is no '
                                 '"end_time" that can be accessed yet!')

        end_datetime = datetime.fromtimestamp(self.data['end_time'])
        return end_datetime.strftime(self.DATETIME_FORMAT)


class ArchivedExperiment:

    def __init__(self,
                 archive_path: str):
        self.path = archive_path

        self.module_path = os.path.join(self.path, 'snapshot.py')

        self.spec = None
        self.module = None

    def import_experiment_module(self):
        self.spec = importlib.util.spec_from_file_location('snapshot', self.module_path)
        self.module = importlib.util.module_from_spec(self.spec)
        self.spec.loader.exec_module(self.module)

    def __enter__(self):
        self.import_experiment_module()
        for key in dir(self.module):
            value = getattr(self.module, key)
            if isinstance(value, Experiment):
                return value

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass


# == EXPERIMENT REGISTRY ====================================================================================


class NamespaceFolder:

    class MetaPlaceholder:
        pass

    def __init__(self,
                 folder_path: str):
        self.path = folder_path
        self.experiments: Dict[str, str] = {}
        self.experiment_metas: Dict[str, dict] = {}
        self.experiment_index_map: Dict[int, str] = {}

        self.meta = self.MetaPlaceholder()
        self.MetaPlaceholder.__contains__ = self.__contains__
        self.MetaPlaceholder.__getitem__ = self.meta_getitem

        self.update()

    def update(self):
        for element_name in os.listdir(self.path):
            element_path = os.path.join(self.path, element_name)
            if os.path.isdir(element_path) and 'experiment_meta.json' in os.listdir(element_path):
                self.experiments[element_name] = element_path

                meta_path = os.path.join(element_path, 'experiment_meta.json')
                with open(meta_path, mode='r') as file:
                    self.experiment_metas[element_name] = json.loads(file.read())

                if element_name.isdigit():
                    element_index = int(element_name)
                    self.experiment_index_map[element_index] = element_name

    def __len__(self) -> int:
        return len(self.experiments)

    def __contains__(self, key) -> bool:
        if isinstance(key, str):
            return key in self.experiments.keys()
        elif isinstance(key, int):
            return key in self.experiment_index_map.keys()

    def __getitem__(self, key) -> ArchivedExperiment:
        if isinstance(key, str):
            path = self.experiments[key]
        elif isinstance(key, int):
            name = self.experiment_index_map[key]
            path = self.experiments[name]
        else:
            raise TypeError(f'type {type(key)} cannot be used to index {self.__class__.__name__}!')

        archived_experiment = ArchivedExperiment(path)
        return archived_experiment

    def meta_getitem(self, key):
        if isinstance(key, str):
            meta = self.experiment_metas[key]
        elif isinstance(key, int):
            name = self.experiment_index_map[key]
            meta = self.experiment_metas[name]
        else:
            raise TypeError(f'type {type(key)} cannot be used to index {self.__class__.__name__}!')

        return meta


class ExperimentRegistry:

    def __init__(self,
                 base_path: str,
                 max_depth: int = 5):
        self.path = base_path
        self.max_depth = max_depth

        self.namespaces = {}

    def load(self):
        self.traverse_folder([], 0)

    def traverse_folder(self,
                        path_elements: List[str],
                        recursion_depth: int = 0):
        if recursion_depth >= self.max_depth:
            return

        path = os.path.join(self.path, *path_elements)
        for root, folders, files in os.walk(path):

            for folder in folders:
                folder_path = os.path.join(root, folder)
                # For the folders there are only two cases: The first case is that the folder contains an
                # "experiment_meta.json" which identifies it as an experiment archive. That would mean that
                # the current folder is a namespace folder and needs to be added to the dict. Otherwise
                # we recurse further into the folder
                if 'experiment_meta.json' in os.listdir(folder_path):
                    # The namespace name in this case is simply the combination of all the sub path sections
                    # we needed to get here except the base path of the registry itself
                    namespace = '/'.join(path_elements)
                    self.namespaces[namespace] = NamespaceFolder(path)
                    return

                else:
                    self.traverse_folder(path_elements.copy() + [folder], recursion_depth + 1)

            return

    def __contains__(self, key):
        return key in self.namespaces.keys()
