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


class TestExperimentArgumentParser:
    """
    ExperimentArgumentParser is a class that is used to parse command line arguments that are passed to the 
    individual experiment modules.
    """
    
    def test_command_line_arguments_basically_work(self):
        """
        It should generally be possible to modify the behavior of an experiment object by specifiying 
        command line arguments (sys.argv)
        """
        argv = ['test.py', '--__DEBUG__=True']
        with ConfigIsolation() as config, ExperimentIsolation(argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace='experiment',
                glob=iso.glob,
            )
            # We'll have to call this method explicitly because this operation would only be done in the 
            # experiment.run_if_main() method usually.
            experiment.arg_parser.parse()
            
            assert '__DEBUG__' in experiment.parameters
            assert experiment.__DEBUG__ is True

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
            
    def test_prefix_parameter_works(self):
        """
        When using the special parameter __PREFIX__ that string should be added in front of the 
        experiment name when the experiment archive folder is being created.
        """
        parameters = {'__PREFIX__': 'custom'}
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod=parameters) as iso:
            
            config.load_plugins()
            
            experiment = Experiment(
                base_path=iso.path,
                namespace='experiment',
                glob=iso.glob,
            )
            experiment.run()
            assert '__PREFIX__' in experiment.parameters
            
            assert experiment.name.startswith('custom')
            assert 'custom' in experiment.path
