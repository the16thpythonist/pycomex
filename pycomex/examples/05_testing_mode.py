"""
This experiment will illustrate how to use the testing mode functionality of the pycomex library 
to test experiments with a long runtime for coding errors in beforehand.

**MOTIVATION**

There are few things worse than having a really long running experiment raise an exception on one of 
the very last few lines of code - potentially rendering hours or days of computational time useless.
Although a real annoyance when conducting computation experiments, it turns out this scenario 
actually happens quite a lot.

Often an experiment already works and one just wants to add some additional feature - perhaphs 
only some additional plotting - to the very end of it, but a spelling error somehow slips into that 
code. One executes the experiment assuming it will work - since it did so before the modification - 
only to realize that it crashed at the very last stage.

**TESTING**

To mitiage this issue, it's a good practice to always run a *testing* version of the experiment 
before submitting it for the final run on a cluster or the like. 

In such a testing version, we ideally want as much of the experiment code to execute as possible 
with minimal runtime. With experiments becoming slightly more complex, setting up such a testing 
scenario often times can't be done by changing a single line of code - often times it is necessary 
to change multiple parameters or even execute some custom code.

The PyComex framework provides some features of convenience to seamlessly support this testing practice, 
which will be explained in this example module.

"""

import os
import time

import matplotlib.pyplot as plt
import numpy as np

from pycomex import Experiment, file_namespace, folder_path

# (1)   Often times an experiment includes parameters like this, which for example determine the number
#       of iterations of a procedure, or the number of elements to load from a dataset etc.
#       For the "normal" configuration of an experiment these values will likely be large and experiments
#       will have a considerable runtime. Therefore it might be necessary
NUM_ITERATIONS = 10_000
NUM_ELEMENTS = 1000

# (2)   An experiment can be put into testing mode by setting this magic parameter __TESTING__ to True.
#       if the parameter is not explicitly set to True, it will always be implicitly be assumed as False.
#       This way, switching between the testing mode and execution mode of an experiment again only
#       includes changing a single line of code!
__TESTING__ = True
__DEBUG__ = True


@Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)
def experiment(e: Experiment):

    # (3)   It is now possible to write a custom code implementation including all the necessary modifications
    #       to the experiment that will result in a testing version of the experiment that can be run much
    #       more quickly.
    #       For most experiments this will most likely only include the chaning of several parameters, but
    #       it is also possible to execute any custom code that is needed to achieve the testing state, such
    #       as the entire generation of a small mock dataset file for example.
    @e.testing
    def testing(e: Experiment):
        e.NUM_ITERATIONS = 10
        e.NUM_ELEMENTS = 10

        # potentially any custom code required to put the experiment into the testing state...

    # Here we have a mock implementation of an experiment where we just do some data generation in
    # a loop which will take significantly longer, the more iterations there are.
    e.log("executing main loop...")
    for i in range(e.NUM_ITERATIONS):

        e[f"data/{i}"] = np.random.normal(
            size=(NUM_ITERATIONS, 2), loc=(i, i), scale=(1, 2)
        )

    # Usually there is then some additional code after this main bulk of the experiment is done, which
    # implements an evaluation or some plotting and it is at this point where an unexpected error would be
    # particularly detrimental.
    e.log("plotting the results...")
    fig, ax = plt.subplots(
        ncols=1,
        nrows=1,
        figsize=(10, 10),
    )
    for values in e["data"].values():
        values = np.array(values)
        ax.scatter(values[:, 0], values[:, 1], color="blue")

    fig_path = os.path.join(e.path, "plot.pdf")
    fig.savefig(fig_path)


# (4)   An "experiment.testing" implementation will also persist to the child experiments - if it is
#       defined in the base experiment. However testing implementations are fully overriding, which
#       means that if a child experiment provides a different implementation, the base experiment version
#       will NOT be called anymore.
experiment.run_if_main()
