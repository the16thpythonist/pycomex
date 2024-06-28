import os
import re
import shutil
import sys
import time
import json
import inspect
import traceback
import typing as t
import logging
import datetime
import textwrap
import importlib.util
from collections import defaultdict

from pycomex.utils import random_string, dynamic_import
from pycomex.utils import TEMPLATE_ENV
from pycomex.utils import CustomJsonEncoder
from pycomex.utils import get_comments_from_module
from pycomex.utils import parse_parameter_info, parse_hook_info
from pycomex.utils import type_string
from pycomex.utils import trigger_notification
from pycomex.config import Config

HELLO: str = ''


class Experiment:
    """
    Functional Experiment Implementation. This class acts as a decorator.
    """

    def __init__(self,
                 base_path: str,
                 namespace: str,
                 glob: dict,
                 debug: bool = False,
                 name_format: str = '{date}__{time}__{id}',
                 notify: bool = True,
                 ) -> None:
        
        self.base_path = base_path
        self.namespace = namespace
        self.glob = glob
        self.debug = debug
        self.name_format = name_format
        self.notify = notify
        
        # 26.06.24
        # The config object is a singleton object which is used to store all the configuration information
        # of pycomex in general. Most importantly, the config singleton stores the reference to the plugin 
        # manager "pm" that will be used throughout the experiment lifetime to create entry points to extend 
        # it's functionality.
        self.config = Config()

        # ~ setting up logging
        self.log_formatter = logging.Formatter('%(asctime)s - %(message)s')
        stream_handler = logging.StreamHandler(sys.stdout)
        self.logger = logging.Logger(name='experiment', level=logging.DEBUG)
        self.logger.addHandler(stream_handler)

        # After the experiment was properly initialized, this will hold the absolute string path to the *archive*
        # folder of the current experiment execution!
        self.path: t.Optional[str] = None
        
        # 08.11.23
        # Optionally it is possible to define a specific name before the experiment is started and then 
        # the experiment archive will be created with that custom name. In the default case (if this stays None)
        # the name will be generated according to some pattern
        self.name: t.Optional[str] = None
        
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
            'parameters': {},
            'hooks': {},
        }
        self.error = None
        self.tb = None
        
        # 27.10.23
        # This boolean flag indicates whether the experiment is currently actually being executed or whether one is 
        # just dealing with a stored version of the experiment. It will be set to True only right before the actual 
        # function implementation of the experiment is executed.
        self.is_running: bool = False
        # 27.10.23
        # This boolean flag indicates whether the experiment is currently in the testing mode. This flag is only 
        # set to True after the testing hook function implementation was already executed.
        self.is_testing: bool = False

        # This list will contain the absolute string paths to all the python module files, which this
        # experiment depends on (for example in the case that this experiment is a sub experiment that was
        # created with the "extend" constructor)
        self.dependencies: t.List[str] = []

        self.analyses: t.List[t.Callable] = []
        self.hook_map: t.Dict[str, t.List[t.Callable]] = defaultdict(list)

        # This method here actually "discovers" all the parameters (=global variables) of the experiment module.
        # It essentially iterates through all the global variables of the given experiment module and then if it finds 
        # a parameter (CAPS) it inserts it into the "self.parameters" dictionary of this object.
        self.update_parameters()
        
        # 27.10.23
        # This method will extract other metadata from the source experiment module. This metadata for example includes 
        # a description of the experiment (the doc string of the experiment module).
        # Only after this method has been called, will those properties of the "self.metadata" dict actually contain 
        # the appropriate values.
        self.read_module_metadata()

        # Here we do a bit of a trick, we insert a special value into the global dictionary of the source experiment 
        # dict wich contains a reference to the experiment object itself. This will later make it a lot easier when we 
        # import an experiment module to actually get the experiment object instance from it, because we can't guarantee 
        # what variable name the user will actually give it, but this we can assume to always be there.
        self.glob['__experiment__'] = self
        
        # This hook can be used to inject additional functionality at the end of the experiment constructor.
        self.config.pm.apply_hook(
            'experiment_constructed', 
            experiment=self,
        )

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
        
    # ~ Module Metadata

    def read_module_metadata(self):
        """
        This method extract certain information of the original experiment module and saves them as the appropriate 
        metadata for the experiment object.
        This information includes for example the module doc string of the experiment module which will be attached as 
        the "description" of the experiment.
    
        :returns: None
        """
        # ~ the experiment name
        # We simply use the name of the python experiment module as the name of the experiment as well!
        name = os.path.basename(self.glob['__file__']).split('.')[0]
        self.metadata['name'] = name
        
        # ~ the experiment description
        # We simply say that the docstring of the module is the experiment description.
        
        doc_string = self.glob['__doc__']
        doc_string = '' if doc_string is None else doc_string
        description = doc_string.lstrip(' \n')
        self.metadata['description'] = description
        short_description = doc_string.split('\n\n')[0]
        short_description = textwrap.shorten(short_description, width=600)
        self.metadata['short_description'] = short_description

        # ~ the experiment parameters
        # We also importantly want to automatically extract some additionional information about the 
        
        # At the point that this method is usually executed, we can already expect that the experiment parameters 
        # were discovered and saved into the self.parameters dictionary.
        # So now we iterate through this dictionary and then.
        for parameter, value in self.parameters.items():
            if parameter not in self.metadata['parameters']: 
                self.metadata['parameters'][parameter] = {
                    'name': parameter,
                }
        
        # Here we get the type annotations.
        # This also needs some additional justification, becasue the observant reader will question why we do not 
        # just use the __annotations__ property of the glob dictionary of the experiment module here. The problem 
        # is that we want to get the annotations of the same file before that file is fully loaded by importlib!
        # Which means that in most cases, the __annotations__ dict will not have been created yet!
        # But using inspect like this works, although we have to do a bit of a hack with the frame. I think that we 
        # can be sure that the frame twice on top from this point on is always experiment module itself.        
        frame = inspect.currentframe().f_back.f_back
        module = inspect.getmodule(frame)
        annotations = inspect.get_annotations(module)

        for parameter, type_instance in annotations.items():
            if parameter in self.parameters:
                self.metadata['parameters'][parameter]['type'] = type_string(type_instance)
        
        module_path = self.glob['__file__']
        comment_lines = get_comments_from_module(module_path)
        comment_string = '\n'.join([line.lstrip('#') for line in comment_lines])
        parameter_info: t.Dict[str, str] = parse_parameter_info(comment_string)
        for parameter, description in parameter_info.items():
            if parameter in self.parameters:
                self.metadata['parameters'][parameter]['description'] = description
                
        # The experiment hooks
        # We also want to save information about all the available hooks in the metadata dictionary 
        
        # The most basic information that we can gather about the hooks is which hooks are even available 
        # at all. This information is directly accessible over the main hook dictionary.
        for hook, func_list in self.hook_map.items():
            if hook not in self.metadata['hooks']:
                self.metadata['hooks'][hook] = {
                    'name': hook,
                    'num': len(func_list),
                }
            
        # Then we can do something similar to the parameters, where we parse all the comments inside the 
        # experiment module and check if there is the special hook description syntax somewhere.
        hook_info: t.Dict[str, str] = parse_hook_info(comment_string)
        for hook, description in hook_info.items():
            if hook not in self.metadata['hooks']:
                self.metadata['hooks'][hook] = {
                    'name': hook,
                }
                
            self.metadata['hooks'][hook]['description'] = description
            
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
        """
        This method can be used to register functions as hook candidates for the experiment object to use 
        whenver the corresponding call of the "apply_hook" method is issued with a matching string identifier.
        """
        def decorator(func, *args, **kwargs):
            # 07.05.23 - The default flag should only be used for any default implementations used within the 
            # base experiment file or in any case were the hook is defined for the first time. When that flag 
            # is active it will only be used as a fallback option if sub experiment hasn't provided any more 
            # relevant implementation.
            if default and name in self.hook_map:
                return

            if replace:
                self.hook_map[name] = [func]
            else:
                # We need to PREPEND the function here because we are actually building the hooks up backwards 
                # through the inheritance hierarchy. So the prepending here is actually needed to make it work 
                # in the way that a user would intuitively expect.
                self.hook_map[name] = self.hook_map[name] + [func]

        return decorator

    def apply_hook(self, name: str, default: t.Optional[t.Any] = None, **kwargs):
        result = default

        if name in self.hook_map:
            for func in self.hook_map[name]:
                result = func(self, **kwargs)

        return result
    
    # ~ Testing functionality
    # The "testing" functionality refers to a feature of the Experiment object whereby it can be put into the 
    # "testing" mode by setting the magic parameter __TESTING__ to True. In this testing mode special hooks will 
    # be executed that modify the experiment parameters in a way that results in a minimal runtime of the experiment 
    # which only serves the purpose of testing if all the code actually runs without exceptions.
    
    # 27.10.23 - this method is a decorator which can be used to define the special testing hooks. Within these 
    # testing hook implementations we implement the parameter changes that are applied to the model if 
    def testing(self, func: t.Callable) -> t.Callable:
        """
        This method can be used as a decorator for a function within an experiment module. The decorated function will then 
        be subsequently used as the implementation of how to put the experiment itself into testing mode. So when the experiment 
        is actually put into testing mode via __TESTING__, that code will be executed to modify the parameters and whatever 
        else is required for it.
        
        :returns: None
        """
        # We dont need to check anything here because by design the testing implementation should always be overriding.
        # In each highest instance in the hierarchy of sub experiments should it be possible to define distinct 
        # testing behavior that is not implicitly modified or dependent on the lower levels.
        self.hook_map['__TESTING__'] = func
        
        # This requires a bit more explanation because it gets a bit convoluted here. We actually immediately *try* to
        # execute the testing immediately after adding the function at the point where the decoration happens. 
        # We need this because of the way that the testing function will most likely be defined in BASE experiment
        # modules - that is INSIDE the experiment function. At that point the experiment has already started and 
        # if we dont execute it right then, there's no idiomatic way to do so at a later point.
        # Although this isn't a big problem because this function will actually check various conditions to make sure 
        # that we are not actually executing the testing function for example when defining the testing hook in a child 
        # experiment or when merely importing an experiment from another file.
        self.apply_testing_if_possible()
        
        return func
    
    def apply_testing_if_possible(self):
        """
        This will execute the function which has been provided to the experiment as an implementation of the testing
        function, IF a certain set of conditions is satisfied.

        These are the conditions under which the testing code will be executed:
        
        - The experiment is actually configured to run in testing mode by the magic parameter __TESTING__
        - The experiment has been provided with a function that can be executed for the testing mode
        - The experiment is actually currently being executed as indicated by the is_running flag
        - The experiment is not already in testing mode
        
        :returns: None
        """
        # "applying" the test mode means to actually execute the function that is currently saved as the "testing" 
        # hook. However, we only actually execute that in case a very specific set of conditions is met:
        # - the experiment needs to be already running.
        # - the testing hasn't been applied before
        # - the experiment is not currently in it's loaded form
        # - there actually exists a test to be executed
        
        # First and most important criterium: Is the experiment even configured to testing mode?
        # This is indicated with the magic parameter __TESTING__
        if '__TESTING__' not in self.parameters or not self.parameters['__TESTING__']:
            return
        
        # Is there actually a test hook impementation that could be executed?
        # This is implemented as the special __TESTING__ name for a hook
        if '__TESTING__' not in self.hook_map:
            return
        
        # Also if the experiment is not actually in execution mode we are not running the test either
        if not self.is_running:
            return
        
        # And finally, if the testing has already been applied then we also dont't do it
        if self.is_testing:
            return
        
        # Only after all these conditions have been checked do we actually execute the testing hook 
        # implementation here.
        self.apply_hook('before_testing')
        func = self.hook_map['__TESTING__']
        func(self)
        
        self.is_testing = True

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

    def initialize(self) -> None:
        """
        This method handles all the initial preparations that are needed to set up the 
        experiment before any of the custom code can be implemented. This for example 
        includes the creation of the archive folder, the initilization of the Logger 
        instance and the copying of the original code into the archive folder. The method 
        will also set up all the necessary metadata such as the start time of the experiment.
        
        :returns: None
        """
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

    def finalize(self) -> None:
        """
        This method is called at the very end of the experiment.
        This method will for example save the final experiment metadata and main experiment 
        object storage to the corresponding JSON files in the archive folder. It will print 
        the final log messages and system notification to inform the user about the end of 
        the experiment.
        """
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
        
        # ~ trigger system notification
        # 03.06.24 - After the experiment is done, we might want to send a system notification to 
        # the user which informs them that the experiment is done. This is especially useful in the case
        # that the experiment was running for a long time and the user might have forgotten about it.
        if self.notify:
            duration_hours = self.metadata['duration'] / 3600
            message = (
                f'Experiment "{self.name}" is done after {duration_hours:.1f} hours!\n'
                f'Error: {self.error}'
            )
            trigger_notification(message)

    def execute(self) -> None:
        """
        This method actually executes ALL of the necessary functionality of the experiment.
        This inludes the initialization of the experiment, the execution of the custom experiment 
        implementation and the finalization of the experiment artifacts.
        
        :returns: None
        """
        self.initialize()
        
        self.config.pm.apply_hook(
            'after_experiment_initialize',
            experiment=self,
        )

        try:
            # This flag will be used at various other places to check whether a given experiment object is 
            # currently actually in the process of executing or whether it is rather a 
            self.is_running = True
            # Right before we actually start the main execution code of the 
            self.apply_testing_if_possible()
            
            # 27.10.23 - Added the "before_execute" and the "after_execute" hook because they might be useful 
            # in the future.
            self.apply_hook('before_run')
            self.func(self)  # This is where the actual user defined experiment code gets executed!
            self.apply_hook('after_run')
            
        except Exception as error:
            self.error = error
            self.tb = traceback.format_exc()

        self.finalize()
        
        self.config.pm.apply_hook(
            'after_experiment_finalize',
            experiment=self,
        )

    def __call__(self, func, *args, **kwargs):
        self.func = func

        return self
    
    def set_main(self) -> None:
        """
        Will modify the internal dictionary in such a way that after this method was called, 
        "is_main" will evaluate as True.
        
        :returns: None
        """
        self.glob['__name__'] = '__main__'

    def is_main(self) -> bool:
        """
        Returns True only if the current global context is "__main__" which is only the case if the python 
        module is directly being executed rather than being imported for example.
        
        :returns: bool
        """
        return self.glob['__name__'] == '__main__'

    def run_if_main(self):
        """
        This method will actually execute the main implementation of the experiment, but only if the current 
        global context is the __main__ context. That is only true if the corresponding python module is actually 
        being executed rather than imported.
        
        This is the method that any experiment method should be using at the very end of the module. A user should 
        NOT use execute() directly, as that would issue the experiment to be executed in the case of an import as well!
        
        .. code-block:: python
        
            # Define the experiment...
            
            # At the end of the experiment module
            experiment.run_if_main()
        
        :returns: None
        """
        if self.is_main():
            self.execute()
            self.execute_analyses()
            
    def run(self):
        """
        unlike, the method "run_if_main", this method will actually execute the experiment no matter what. At the point 
        at which this method is called, the experiment will be executed
        """
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
        # 04.07.2023 - This is one of those super weird bugs. Previously the path of the code file was just 
        # "code.py", but this naming has actually resulted in a bug - namely that it was not possible to 
        # use tensorflow any longer from either within that code file or the analysis file within an experiment 
        # archive folder. This is because tensorflow is doing some very weird dynamic shenanigans where at some 
        # point they execute the line "import code" which then referenced to our python module causing a 
        # circular import and thus an error!
        return os.path.join(str(self.path), 'experiment_code.py')

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
        """
        This method will for one thing create the actual path to the archive folder of the current expriment. This 
        means that it will combine the information about the base path, the namespace and the name of the experiment 
        to create the actual absolute path at which the archive folder should exist.
        
        Additionally, this method will also CREATE that folder (hierarchy) if it does not already exist. So potentially 
        this method will actually create multiple nested folders on the system.
        
        :returns: None
        """
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

        # 08.11.23
        # Now at this point we can be sure that the base path exists and we can create the specific
        # archive folder. 
        # How this archive folder will be called depends on some conditions.
        # - Most importantly, if the experiment was given an actual name (self.name != None) then 
        #   we want to use that name, otherwise the name will be auto generated
        # - The next best option would be if the experiment is in debug mode, we will call the 
        #   resulting folder "debug"
        # - In the last case we generate a name from the current datetime combined with a random
        #   string to make it unique.
        
        if self.name is not None:
            pass
        
        elif self.debug:
            self.name = 'debug'
            
        else:
            # This method will format the full name of the experiment which includes not only the 
            # name of the experiment but also the date and time information about the starting 
            # time.
            self.name = self.format_full_name()
            
        # Now that we have decided on the name we can assemble the full path
        self.path = os.path.join(current_path, self.name)
        
        # If the experiment is in "debug" mode that means that we actually want to get rid of the previous 
        # archive folder with the same name, it one exists
        if self.debug and os.path.exists(self.path):
            shutil.rmtree(self.path)

        # And then finally in any case we create a new and clean folder
        os.mkdir(self.path)

    def format_full_name(self, date_time: datetime.datetime = datetime.datetime.now()) -> str:
        """
        Given a datetime object ``data_time``, this function will format the "full" experiment name 
        which does not only include the name of the experiment but also the time and date specificied 
        by the datetime as well as a random ID string.
        
        This full name is therefore guaranteed to be unique for each experiment execution.
        
        :param date_time: the datetime object which specifies the time and date that should be included
            in the experiment name. Default is now()
        
        :returns: the string name
        """
        date_string = date_time.strftime('%d_%m_%Y')
        time_string = date_time.strftime('%H_%M')
        id_string = random_string(length=4)
        name = self.name_format.format(
            date=date_string,
            time=time_string,
            id=id_string,
        )
        return name

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
        
        self.config.pm.apply_hook(
            'experiment_commit_fig',
            experiment=self,
            name=file_name,
            figure=fig,   
        )

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
            
        self.config.pm.apply_hook(
            'experiment_commit_json',
            experiment=self,
            name=file_name,
            data=data,
            content=content,
        )

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
            
        self.config.pm.apply_hook(
            'experiment_commit_raw',
            experiment=self,
            name=file_name,
            content=content,
        )

    def track(self, name: str, value: float) -> None:
        """
        This method can be used to track a specific value within the experiment object. This is useful for example
        to keep track of the current state of a model during training or to save the results of a specific
        computation.

        :param name: The name under which the value should be saved
        :param value: The value to be saved

        :returns: None
        """
        if name not in self.data:
            self[name] = []
            
        self[name].append(value)
        
        self.config.pm.apply_hook(
            'experiment_track',
            experiment=self,
            name=name,
            value=value,
        )
        
    def track_many(self, data: dict[str, float]) -> None:
        """
        This method can be used to track multiple values at once. The data should be a dictionary where the keys
        are the names under which the values should be saved and the values are the values to be saved.
        
        :param data: A dictionary where the keys are the names and the values are the values to be saved
        
        :returns: None
        """
        for key, value in data.items():
            self.track(key, value)

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
        
        # 30.10.23 - This method will read all the metadata from the thingy
        experiment.read_module_metadata()

        # This line is necessary so that the experiments can be discovered by the CLI
        glob['__experiment__'] = experiment

        return experiment

    @classmethod
    def load(cls, path: str):
        module = dynamic_import(path)
        
        # 28.04.23 - before this was implemented over a hardcoded variable name for an experiment, but
        # strictly speaking we can't assume that the experiment instance will always be called the same
        # this is just a soft suggestion.
        experiment = None
        for key in dir(module):
            value = getattr(module, key)
            if isinstance(value, Experiment):
                experiment = value

        folder_path = os.path.dirname(path)
        experiment.path = folder_path

        with open(experiment.metadata_path) as file:
            content = file.read()
            experiment.metadata = json.loads(content)

        with open(experiment.data_path) as file:
            content = file.read()
            experiment.data = json.loads(content)

        return experiment


def find_experiment_in_module(module: t.Any) -> Experiment: 
    """
    Given an imported module object, this function will return the *first* experiment object that is encountered to be 
    known to the global scope of the given module.
    
    :returns: An Experiment object
    """
    if '__experiment__' in dir(module):
        experiment = getattr(module, '__experiment__')
        return experiment
    else: 
        raise ModuleNotFoundError(f'You are attempting to get the experiment from the module {module.__name__}. '
                                  f'However, it seems like there is no Experiment object defined in that module!')



def get_experiment(path: str) -> None:
    
    module = dynamic_import(path)
    experiment = find_experiment_in_module(module)
    return experiment


def run_experiment(path: str) -> None:
    """
    This function runs an experiment given the absolute path to the experiment module.
    
    :param path: The absolute string path to a valid experiment python module
    
    :returns: None
    """
    # This is a handy utilitiy function which just generically imports a python module given its absolute path in
    # the file system.
    module = dynamic_import(path)
    
    # This function will actually return the (first) Experiment object instance that is encountered to be defined 
    # within the given module object.
    # It will raise an error if there is none.
    experiment = find_experiment_in_module(module)
    
    # And now finally we can just execute that experiment.
    experiment.set_main()
    experiment.run_if_main()
    
    return experiment