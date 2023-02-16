"""
This example illustrates how to use experiment inheritance.

This refers to the concept of defining a "child experiment" which inherits
most of its main functionality from another "parent experiment",
but is able to override the global parameters and inject custom
code using a hook system.

This feature is realized through the "SubExperiment" class which acts the
same as a regular experiment for most cases, but takes another argument
which is the absolute string path to the parent experiment module, which
will then be executed.
"""
import os
import pathlib
import random
import tempfile
from pycomex.experiment import SubExperiment
from pycomex.util import Skippable

# (1) One of the major features of experiment inheritance is the possibility
#     to overwrite the global parameters (upper case variables in global scope)
#     easily.
#     By just assigning new values with the same variable names here, these
#     values will automatically be injected into the runtime of the parent
#     experiment and the experiment will execute with these values instead!
NUM_WORDS = 500

# SubExperiment requires one additional positional argument, which is the
# absolute string path to the experiment module which is to be used as
# the parent experiment - this module will then actually be executed.
PATH = pathlib.Path(__file__).parent.absolute()
PARENT_PATH = os.path.join(PATH, 'analysing.py')
# Other than that, SubExperiment takes the same arguments as regular ones.
# These values here will actually overwrite the configuration in the parent
# experiment
BASE_PATH = os.getcwd()
NAMESPACE = 'example/inheritance'
DEBUG = True
with Skippable(), (se := SubExperiment(PARENT_PATH, BASE_PATH, NAMESPACE, glob=globals())):
    # (2) The body of a SubExperiment works a bit differently than a regular experiment.
    #     The actual experiment code from the parent experiment is only executed when
    #     this context here EXITS.
    #     This context body can be used to define HOOKS. By defining functions with the
    #     special "hook" decorator it is possible to inject the code within the content
    #     of these functions to those places where the hooks with the corresponding
    #     names are called within the parent experiment.

    # NOTE: The first argument of every hook is always the experiment instance of the
    #       parent experiment!
    #       after that the names of additional parameters, if there are any at all, depend
    #       on how the individual hooks were set up in the parent experiment.

    @se.hook('filter_words')
    def remove_random_words(e, words):
        e.info('removing 10 random words')
        indices = list(range(len(words)))
        remove_indices = random.sample(indices, k=10)
        for index in remove_indices:
            words.pop(index)

        # Since the name indicates that this is a filter hook, we need to return the new
        # value of the words variable.
        return words

    # (3) Parameter Hooks:
    #     Besides the user-defined custom hooks, there are also default hooks which can be registered. For
    #     example it is possible to register a hook for every experiment "parameter" (upper-case global
    #     variables) from the parent experiment.
    #     These hooks are filter hooks, which means as their only argument "value" they receive the original
    #     value of that parameter defined in the parent experiment. This provides the possibility to
    #     *modify* these values instead of straight-up overwriting them...

    @se.hook('REPETITIONS')
    def repetitions(e, value):
        """
        This hook for example modifies the REPETITIONS parameter to use only half of the originally defined
        value, whatever that was defined as in the parent experiment.
        """
        print(e.p['REPETITIONS'])
        return int(value / 2)

    # This is another example of a hook available by default. This hook will be executed at the very end
    # of the experiment. This can be useful when additional functionality should be added to the end of
    # an existing parent experiment!
    @se.hook('after_experiment')
    def after_experiment(e):
        e.info('We can even use the logging here!')
        e.info(f'For example we can print the value of the REPETITIONS parameter: {e.p["REPETITIONS"]}')
        e.info('The original value was 10, but remember that we modified this with a parameter hook!')

        # And we can assign / modify the contents of the experiment data store
        e['message'] = 'hello from sub experiment!'


# (4) Analysis extensions:
#     We can even define an analysis section for sub experiments as well. These are additive, which means
#     that the analysis of a sub experiment is run after the analysis of the parent experiment and that
#     is even the case for the code that is copied to the analysis.py file!
#     The code which is copied there is a concatenation of all the individual analysis code snippets in the
#     order in which they are executed.
with Skippable(), se.analysis:

    # We can also add additional analysis in the sub experiments!
    se.info('hello from sub experiment')

