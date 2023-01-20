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
import threading
import importlib.util
import typing as t
from datetime import datetime
from collections import defaultdict
from typing import List, Type, Optional, Tuple, Dict

import jinja2 as j2
import psutil

from pycomex.util import TEMPLATE_ENV, EXAMPLES_PATH
from pycomex.util import NULL_LOGGER
from pycomex.util import RecordCode
from pycomex.util import SkipExecution
from pycomex.util import CustomJsonEncoder
from pycomex.util import Singleton
from pycomex.util import split_namespace
from pycomex.work import AbstractWorkTracker
from pycomex.work import NaiveWorkTracker



def _run_experiment(experiment_path: str,
                   parameters_path: Optional[str] = None,
                   blocking: bool = True,
                   print_output: bool = True,
                   ) -> Tuple[str, subprocess.CompletedProcess]:
    """
    Given the string absolute ``experiment_path`` to the python experiment module, this function will
    execute that module as an experiment.

    :param Optional[str] parameters_path: A string path to either a .JSON or a .PY file which specify
        parameter overwrite for the execution of the experiment.
    :param bool blocking: Whether to run the experiment in a blocking manner. If False, then the
        experiment will be started in the background.
    :param bool print_output: Whether to print the output of the subprocess to stdout

    :returns: A tuple whose first element is the absolute string path ot the experiment archive folder which
        was created by the experiment. The second element is the subprocess.Process object which was used
        to execute the experiment.
    """
    with tempfile.NamedTemporaryFile(mode='w+') as out_path:

        command = f'{sys.executable} {experiment_path} -o {out_path.name}'
        if parameters_path is not None:
            command += f' -p {parameters_path}'

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if blocking:
            for line in process.stdout:
                if print_output:
                    print(line.decode(), end='')

            process.wait()
        else:
            time.sleep(0.1)

        with open(out_path.name) as file:
            archived_path = file.read()

    return archived_path, process


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


class ExperimentExchange(metaclass=Singleton):
    """
    Singleton which acts as data transfer object during experiment inheritance.

    **THE CHALLENGE WITH EXPERIMENT INHERITANCE**

    In experiment inheritance child experiments, realized through the SubExperiment class, are able to
    refer to a parent experiment whose main experiment code will then be executed instead. However, for this
    to be a useful feature there has to be the option for child experiments to pass additional information
    to the parent to be able to overwrite some default parameters (global variables).

    The realization of such parameter overwrites is not trivial due to the fact of how experiments work.
    In essence, a parent experiment can be called by simply importing that module, since it acts as a script
    and all the logic is defined at the base module level. Aka the parameters (global variables) are also
    defined at the upmost level, which means that any modifications would always be overwritten during the
    import.

    The overwrite values need to be made available during the __enter__ stage of the parent experiment
    context manager. This is the purpose of this singleton: The very same instance is available globally
    in the same runtime. The child experiment puts the values into the internal dictionary and the parent
    experiment retrieves them during __enter__.

    **THREAD-SAVE ADDRESSING**

    Before importing the parent experiment and thus effectively triggering the execution, the child
    experiment puts some values into this global data transfer object. During __enter__ the parent experiment
    will then check if data has been provided and if that is the case, use that data to overwrite it's local
    values. If we put data into the exchange object, how do we make sure that it is only accessed by the
    correct parent experiment?

    First of all, data is put into a dictionary, whose keys are the absolute file paths of the parent
    experiments. This path is known by the parent and the child experiment. This already makes sure that
    the correct type of parent experiment only receives this data. But in a multi-threading scenario where
    potentially multiple of the same parent experiment are supposed to be started in the same runtime this
    can still lead to collisions.

    For this purpose a threading lock is placed as soon as a child places the data. This lock is registered
    to the same path. New data to the same name cannot be placed in the exchange instance as long as that
    lock is not released. This entirely blocks any other parent experiments with the same name to be started
    at the same time. The lock is released as soon as the parent experiment has retrieved the data.
    """
    def __init__(self):
        # This dictionary will contain the actual data which is passed from child to parent experiment.
        # The keys are absolute string paths of the parent experiments. The values are dictionaries which
        # have to be valid experiment update dicts - aka they are going to be used as the argument to the
        # "update" method of the parent experiment instance.
        self.data: t.Dict[str, dict] = {}

        # This dictionary will contain the thread locks. The keys are the same absolute string paths of the
        # parent experiments and the values are instances of threading.Lock
        self.locks: t.Dict[str, threading.Lock] = {}

    def request(self, key: str, data: dict) -> None:
        """
        Given the absolute string path of an experiment ``key`` and a dictionary with valid update values
        for an experiment instance ``data``, this method will place this data into the internal exchange
        dictionaries, such that the next experiment which is started with the given path during the same
        runtime will receive these value and use them to update it's internal state before running the
        experiment code:

        :param str key: The absolute string path of a parent experiment for which a data overwrite is
            requested.
        :param dict data: The dictionary containing the values to be updated.

        :returns: None
        """
        if key not in self.locks:
            self.locks[key] = threading.Lock()
        self.locks[key].acquire(blocking=True)

        self.data[key] = data

    def release(self, key: str) -> None:
        """
        Given the absolute string path ``key`` of a parent experiment, this method releases the associated
        lock and deletes the corresponding data. Should be used after the data was read by the
        recipient parent experiment.

        :returns: None
        """
        self.locks[key].release()
        del self.data[key]

    def clear(self) -> None:
        """
        Completely resets the internal exchange dictionaries.

        Use only for testing purposes.

        :returns: None
        """
        self.data = {}
        self.locks = {}

    # -- Magic Methods --

    def __contains__(self, key: str):
        return key in self.data.keys()

    def __getitem__(self, item: str):
        return self.data[item]


