"""
This module implements the standard structure expected of a pycomex experiment module. It generates some
random numbers and plots them afterwards. It is used for testing purposes.

DO NOT MODIFY. The contents of this file will be checked for in unittests.
"""
import os
import pathlib

from pycomex.experiment import SubExperiment
from pycomex.util import Skippable

# == FUNCTIONALITY PARAMETERS ==
NUM_VALUES = 200
OFFSET = 10

# == EXPERIMENT PARAMETERS ==
PATH = pathlib.Path(__file__).parent.absolute()
EXPERIMENT_PATH = os.path.join(PATH, 'mock_experiment.py')
BASE_PATH = os.path.join(os.path.dirname(PATH), 'artifacts')
NAMESPACE = 'experiment_results/mock_sub_experiment'
DEBUG = True
with Skippable(), (se := SubExperiment(EXPERIMENT_PATH, BASE_PATH, NAMESPACE, glob=globals())):

    @se.hook('after_values', replace=True)
    def offset_values(e, values):
        e.info('SUB IMPLEMENTATION')
        e['values'] = values + OFFSET


