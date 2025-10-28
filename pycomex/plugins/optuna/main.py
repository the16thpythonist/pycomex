"""Plugin integrating `Weights & Biases` into experiments."""

import datetime
import os
import re
from typing import Optional

import rich_click as click
import matplotlib.pyplot as plt

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.plugin import Plugin, hook


class OptunaPlugin(Plugin):
    """
    This plugin integrates Optuna hyperparameter optimization into the package.
    """

    def __init__(self, config):
        super().__init__(config)
        
        # --- experiment parameters ---
        # These parameters will have to be populated from the experiment - after that has been initialized
        # all of these information we need further down the line for the study tracking and so on.
        
        # This will be the path to the experiments folder - so the folder that contains all of the experiment 
        # modules themselves or at the very least the parent folder of the current experiment runtime.
        self.base_path: Optional[str] = None
        
    @hook("cli_register_commands", priority=0)
    def register_cli_commands(self, config, cli):
        """Register custom CLI commands."""

        # --- define custom commands ---
        
        @click.group(
            name="optuna"
        )
        def optuna():
            pass
        
        @click.command(
            "optimize", 
            short_help=(
                "Run an experiment module with Optuna optimization. This effectively means that certain parameters "
                "will not use the fixed values but instead use the next set of parameters determined by optuna in "
                "the current trial run in the search of the ideal parameter set for the configured objective."
                )
        )
        @click.option(
            "--name", 
            help="Name parameter"
        )
        @click.pass_obj
        def optimize(cli_instance, name):
            # Access CLI utilities
            cli_instance.cons.print(f"[bold]Hello {name}![/bold]")

            # Access plugin state via closure
            self.process(name)
            
        
        @click.command(
            "results",
            short_help=(
                'Show the results of the optimization for the given EXPERIMENT.'
            )
        )
        @click.argument("experiment")
        def results(cli_instance, name):
            pass

        # --- register custom commands ---
        
        optuna.add_command(optimize)
        optuna.add_command(results)
        cli.add_command(optuna)

    @hook("experiment_constructed", priority=0)
    def experiment_constructed(
        self, config: Config, experiment: Experiment, **kwargs
    ) -> None:
        """
        This hook is called at the end of the Experiment constructor.
        
        
        """
        pass

    @hook("after_experiment_initialize", priority=0)
    def after_experiment_initialize(
        self, config: Config, experiment: Experiment, **kwargs
    ) -> None:
        """
        This method is called after Experiment.initialize() has been called.


        """
        
        self.base_path = experiment.base_path

    @hook("experiment_commit_fig", priority=0)
    def experiment_commit_fig(
        self,
        config: Config,
        experiment: Experiment,
        name: str,
        figure: plt.Figure,
    ) -> None:
        pass

    @hook("experiment_track", priority=0)
    def experiment_track(
        self,
        config: Config,
        experiment: Experiment,
        name: str,
        value: float,
    ) -> None:
        pass

    @hook("after_experiment_finalize", priority=0)
    def after_experiment_finalize(
        self,
        config: Config,
        experiment: Experiment,
        **kwargs,
    ) -> None:
        pass

    # --- Helper Methods ---
    
    def get_study_folder(experiment: Experiment) -> str:
        """
        Given an `experiment`, this method will determine the appropriate ".study" folder which will 
        then give the thing that is now the thing
        """