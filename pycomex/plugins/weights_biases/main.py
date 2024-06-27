import os
import wandb
import datetime

import matplotlib.pyplot as plt

from pycomex.config import Config
from pycomex.plugin import Plugin, hook
from pycomex.functional.experiment import Experiment


class WeightsAndBiasesPlugin(Plugin):
    """
    This plugin integrates the "Weights and Biases" integration for the pycomex experiments.
    
    Weights and biases is an online service for tracking machine learning experiments. In an online 
    dashboard one can observe the real-time training progress of certain models. The service also supports
    the logging of different artifacts such as plots and images for example.
    
    The plugin uses the following hooks to realize the integration:
    - experiment_constructed: Check if the necessary conditions for wandb usage are met 
      (project name and api key defined)
    - after_experiment_initialize: register the run in the wandb service
    - experiment_commit_fig: commit a figure to the wandb service
    - experiment_track: track a float value to the wandb service for the plotting
    - after_experiment_finalize: stop the run in the wandb service
    """
    def __init__(self, config):
        super().__init__(config)
        self.run = None
        
        self.project_name: str = None
        self.api_key: str = None
        
    @hook('experiment_constructed', priority=0)
    def experiment_constructed(self, 
                               config: Config, 
                               experiment: Experiment, 
                               **kwargs
                               ) -> None:
        """
        This hook is called at the end of the Experiment constructor.
        
        Checks if the necessary conditions for the weights and biases integration are met. If so, sets 
        the "__wandb__" flag in the experiment metadata to True. The necessary conditions are that the 
        experiment defines a "WANDB_PROJECT" key in the parameters and that the environment variable
        "WANDB_API_KEY" is set.
        """
        
        experiment.metadata['__wandb__'] = False
        
        # There are two conditions that have been met before we can even start working with wandb:
        
        # The first condition is that within the experiment parameters there is a key called 'WANDB_PROJECT'
        # which defines the name of the project to which the experiment should be logged to. If this key is
        # not present, we'll skip the initialization of wandb.
        if 'WANDB_PROJECT' not in experiment.parameters:
            experiment.logger.debug('no wandb project defined. skipping...')
            return
        else:
            self.project_name = experiment.WANDB_PROJECT
        
        # THe second condition is that the environment variable 'WANDB_API_KEY' is set. If this is not the case
        # we'll skip the initialization of wandb. This environment variable is required to authenticate the
        # user with the wandb service.
        if 'WANDB_API_KEY' not in os.environ:
            experiment.logger.debug('wandb api key not found. skipping...')
            return
        else:
            self.api_key = os.environ['WANDB_API_KEY']
        
        # Only then can we login to the wandb service.
        # But - there is always the possibility that this fails due to connectivity issues or other reasons.
        try:
            experiment.logger.debug('login into weights an biases...')
            wandb.login()
        except Exception as exc:
            experiment.logger.debug(f'wandb login failed with "{exc}". skipping...')
            return
        
        # We'll save this special flag to the experiment data storage which indicates that wandb 
        # has been initialized for this experiment. We'll later check this flag in other hooks to 
        # check if it is save to execute wandb functionality or not.
        experiment.metadata['__wandb__'] = True
        
    @hook('after_experiment_initialize', priority=0)
    def after_experiment_initialize(self,
                                    config: Config, 
                                    experiment: Experiment,
                                    **kwargs
                                    ) -> None:
        """
        This method is called after Experiment.initialize() has been called.
        
        If the experiment metadata contains the "__wandb__" flag set to True, this method will start a
        new run in the wandb service. The run will be named after the experiment name and the start time.
        Uses the experiment metadata and parameters to log the configuration of the experiment.
        """
        if experiment.metadata.get('__wandb__', False):
            
            start_date_time = datetime.datetime.fromtimestamp(experiment.metadata['start_time'])
            experiment_name = experiment.metadata['name'] + '_' + experiment.format_full_name(start_date_time)
            
            experiment.logger.debug('starting weights and biases run...')
            self.run = wandb.init(
                project=experiment.WANDB_PROJECT,
                name=experiment_name,
                id=experiment_name,
                config={
                    'metadata': experiment.metadata,
                    'parameters': experiment.parameters,
                }
            )
    
    @hook('experiment_commit_fig', priority=0)
    def experiment_commit_fig(self,
                              config: Config,
                              experiment: Experiment,
                              name: str,
                              figure: plt.Figure,
                              ) -> None:
        
        if experiment.metadata.get('__wandb__', False):
            
            self.run.log({name: wandb.Image(figure)})
            
    @hook('experiment_track', priority=0)
    def experiment_track(self,
                         config: Config,
                         experiment: Experiment,
                         name: str,
                         value: float,
                         ) -> None:
        
        if experiment.metadata.get('__wandb__', False):
            
            self.run.log({name: value})
    
    @hook('after_experiment_finalize', priority=0)
    def after_experiment_finalize(self, 
                                  config: Config,
                                  experiment: Experiment,
                                  **kwargs,
                                  ) -> None:
        
        if experiment.metadata.get('__wandb__', False):
            
            experiment.logger.debug('stopping weights and biases run...')
            self.run.config.update({'metadata': experiment.metadata}, allow_val_change=True)
            self.run.finish()