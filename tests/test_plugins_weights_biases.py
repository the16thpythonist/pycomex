"""
Unittests for the weights and biases plugin "weights_biases".
"""
import os
import sys

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.testing import ConfigIsolation
from pycomex.testing import ExperimentIsolation


def test_plugin_loading_works():
    """
    After simply calling config.load_plugins() the plugin manager should be populated with all the available 
    plugins including the target weights and biases plugin.
    """
    with ConfigIsolation() as config:
        
        assert len(config.pm) == 0
        
        # This should properly load all the available plugins including the weights and biases 
        # plugin to be tested.
        config.load_plugins()
        
        assert 'weights_biases' in config.plugins
        assert len(config.pm) != 0
    
    
def test_plugin_basically_works():
    """
    The weights and biases plugin should be able to be initialized and the experiment should be able to run
    without any issues.
    """
    parameters = {
        'WANDB_PROJECT': 'test',
    }
    
    with ConfigIsolation() as config, ExperimentIsolation(sys.argv, glob_mod=parameters) as iso:
        
        config.load_plugins()
        assert 'weights_biases' in config.plugins
        
        experiment = Experiment(
            base_path=iso.path,
            namespace='experiment',
            glob=iso.glob,
        )
        
        experiment.run()
        
        assert '__wandb__' in experiment.metadata
        assert experiment.metadata['__wandb__'] is False
        
        assert 'weights_biases' in config.plugins
        assert config.plugins['weights_biases'].project_name == 'test'
        