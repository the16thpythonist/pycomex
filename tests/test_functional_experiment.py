import os
import sys

from pycomex.testing import ConfigIsolation
from pycomex.testing import ExperimentIsolation
from pycomex.functional.experiment import Experiment, run_experiment

from .util import ASSETS_PATH


def test_run_experiment_works():
    """
    The "run_experiment" utility function should be able to execute an experiment module from 
    its absolute file path
    """
    experiment_path = os.path.join(ASSETS_PATH, 'mock_functional_experiment.py')
    experiment: Experiment = run_experiment(experiment_path)

    assert experiment.error is None
    assert len(experiment.data) != 0


class TestExperiment:
    
    def test_construction_basically_works(self):
        """
        It should be possible to construct the experiment object without any errors and after 
        constructing it should have the parameters that were passed to it.
        """
        parameters = {'PARAMETER': 10}
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod=parameters) as iso:
            
            config.load_plugins()
            
            experiment = Experiment(
                base_path=iso.path,
                namespace='experiment',
                glob=iso.glob,
            )
            
            assert isinstance(experiment, Experiment)
            assert 'PARAMETER' in experiment.parameters

            
