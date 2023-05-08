import os
import shutil
import sys
import time
import json
import inspect
import traceback
import typing as t
import logging
import datetime
from collections import defaultdict
from pycomex.utils import random_string, dynamic_import
from pycomex.utils import TEMPLATE_ENV
from pycomex.utils import CustomJsonEncoder


class Experiment:
    """
    Functional Experiment Implementation. This class acts as a decorator.
    """

    def __init__(self,
                 base_path: str,
                 namespace: str,
                 glob: dict,
                 debug: bool = False,
                 name_format: str = '{date}__{time}__{id}'):
        self.base_path = base_path
        self.namespace = namespace
        self.glob = glob
        self.debug = debug
        self.name_format = name_format

        # ~ setting up logging
        self.log_formatter = logging.Formatter('%(asctime)s - %(message)s')
        stream_handler = logging.StreamHandler(sys.stdout)
        # stream_handler.setFormatter(self.log_formatter)
        self.logger = logging.Logger(name='experiment')
        self.logger.addHandler(stream_handler)

        self.path: t.Optional[str] = None
        self.func: t.Optional[t.Callable] = None
        self.parameters: dict = {}
        self.data: dict = {}
        self.metadata: dict = {
            'status': None,
            'start_time': None,
            'end_time': None,
            'duration': None,
            'has_error': False,
            'base_path': str(base_path),
            'namespace': str(namespace),
            'description': '',
            'short_description': '',
        }
        self.error = None
        self.tb = None

        # This list will contain the absolute string paths to all the python module files, which this
        # experiment depends on (for example in the case that this experiment is a sub experiment that was
        # created with the "extend" constructor)
        self.dependencies: t.List[str] = []

        self.analyses: t.List[t.Callable] = []
        self.hook_map: t.Dict[str, t.List[t.Callable]] = defaultdict(list)

        self.update_parameters()

        self.glob['__experiment__'] = self

    @property
    def dependency_names(self) -> t.List[str]:
        """
        A list of all the names of the python dependency modules, without the file extensions.
        """
        names = []
        for path in self.dependencies:
            name = os.path.basename(path)
            name = os.path.splitext(name)[0]
            names.append(name)

        return names

    def update_parameters_special(self):
        if '__DEBUG__' in self.parameters:
            self.debug = bool(self.parameters['__DEBUG__'])

    def update_parameters(self):
        for name, value in self.glob.items():
            if name.isupper():
                self.parameters[name] = value

        # This method will search through the freshly updated parameters dictionary for "special" keys
        # and then use those values to trigger some more fancy updates based on those.
        self.update_parameters_special()

    # ~ Logging

    def log(self, message: str):
        self.logger.info(message)

    def log_lines(self, lines: t.List[str]):
        for line in lines:
            self.log(line)

    def log_parameters(self):
        for name, value in self.parameters:
            self.log(name)

    # ~ Hook System

    def hook(self, name: str, replace: bool = True, default: bool = True):

        def decorator(func, *args, **kwargs):
            # 07.05.23 - The thingy
            if default and name in self.hook_map:
                return

            if replace:
                self.hook_map[name] = [func]
            else:
                self.hook_map[name].append(func)

        return decorator

    def apply_hook(self, name: str, default: t.Optional[t.Any] = None, **kwargs):
        result = default

        if name in self.hook_map:
            for func in self.hook_map[name]:
                result = func(self, **kwargs)

        return result

    # ~ Posthoc Analysis functionality

    def analysis(self, func, *args, **kwargs):
        self.analyses.append(func)

    def execute_analyses(self):
        for func in self.analyses:
            func(self)

    def get_analysis_code_map(self) -> t.Dict[str, str]:
        map = {}
        for func in self.analyses:
            name = f'{func.__module__}.{func.__name__}'
            map[name] = inspect.getsource(func)

        return map

    # ~ Experiment Execution

    def initialize(self):
        # ~ creating archive
        self.prepare_path()

        # ~ creating the log file
        file_handler = logging.FileHandler(self.log_path)
        file_handler.setFormatter(self.log_formatter)
        self.logger.addHandler(file_handler)

        # ~ copying all the code into the archive
        self.save_dependencies()
        self.save_code()

        # ~ updating the metadata
        self.metadata['status'] = 'running'
        self.metadata['start_time'] = time.time()
        self.metadata['duration'] = 0
        self.metadata['description'] = self.glob['__doc__']
        self.save_metadata()

        # ~ creating the analysis module
        self.save_analysis()

        # ~ logging the start conditions
        template = TEMPLATE_ENV.get_template('functional_experiment_start.out.j2')
        self.log_lines(template.render({'experiment': self}).split('\n'))

    def finalize(self):
        # ~ updating the metadata
        self.metadata['end_time'] = time.time()
        self.metadata['duration'] = self.metadata['end_time'] - self.metadata['start_time']
        self.metadata['status'] = 'done'

        # ~ saving all the data
        self.save_metadata()
        self.save_data()

        # ~ handling a possible exception during the experiment
        if self.error:
            template = TEMPLATE_ENV.get_template('functional_experiment_error.out.j2')
            self.log_lines(template.render({'experiment': self}).split('\n'))

        # ~ logging the end conditions
        template = TEMPLATE_ENV.get_template('functional_experiment_end.out.j2')
        self.log_lines(template.render({'experiment': self}).split('\n'))

    def execute(self):
        self.initialize()

        try:
            self.func(self)
        except Exception as error:
            self.error = error
            self.tb = traceback.format_exc()

        self.finalize()

    def is_main(self) -> bool:
        return self.glob['__name__'] == '__main__'

    def __call__(self, func, *args, **kwargs):
        self.func = func

        return self

    def run_if_main(self):

        if self.is_main():
            self.execute()
            self.execute_analyses()

    # ~ Archive management

    def check_path(self) -> None:
        if not self.path:
            raise ValueError('Attempting to access a specific path of archive, but not archive path exists '
                             'yet! Please make sure an experiment is either loaded or properly initialized '
                             'first before attempting to access any specific archive element.')

    @property
    def metadata_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), 'experiment_meta.json')

    @property
    def data_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), 'experiment_data.json')

    @property
    def code_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), 'code.py')

    @property
    def log_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), 'experiment_out.log')

    @property
    def error_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), 'experiment_error.log')

    @property
    def analysis_path(self) -> str:
        self.check_path()
        return os.path.join(str(self.path), 'analysis.py')

    def prepare_path(self):
        # One thing which we will need to assume as given here is that the given base_path exists!
        # The rest of the nested sub structure we can create if need be, but the base path has to exist in
        # the first place as a starting point
        if not os.path.exists(self.base_path):
            raise NotADirectoryError(f'The given base path "{self.base_path}" for the experiment archive '
                                     f'does not exist! Please make sure the path points to a valid folder.')

        if not os.path.isdir(self.base_path):
            raise NotADirectoryError(f'The given experiment base path "{self.base_path}" is not a '
                                     f'directory! Please make sure the file points to a valid folder.')

        # Then we can iterate through all the components of the namespace and recursively create those
        # directories if they not already exist.
        namespace_list = self.namespace.split('/')
        current_path = self.base_path
        for name in namespace_list:
            current_path = os.path.join(current_path, name)
            if not os.path.exists(current_path):
                os.mkdir(current_path)

        # Now at this point we can be sure that the base path exists and we can create the specific
        # archive folder. How this archive folder will be called first of all depends on the "self.debug".
        # If it is true, then we will forcefully recreate the debug folder. If false, we create a new
        # folder based on the class internal format string.
        if self.debug:
            self.path = os.path.join(current_path, 'debug')
            if os.path.exists(self.path):
                shutil.rmtree(self.path)

        else:
            now = datetime.datetime.now()
            date_string = now.strftime('%d_%m_%Y')
            time_string = now.strftime('%H_%M')
            id_string = random_string(length=4)
            name = self.name_format.format(
                date=date_string,
                time=time_string,
                id=id_string,
            )
            self.path = os.path.join(current_path, name)

        os.mkdir(self.path)

    def save_metadata(self) -> None:
        with open(self.metadata_path, mode='w') as file:
            content = json.dumps(self.metadata, indent=4, sort_keys=True)
            file.write(content)

    def save_data(self) -> None:
        with open(self.data_path, mode='w') as file:
            content = json.dumps(self.data, cls=CustomJsonEncoder)
            file.write(content)

    def save_code(self) -> None:
        source_path = self.glob['__file__']
        destination_path = self.code_path
        shutil.copy(source_path, destination_path)

    def save_dependencies(self) -> None:
        for path in self.dependencies:
            file_name = os.path.basename(path)
            destination_path = os.path.join(self.path, file_name)
            shutil.copy(path, destination_path)

    def save_analysis(self) -> None:
        with open(self.analysis_path, mode='w') as file:
            template = TEMPLATE_ENV.get_template('functional_analysis.py.j2')
            content = template.render({'experiment': self})
            file.write(content)

    # ~ Internal data storage

    def __getitem__(self, key):
        """
        This class implements custom behavior when using an index assignment operation. Only string keys
        are supported, but these strings may describe nested structures by using the "/" character, as one
        would do to define a nested folder structure.

        As an example consider the two equivalent ways of retrieving a value stored within an experiments
        data store (assuming the value exists):

        .. code-block:: python

            with (e := Experiment('/tmp', 'name', globals()):
                # ... adding data
                value = e.data['metrics']['mse']['10']
                value = e['metrics/mse/10']

        :returns: The value from the data store
        """
        keys = key.split("/")
        current = self.data
        for key in keys:
            if key in current:
                current = current[key]
            else:
                raise KeyError(f'The namespace "{key}" does not exist within the experiment data storage')

        return current

    def __setitem__(self, key, value):
        """
        This class implements custom behavior when using an index assignment operation. Only string keys
        are supported, but these strings may describe nested structures by using the "/" character, as one
        would do to define a nested folder structure. If the specified nested location does not already
        exist within the internal data dict structure, it will be *automatically* created.

        .. code-block:: python

            with (e := Experiment('/tmp', 'name', globals()):
                # This will be saved into e.data['metrics']['repetitions']['10']['metric']
                # and if that nesting does not exist like this it will be created automatically, no matter
                # how many of the intermediate steps are missing!
                e['metrics/repetitions/10/metric'] = 10.23

        :returns: None
        """
        if not isinstance(key, str):
            raise ValueError('You are attempting to add to the internal experiment storage, by using a non '
                             'string key. This is not possible! Please use a valid query string to identify '
                             'the (nested) location where to save the value within the storage structure.')

        # ~ Decoding the nesting and potentially creating it along the way if it does not exist
        keys = key.split("/")
        current = self.data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}

            current = current[key]

        # 28.11.2022
        # At this point we were previously performing a value processing. For example if the value to be
        # saved was a numpy array it was converted into a list. This was done to prevent an exception to
        # arise from numpy arrays which are not naturally serializable.
        # - I realized that this should be addressed by a custom JsonEncoder because there are other ways
        #   for a numpy array to accidentally enter the experiment storage which are not caught here
        # - This causes unwanted implicit behaviour, where the user for example thinks he has saved a numpy
        #   array into the experiment storage & wants to retrieve it as such again during the same runtime.

        current[keys[-1]] = value

    def __getattr__(self, item: str):
        if item.isupper():
            return self.parameters[item]
        else:
            raise AttributeError(f'The experiment object does not have an attribute "{item}"')

    def __setattr__(self, key, value):
        if key.isupper():
            self.parameters[key] = value
            self.glob[key] = value
        else:
            super(Experiment, self).__setattr__(key, value)

    # ~ File Handling Utility

    def open(self, file_name: str, *args, **kwargs):
        """
        This is an alternative file context for the default python ``open`` implementation.
        """
        path = os.path.join(self.path, file_name)
        return open(path, *args, **kwargs)

    def commit_fig(self,
                   file_name: str,
                   fig: t.Any,
                   ) -> None:
        """
        Given the name ``file_name`` for a file and matplotlib Figure instance, this method will save the
        figure into a new image file in the archive folder.

        :returns: None
        """
        path = os.path.join(self.path, file_name)
        fig.savefig(path)

    def commit_json(self,
                    file_name: str,
                    data: t.Union[t.Dict, t.List],
                    encoder_cls=CustomJsonEncoder
                    ) -> None:
        """
        Given the name ``file_name`` for a file and some json encodable data structure ``data``, this method
        will write that data into a new JSON file in the archive folder.

        :param file_name: The name that the file should have, including the .json extension.
        :param data: Either a dict or list which can be json encoded, meaning no custom data structures
        :param encoder_cls: A Json EncoderClass when custom objects need to be encoded. Default is the
            pycomex.CustomJsonEncoder, which is able to encode numpy data by default.

        :returns: None
        """
        path = os.path.join(self.path, file_name)
        with open(path, mode='w') as file:
            content = json.dumps(data, cls=encoder_cls)
            file.write(content)

    def commit_raw(self, file_name: str, content: str) -> None:
        """
        Given the name ``file_name`` for a file and the string ``content``, this method will save the
        string content into a new file of that name within the experiment archive folder.

        :param file_name: The name that the file should have, including the file extension
        :param content: The string content to write into the text file

        :returns: void
        """
        file_path = os.path.join(self.path, file_name)
        with open(file_path, mode='w') as file:
            file.write(content)

    # ~ Alternate constructors

    @classmethod
    def extend(cls,
               experiment_path: str,
               base_path: str,
               namespace: str,
               glob: dict):
        """
        This method can be used to extend an experiment through experiment inheritance by providing the
        path ``experiment_path`` to the base experiment module. It will return the ``Experiment`` instance
        which can subsequently be extended by defining hook implementations and modifying parameters.

        ..code-block: python

            experiment = Experiment.extend(
                experiment_path='base_experiment.py',
                base_path=os.getcwd(),
                namespace='results/sub_experiment',
                glob=globals(),
            )

            experiment.PARAMETER = 2 * experiment.PARAMETER

            experiment.hook('hook')
            def hook(e):
                e.log('hook implementation')

        :param experiment_path: Either a relative or an absolute path to the python module which contains
            the base experiment code to be extended.
        :param base_path: An absolute path to the folder to act as the base path for the archive structure
        :param namespace: A namespace string that defines the archive structure of the experiment
        :param glob: The globals() dictionary

        :returns: Experiment instance
        """
        # First of all we need to import that module to access the Experiment instance that is
        # defined there. That is the experiment which we need to extend.

        # 28.04.23 - this fixes a bug, where the relative import would only work the current working
        # directory is exactly the folder that also contains. Previously if the working directory was
        # a different one, it would not work.
        try:
            module = dynamic_import(experiment_path)
        except (FileNotFoundError, ImportError):
            parent_path = os.path.dirname(glob['__file__'])
            experiment_path = os.path.join(parent_path, *os.path.split(experiment_path))
            module = dynamic_import(experiment_path)

        # 28.04.23 - before this was implemented over a hardcoded variable name for an experiment, but
        # strictly speaking we can't assume that the experiment instance will always be called the same
        # this is just a soft suggestion.
        experiment = None
        for key in dir(module):
            value = getattr(module, key)
            if isinstance(value, Experiment):
                experiment = value

        # Then we need to push the path of that file to the dependencies.
        experiment.dependencies.append(experiment.glob['__file__'])

        # Finally we need to replace all the archive-specific parameters like the base path
        # and the namespace
        experiment.base_path = base_path
        experiment.namespace = namespace
        # The globals we merely want to update and not replace since we probably won't define
        # all of the parameters new in the sub experiment module.
        # TODO: nested updates!
        experiment.glob.update(glob)
        experiment.update_parameters()

        # This line is necessary so that the experiments can be discovered by the CLI
        glob['__experiment__'] = experiment

        return experiment

    @classmethod
    def load(cls, path: str):
        module = dynamic_import(path)
        experiment = module.experiment

        folder_path = os.path.dirname(path)
        experiment.path = folder_path

        with open(experiment.metadata_path) as file:
            content = file.read()
            experiment.metadata = json.loads(content)

        with open(experiment.data_path) as file:
            content = file.read()
            experiment.data = json.loads(content)

        return experiment
