"""
This module implements the standard structure expected of a pycomex experiment module. It generates some
random numbers and plots them afterwards. It is used for testing purposes.

DO NOT MODIFY. The contents of this file will be checked for in unittests.
"""
import os
import pathlib

import numpy as np
import matplotlib.pyplot as plt

from pycomex.experiment import Experiment
from pycomex.util import Skippable

# == FUNCTIONALITY PARAMETERS ==
MEAN = 0
STANDARD_DEVIATION = 1
NUM_VALUES = 1000

# == ANALYSIS PARAMETERS ==
NUM_BINS = 10
COLOR_PRIMARY = 'gray'

# == EXPERIMENT PARAMETERS ==
PATH = pathlib.Path(__file__).parent.absolute()
BASE_PATH = os.path.join(os.path.dirname(PATH), 'artifacts')
NAMESPACE = 'experiment_results/mock_experiment'
DEBUG = True
# This special "DEPENDENCY_PATHS" variable has to cause the experiment to copy the specified text
# file into the archive folder!
DEPENDENCY_PATHS = {
    'text': os.path.join(PATH, 'mock.txt')
}
with Skippable(), (e := Experiment(base_path=BASE_PATH, namespace=NAMESPACE, glob=globals())):
    values = np.random.normal(
        loc=MEAN,
        scale=STANDARD_DEVIATION,
        size=NUM_VALUES,
    )
    e['values'] = values

    # This section here checks if default implementation of hooks works as I would imagine
    # it should work. Doing it like this, the code in the function should get executed as a
    # default implementation, but it should also be possible to override this code from
    # any sub-experiments.
    @e.hook('after_values', default=True)
    def default_implementation(_e, values):
        _e.info('DEFAULT IMPLEMENTATION')

    e.apply_hook('after_values', values=values)


with e.analysis:
    fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(10, 10))
    ax.hist(e['values'], bins=NUM_BINS, color=COLOR_PRIMARY)
    e.commit_fig('values.pdf', fig)
