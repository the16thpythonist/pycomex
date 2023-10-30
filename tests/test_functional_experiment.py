import os

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


def test_experiment_construction_basically_works():
    """
    A new Experiment object can be constructed without raising errors
    """
    value = 10
    with ExperimentIsolation(glob_mod={'PARAMETER': value}) as iso:
        experiment = Experiment(
            base_path=iso.path,
            namespace='experiment',
            glob=iso.glob,
        )
        
        assert 'PARAMETER' in experiment.parameters
        assert experiment.parameters['PARAMETER'] == value
        # Here we test if the alternative experiment parameter accessing api works
        # Technically each parameter will automatically be exposed as a property
        assert experiment.PARAMETER == value
