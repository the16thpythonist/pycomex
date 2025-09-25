"""
test experiment module - Extended from 04_inheritance

Extended experiment based on 04_inheritance

This module extends the base experiment "04_inheritance" by inheriting all its parameters
and hooks. You can modify parameters and implement hook stubs as needed.

This module-level doc string will automatically be saved as the description
for this experiment.
"""

import os
import tempfile
from typing import *

from pycomex import Experiment, file_namespace, folder_path

# == INHERITED PARAMETERS ==
# The following parameters are inherited from the base experiment.
# You can modify their values as needed or add new parameters.


# :param NUM_WORDS:
#       This is the number of words to be generated each time
NUM_WORDS: Optional[int, NoneType] = 500


# :param REPETITIONS:
#       The number of independent repetitions of the experiment
REPETITIONS: int = 10


__DEBUG__: bool = True

# Extend the base experiment
experiment = Experiment.extend(
    experiment_path="04_inheritance.py",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

# == HOOK IMPLEMENTATIONS ==
# The following hooks are available from the base experiment.


@experiment.hook("filter_words", default=False, replace=True)
def filter_words(e, words):
    """
    This is a filter hook, to be applied on a list of words and may modify that list of  words in any way. It has to return the modified list of words and nothing else.
    """
    e.log("executing filter_words hook in extended experiment")
    # Your implementation here
    return


@experiment.hook("after_experiment", default=False, replace=True)
def after_experiment(e):
    """
    Hook inherited from base experiment
    """
    e.log("executing after_experiment hook in extended experiment")
    # Your implementation here
    return


experiment.run_if_main()
