"""
This example showcases the weights and biases integration for pycomex. The weights and biases plugin
is enabled by default and an experiment can be directly logged to the wandb service by meeting the 
following two criteria: 

- The WANDB_API_KEY environment variable is set in the environment from which the experiment was 
  started.
- The experiment defines the WANDB_PROJECT parameter at the beginning of the file as a non-empty 
  string identifier for an exsiting wandb project.
"""

import time

import matplotlib.pyplot as plt
import numpy as np

from pycomex import Experiment, random_plot, file_namespace, folder_path

# :param N_ELEMENTS:
#      The number of elements to be randomly generated for the scatter plot.
N_ELEMENTS: int = 100
# :optparam WANDB_PROJECT:
#      The name of the wandb project to which the experiment should be logged.
#      This is required to activate the weights and biases integration!
WANDB_PROJECT: str = "test"

__DEBUG__ = True

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)


@experiment
def experiment(e: Experiment):

    e.log("starting experiment...")
    # The experiment "track" method can be used to track the numeric (float) values of certain
    # metrics for example. These will be logged to the wandb service directly and can be
    # observed in the online dashboard in real-time.
    e.track("time", time.time())

    figure = random_plot()
    e.track("plot", figure)

    e.log("creating plot...")
    e.track("time", time.time())
    fig, ax = plt.subplots(
        ncols=1,
        nrows=1,
    )
    data = np.random.rand(N_ELEMENTS, 2)
    ax.scatter(data[:, 0], data[:, 1])

    # The experiment "commit_fig" method can be used to commit a figure to the wandb service as
    # an image artifact. This can be observed in the online dashboard as well. The figure will be
    # saved to the experiment folder as well.
    e.commit_fig("figure.pdf", fig)

    e.track("time", time.time())
    e.track("plot", random_plot())


experiment.run_if_main()