class AbstractExperiment:
    """
    Abstract base class for the experiment context manager.
    """
    def __init__(self,
                 base_path: str,
                 namespace: str,
                 glob: dict,
                 debug: bool = False,
                 ):
        self.base_path = base_path
        self.namespace = namespace
        self.glob = glob

        # Within an experiment it is strongly encouraged to do all printing to the console via the internal
        # "e.info" method, which is actually calling this logger instance. Using a logger has the
        # advantage that additionally to printing to the console, all the printing is additionally
        # recorded within a log file inside the experiment archive folder which can be reviewed again at
        # a later point.
        self.logger: t.Optional[logging.Logger] = NULL_LOGGER

        self.data = {}
        self.meta = {}
        self.parameters = {}
        self.error: t.Optional[Exception] = None
        self.prevent_execution = False
        self.description: t.Optional[str] = None
        self.short_description: t.Optional[str] = None
        self.debug_mode: bool = debug

        self.discover_parameters()

        self.hooks: t.Dict[str, t.List[t.Callable]] = defaultdict(list)

        # After the main experiment context, there can be another context "e.analysis" and it is encouraged
        # that this context is used to define the creation of important artifacts for the analysis and
        # visualization of results.
        # The RecordCode context manager will be able to copy all the code within that context and that code
        # is then copied to the artifacts file within the archive folder.
        self.analysis = RecordCode(initial_stack_index=2)

        # ExperimentExchange is actually a singleton, which means that each invocation of the constructor
        # returns the very same object instance. This object instance is basically a global state which is
        # accessable from anywhere. It is used to exchange(!) parameters for experiment inheritance, which
        # is the case when one experiment is basically the "sub-classing" of another experiment just with
        # slight modifications to parameters for example.
        self.experiment_exchange = ExperimentExchange()

        # ~ experiment relevant paths
        self.namespace_path: t.Optional[str] = None
        self.path: t.Optional[str] = None

        # The following fields will contain the absolute string paths to some very important files within
        # the experiment's archive folder:
        self.data_path: t.Optional[str] = None
        self.meta_path: t.Optional[str] = None
        self.error_path: t.Optional[str] = None
        self.log_path: t.Optional[str] = None
        self.code_name: t.Optional[str] = None
        self.code_path: t.Optional[str] = None

        # The keys of this dictionary are unique string names and the values will be absolute string paths
        # of files or folders which have been added as a dependency for the execution of the experiment.
        # Ultimately these files and folders wil be copied into each(!) created archive folder to ensure
        # the reproducibility of the snapshots.
        self.dependency_paths: t.Dict[str, str] = {}

    def initialize_paths(self):
        """
        This method will calculate all the specific path attributes of the experiment instance from the
        current values of ``self.base_path`` and ``self.namespace``.

        :returns: None
        """
        # 02.01.2023
        # Previously the namespace was just joined to the path as a string, but that would have caused
        # problems with the usage of slashes "/" to declare sub folder structures on a non-unix system.
        # So now the "split_namespace" method takes care of that and divides the namespace string into the
        # semantic segments which can then be joined in an os-agnostic way.
        namespace_split: t.List[str] = split_namespace(self.namespace)
        self.namespace_path = os.path.join(self.base_path, *namespace_split)
        self.path = self.determine_path()

        self.data_path = os.path.join(self.path, 'experiment_data.json')
        self.meta_path = os.path.join(self.path, 'experiment_meta.json')
        self.error_path = os.path.join(self.path, 'experiment_error.txt')
        self.log_path = os.path.join(self.path, 'experiment_log.txt')

        self.code_name = 'snapshot'
        self.code_path = os.path.join(self.path, f'{self.code_name}.py')

    def update(self, other: t.Union[dict, 'AbstractExperiment']) -> None:
        """
        Given ``other`` which is a dictionary with key values pairs representing the instance
        attributes of an experiment object instance, this method will update the corresponding
        attributes of this instance with the new values from the dict.

        ``other`` may also be another AbstractExperiment instance. In that case, this instance's
        internal attributes are updated to match those of the other instance.

        :raises TypeError: if the type of the argument is not either a dict or an experiment instance

        :param other: Defines how to update the internal state.

        :returns: None
        """
        if isinstance(other, AbstractExperiment):
            other = other.to_update_dict()

        if isinstance(other, dict):
            for key, value in other.items():
                local_value = getattr(self, key)
                # If the value in question is a dictionary, we actually want to perform an update operation
                # which will mostly preserve the original dictionary content, except for the first-level
                # keys which collide - which will be replaced.
                # All other datatypes are replaced right away.
                if isinstance(local_value, dict) and isinstance(value, dict):
                    local_value.update(value)
                else:
                    setattr(self, key, value)

        else:
            raise TypeError(f'You are attempting to update the internal state of an Experiment instance '
                            f'using a value of type "{type(other)}". Please use either a dictionary '
                            f'which specifies the update values or pass another instance of '
                            f'AbstractExperiment!')

    def to_update_dict(self) -> dict:
        """
        Returns a dictionary which represents the internal state of the experiment object instance and
        which can be used as the argument to the ``update`` method of another experiment instance.

        :returns: a dictionary with string keys and Any values representing the internal fields of the
            experiment object instance.
        """
        return {
            'base_path': self.base_path,
            'namespace': self.namespace,
            'glob': self.glob,
            'data': self.data,
            'meta': self.meta,
            'parameters': self.parameters,
            'hooks': self.hooks,
            'path': self.path,
            'meta_path': self.meta_path,
            'data_path': self.data_path,
            'error_path': self.error_path,
            'log_path': self.log_path,
            'code_path': self.code_path,
            'error': self.error,
        }

    def discover_parameters(self) -> None:
        """
        This method extracts the parameters (upper case global variables) from ``self.glob`` and transfers
        them to the ``self.parameters`` dict.

        Additionally, this method detects all the *special* parameters: There are some parameter names
        which have a special meaning which will also be detected and processed appropriately. One example
        would be the global boolean flag "DEBUG" which, if detected, will be used to set the internal
        ``self.debug_mode`` attribute.

        :returns: None
        """
        for key, value in self.glob.items():
            if key.isupper():
                self.parameters[key] = value

        # ~ Detecting special parameters
        if "__doc__" in self.glob and isinstance(self.glob["__doc__"], str):
            self.data["description"] = self.glob["__doc__"]
            self.description = self.glob['__doc__']

        if "DEBUG" in self.glob and isinstance(self.glob["DEBUG"], bool):
            self.debug_mode = self.glob["DEBUG"]

        if 'DEPENDENCY_PATHS' in self.glob:
            if isinstance(self.glob['DEPENDENCY_PATHS'], dict):
                self.dependency_paths = self.glob['DEPENDENCY_PATHS']
            else:
                self.warning('it looks like you have defined "DEPENDENCY_PATH", but it is not a dictionary '
                             'please make sure that this variable is a dictionary whose keys are unique '
                             'string identifiers and the values are existing absolute string paths of '
                             'files that are required for the working of the experiment.')

        # TODO: Default short description from __doc__ first line.
        if "SHORT_DESCRIPTION" in self.glob:
            self.short_description = self.glob["SHORT_DESCRIPTION"]

    def determine_path(self) -> str:
        # ~ are we importing a snapshot file?
        # The first thing we do is to check whether this invocation of the experiment is the import of a
        # snapshot file (located in an already completed experiment archive folder) or if this is actually
        # a new experiment.

        # We determine if it is a snapshot by checking if there is an "experiment_meta.json" file in the
        # same folder (which will *always* be the case for the archival copy of an experiment module, as
        # the meta file is created during the very start of an experiment already).
        # In that case we want to return the path of that archive folder rather than create a new path!
        folder_path = pathlib.Path(self.glob['__file__']).parent.absolute()
        meta_path = os.path.join(folder_path, 'experiment_meta.json')
        # An exception to that rule is if the __name__ of the archival experiment copy is __main__ aka
        # if that file is actively being executed.
        if os.path.exists(meta_path) and self.glob['__name__'] != '__main__':
            return str(folder_path)

        # ~ resolving the namespace
        # ... otherwise, if it is a new experiment we need to determine the new record folder path that
        # will have to be created to hold all the experiment results.

        if self.debug_mode:
            return os.path.join(self.namespace_path, 'debug')

        elif not os.path.exists(self.namespace_path):
            return os.path.join(self.namespace_path, '000')

        else:
            contents = os.listdir(self.namespace_path)
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

            return os.path.join(self.namespace_path, f'{index:03d}')

    def load_records(self) -> None:
        """
        Loads the contents of the experiment's "experiment_data.json" file and updates the internal
        ``self.data`` dict with those loaded values.

        That data file must already exist for this method!

        :raises FileNotFoundError: if the data file does not yet exists, which would indicate that the
            experiment has not yet terminated.
        """
        if os.path.exists(self.data_path):
            with open(self.data_path) as json_file:
                self.data = json.load(json_file)

        else:
            raise FileNotFoundError('You are attempting to load the "experiment_data.json" file to '
                                    'populate the data dictionary of an Experiment instance, but the data '
                                    'file was not found. Please make sure that this method is only called '
                                    'for experiments that are already terminated!')

    # -- Logging --

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

    def info(self, message: str) -> None:
        """
        Logs the given ``message`` string as an "INFO" level log message.

        :param str message: The string message to be printed as a log.
        :returns: None
        """
        self.logger.info(message)

    def warning(self, message: str) -> None:
        """
        Logs the given ``message`` string as an "WARNING" level log message.

        :param str message: The string message to be printed as a log.
        :returns: None
        """
        self.logger.warning(message)

    def info_lines(self, message: str) -> None:
        """
        Logs each line of the given multiline ``message`` string as an "INFO" level log message.

        :param str message: The string message to be printed as a log
        :returns: None
        """
        lines = message.split('\n')
        for line in lines:
            self.logger.info(line)

    # -- Hook System --
    # The hook system is a new feature which is meant to enhance the capability of experiment inheritance
    # A parent experiment may certain points during the execution where custom code of child experiments
    # may be able to "hook in" and be executed. This is what "apply_hook" is used for. A hook will be
    # connected with a unique name and any number of callback functions previously connected to that name
    # using the "hook" decorator will be executed at that point.

    def apply_hook(self,
                   name: str,
                   default: t.Any = None,
                   **kwargs) -> t.Any:
        """
        This method can be used to call custom code injected from child experiments during the main context
        body of an experiment. Each hook has to be identified by a unique string ``name``.

        :param str name: A unique string name, which identifies the
        :param default: This value is returned by the method, if no callback which could have a return value
            is actually registered. This can be used to realize filter hooks.

        :returns: This function returns the value of ``default`` if no hooks with the given name have been
            registered. If multiple hooks have been registered, this function returns the return value of
            the most recent hook callback.
        """
        value = default
        for func in self.hooks[name]:
            # self.info(f'[@] run hook: "{name}" - from: "{func.file_name}.{func.__name__}"')
            value = func(self, **kwargs)
            # self.info(f'    end hook: "{name}"')

        return value

    def hook(self,
             name: str,
             replace: bool = False,
             default: bool = True,
             ) -> t.Callable[[t.Callable], t.Callable]:
        """
        This method will return a decorator, which can be used to register callbacks to certain hooks
        identified by their unique string ``name``.

        :param str name: The unique string name of the hook for which this callback should be registered.
        :param bool replace: If this flag is True, the registered callback will replace any previously
            registered callbacks for the same hook name. If False, the callback will be added to the
            back of the execution chain.
        :param bool default: If this flag is True, then the given callback will only be executed if
            otherwise no other callbacks have been registered to that hook! Effectively declaring that
            callback as the default implementation only!

        :returns: A decorator callable
        """
        # This is not strictly necessary, but here we determine the file name of the currently active
        # experiment file so that we can attach that information later on to the decorated callback function
        # That information can then be used when that callback is actually executed to make a useful
        # log message.
        if '__file__' in self.glob:
            file_name = os.path.basename(self.glob['__file__']).strip('.py')
        else:
            file_name = '__child__'  # generic name if we can't determine the experiment file name

        def decorator(func: t.Callable):
            if replace:
                self.hooks[name] = [func]
            else:
                # In the case default=True and non-empty hook list we DONT want to add the hook to the list
                # because if the default flag is given then that means that this particular callback is
                # supposed to be the default implementation only, which means that it should only be
                # executed if there are no other hooks registered yet!
                if not default or len(self.hooks[name]) == 0:
                    self.hooks[name].append(func)

            setattr(func, 'file_name', file_name)
            return func

        return decorator

    # -- Magic Methods --

    def __enter__(self):
        # As the very first thing we need to check if the invocation of this experiment is as a parent
        # experiment in an inheritance chain. This would be the case if the file path of the experiment
        # module exists as a key within the global ExperimentExchange object. Because in that case it
        # was put there by a child experiment with the intent of passing modified variables to this
        # experiment.
        # If that is the case, the globals dictionary will be updated with the new values that were passed
        # in by the child experiment.
        module_path = self.glob['__file__']
        if module_path in self.experiment_exchange:
            other: dict = self.experiment_exchange[module_path]

            # The update method updates the internal experiment state of the experiment based on a
            # dictionary.
            self.update(other)
            self.discover_parameters()

            # This method is important, because it will release the thread lock for this module so that in
            # a multi threading scenario another parent module with the same path could now be invoked.
            self.experiment_exchange.release(module_path)

        # This method actually initializes/calculates the values of all the specific experiment paths
        # based on the values "base_path" and "namespace".
        # You might be asking: "Why do it as a separate method and not directly in the constructor?"
        # The reason is that even after an experiment instance was constructed there are cases where
        # "base_path" and "name_space" might be modified and thus all the specific paths have to be
        # re-initialized. In that case it is easier to just have to call this single method.
        self.discover_parameters()
        self.initialize_paths()

        # We are going to set this magic variable in the original experiment module. This can then be
        # used to identify whether a module is actually an experiment or not
        self.glob['__experiment__'] = self

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
            # and an artifacts folder already exists. This method will load all the experiment data,
            # which is saved as a JSON file in that folder back into this object, so that even if this
            # object is only imported we can still interact with it as if it was just at the end of the
            # experiment execution!
            if os.path.exists(self.data_path):
                self.load_records()

            # 20.01.2023
            # In analysis mode, we are going to use the dependency paths dict which was saved into the
            # meta data of the current archive folder. This will make sure that we are now using the
            # locally copied versions of these dependencies
            if 'dependency_paths' in self.meta:
                self.dependency_paths = self.meta['dependency_paths']

            # This exception will be caught by the "Skippable" context manager which always has to precede
            # the experiment manager, effectively skipping the entire context body!
            raise SkipExecution()

        # This is a special hook which can be used to inject code before the execution of any main
        # experiment code.
        self.apply_hook('__enter__')

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # This is a special hook which can be used to inject code after any experiment exits the main
        # context.
        self.apply_hook('__exit__')

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


