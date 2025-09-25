"""
Based on the functionality introduced in the previous example, we can take the whole idea one 
step further with so-called "meta experiments". These are experiment modules themselves but their 
implementation essentially relies on the execution of various other experiment modules as part 
of it's own runtime.

**DIFFERENCE TO EXPERIMENT INHERITANCE**

Meta experiments are a slightly different use case than experiment inheritance. In experiment 
inheritance, the focus is rather on somehow substantially modifying the behavior of the original 
base experiment and extending it in some way. Most crucially, the experiment itself stays the 
top most abstraction layer and it is executed at most once during the same runtime.

With meta experiments, the idea is to facilitate the execution of multiple experiments as part 
of a larger experiment that kind of compiles the results of these sub experiments in some sense.

The most obvious use case of meta experiments is to easily perform some kind of ablation studies or 
parameter sweeps. It is possible to modify the parameters of these experiements before executing 
them. In that way one could define a loop in which one (or many) parameters of another experiment 
are iteratively systematically changed.
"""

import os
import pathlib
import typing as t

from pycomex import Experiment, get_experiment, file_namespace, folder_path, random_string

PATH = pathlib.Path(__file__).parent.absolute()

# :param REPETITIONS:
#       pass
REPETITIONS: int = 3

# :param NUM_WORDS_SWEEP:
#       pass
NUM_WORDS_SWEEP: list[int] = [10, 100, 1000]


@Experiment(
    base_path=folder_path(__file__), namespace=file_namespace(__file__), glob=globals()
)
def experiment(e: Experiment):

    e.log("starting meta experiment...")

    for num_words in e.NUM_WORDS_SWEEP:

        e.log(f"running experiment with {num_words} number of words")
        exp: Experiment = get_experiment(os.path.join(PATH, "03_analysing.py"))
        exp.NUM_WORDS = num_words
        exp.logger = e.logger
        exp.name = "meta_" + random_string()
        exp.run()

        e[f"metrics/length/{num_words}"] = sum(exp["metrics/length"].values())


experiment.run_if_main()
