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

from pycomex import SubExperiment, Experiment, Skippable, file_namespace, folder_path

# (1) One of the major features of experiment inheritance is the possibility
#     to overwrite the global parameters (upper case variables in global scope)
#     easily.
#     By just assigning new values with the same variable names here, these
#     values will automatically be injected into the runtime of the parent
#     experiment and the experiment will execute with these values instead!
NUM_WORDS = 500

# (2) A sub experiment can be created by using the "extend" class method.
#     The first parameter will have to be either an absolute or a relative
#     path to another, existing, experiment module that will be used as
#     the basis
experiment = Experiment.extend(
    "03_analysing.py",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

# (3) Sub experiment implementation rely on so-called hooks. In the base experiment
#     module that is being extended there have to be "apply_hook" statements, which
#     act as entry points where subsequent sub-experiments can inject their own
#     functionality.
#     hooks implementations can be created with just normal functions that are
#     decorated with the "hook" method of the experiment and the string name
#     given to that decorator defines the hook to be implemented.

# NOTE: The first argument of every hook function is always the experiment instance e
#       of the parent experiment!
#       after that, the names of additional parameters, if there are any at all, depend
#       on how the individual hooks were set up in the parent experiment.


@experiment.hook("filter_words")
def remove_random_words(e, words):
    e.log("removing 10 random words")
    indices = list(range(len(words)))
    remove_indices = random.sample(indices, k=10)
    for index in remove_indices:
        words.pop(index)

    # Since the name indicates that this is a filter hook, we need to return the new
    # value of the words variable.
    return words


@experiment.hook("after_experiment")
def after_experiment(e):
    e.log("We can even use the logging here!")

    # We can simply access all the parameters which have been defined in either
    # beginnings of the experiment modules simply through the main experiment
    # instance "e"
    e.log(f"Number of repetitions done: {e.REPETITIONS}")

    # And we can assign / modify the contents of the experiment data store
    e["message"] = "hello from sub experiment!"


# (4) Analysis extensions:
#     We can even define an analysis section for sub experiments as well. These are additive,
#     which means that the analysis of a sub experiment is run after the analysis of the
#     parent experiment and that is even the case for the code that is copied to the analysis.py
#     file! The code which is copied there is a concatenation of all the individual analysis
#     code snippets in the order in which they are executed.
@experiment.analysis
def analysis(e):
    # We can also add additional analysis in the sub experiments!
    e.log("hello from sub experiment analysis!")


experiment.run_if_main()