class Experiment(AbstractExperiment):
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
        super(Experiment, self).__init__(
            base_path=base_path,
            namespace=namespace,
            glob=glob,
        )
        self.debug_mode = debug_mode
        self.work_tracker_class = work_tracker_class
        self.templates = templates

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
        super(Experiment, self).__enter__()
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

        # ~ Copying the file dependencies into the archive folder
        # At the very end, we copy all the artifact dependencies (could be files but also folders) into the
        # archive folder of the current experiment run. The purpose of those "dependency" files is the
        # reproducibility of the "snapshot" within that archive folder. These files are potentially files
        # which are needed by the folder.
        self.meta['dependency_paths'] = {}
        for name, dependency_path in self.dependency_paths.items():
            if not os.path.exists(dependency_path):
                raise FileNotFoundError(f'You have specified "{name}"("{dependency_path}") '
                                        f'as a dependency for the experiment. '
                                        f'That path does not exist! Please make sure that the '
                                        f'path exists so it can be copied into the archive folder!')

            file_name = os.path.basename(dependency_path)
            destination_path = os.path.join(self.path, file_name)

            if os.path.isfile(dependency_path):
                shutil.copy(dependency_path, destination_path)
            elif os.path.isdir(dependency_path):
                shutil.copytree(dependency_path, destination_path)

            self.meta['dependency_paths'][name] = destination_path

        # ~ Creating meta file
        self.meta['running'] = True
        self.meta['start_time'] = start_time
        self.status(log=False)
        self.save_experiment_meta()

        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        super(Experiment, self).__exit__(exc_type, exc_value, exc_tb)

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

    def save_experiment_meta(self) -> None:
        """
        Saves the internal experiment metadata dictionary into as a json file with the already
        pre-determined path ``self.meta_path``

        :returns: None
        """
        with open(self.meta_path, mode="w") as json_file:
            json.dump(self.meta, json_file, cls=CustomJsonEncoder)

    def save_experiment_data(self) -> None:
        """
        Saves the internal experiment data dictionary as a JSON file with the already pre-determined path
        ``self.data_path``.

        :returns: None
        """
        with open(self.data_path, mode="w") as json_file:
            # 28.11.2022: Using a custom encoder now to prevent an error when numpy arrays are added to the
            # internal data storage. This encoder will convert them to plain lists before json
            # serialization.
            json.dump(self.data, json_file, cls=CustomJsonEncoder)

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


