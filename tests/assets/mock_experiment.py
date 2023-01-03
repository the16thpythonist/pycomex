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
with Skippable(), (e := Experiment(base_path=BASE_PATH, namespace=NAMESPACE, glob=globals())):
    values = np.random.normal(
        loc=MEAN,
        scale=STANDARD_DEVIATION,
        size=NUM_VALUES,
    )
    e['values'] = values
    e.apply_hook('after_values', values=values)


with e.analysis:
    fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(10, 10))
    ax.hist(e['values'], bins=NUM_BINS, color=COLOR_PRIMARY)
    e.commit_fig('values.pdf', fig)