class SubExperiment(AbstractExperiment):

    def __init__(self,
                 experiment_path: str,
                 base_path: str,
                 namespace: str,
                 glob: dict,
                 inherit_namespace: bool = False,
                 ):
        super(SubExperiment, self).__init__(
            base_path=base_path,
            namespace=namespace,
            glob=glob,
        )
        self.inherit_namespace = inherit_namespace
        self.experiment_exchange = ExperimentExchange()

        self.experiment_path = experiment_path
        self.experiment_name = os.path.basename(experiment_path)

        self.prevent_execution = True

    def __enter__(self):
        return super(SubExperiment, self).__enter__()
        pass

    def get_clean_glob(self):
        cleaned = {}
        for key, value in self.glob.items():
            if key == '__name__' or key.isupper():
                cleaned[key] = value

        return cleaned

    def __exit__(self, exc_type, exc_val, exc_tb):
        super(SubExperiment, self).__exit__(exc_type, exc_val, exc_tb)

        # 20.01.2023
        # If the given experiment path does not exist, then we are first going to search for the base
        # experiment in the current archive folder (It would be found there, if we are in fact currently
        # executing the snapshot of an experiment from an archive folder!). If it is not found there
        # either we produce a helpful error message.
        if not os.path.exists(self.experiment_path):
            experiment_path = self.experiment_path
            self.experiment_path = os.path.join(self.path, self.experiment_name)

            if not os.path.exists(self.experiment_path):
                raise FileNotFoundError(f'The base experiment "{self.experiment_name}" defined for this '
                                        f'sub experiment could not be found at the provided location '
                                        f'{experiment_path}! Please make sure to provide a valid path to '
                                        f'an existing base experiment module!')

        data = {
            'glob': self.get_clean_glob(),
            'hooks': self.hooks,
        }
        # If the flag "inherit_namespace" is set then we want to execute the parent experiment with the
        # original namespace and base path instead of using the one defined for the sub experiment.
        if not self.inherit_namespace:
            data['base_path'] = self.base_path
            data['namespace'] = self.namespace

        # This method will place the local dict "data" which contains the updated experiment information
        # into the global experiment data exchange object keyed with the name of the experiment module's
        # path, so that the parent experiment can access that data during it's __enter__ operation.
        self.experiment_exchange.request(self.experiment_path, data=data)

        spec = importlib.util.spec_from_file_location('experiment', self.experiment_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # At experiment __enter__ EVERY experiment will save a reference to itself into it own module's
        # global variable called __experiment__. We access the experiment like that and use it to update
        # our own internal state. This essentially accomplishes the magic that after the context manager
        # exits the SubExperiment essentially has the same content as if it was the parent experiment which
        # was just executed.
        experiment = getattr(module, '__experiment__')
        self.update(experiment)

        # 20.01.2023
        # This fixes the issue where the snapshot of a sub experiment is not in fact executable, because
        # the base experiment upon which it extends does not exist in the same folder. So here we copy that
        # base experiment into the same folder as well!
        destination_path = os.path.join(self.path, self.experiment_name)
        shutil.copy(self.experiment_path, destination_path)


def run_experiment(experiment_path: str,
                   parameters: dict = {}
                   ) -> AbstractExperiment:
    """

    """
    glob = {
        # We need this to make sure that the experiment actually executes.
        '__name__': '__main__',
        '__file__': experiment_path,
        # overwriting the default parameters from the original experiment file (optionally)
        **parameters
    }

    se = SubExperiment(
        experiment_path=experiment_path,
        glob=glob,
        # With this configuration, the original base path and namespace from the file itself will be used.
        base_path='',
        namespace='',
        inherit_namespace=True,
    )
    with se:
        pass

    return se


def run_example(example_name: str,
                parameters: dict = {},
                ) -> AbstractExperiment:
    """

    """
    example_path = os.path.join(EXAMPLES_PATH, example_name)
    return run_experiment(
        experiment_path=example_path,
        parameters=parameters,
    )


# == EXPERIMENT REGISTRY ====================================================================================


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

