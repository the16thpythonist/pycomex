# Plugin System Hooks

This file provides an overview of all the hooks that are available for implementing pycomex plugins. These hooks provide 
the opportunity to extend the functionality of pycomex by injecting custom code at different points of the pycomex 
experimentation workflow.

# 🧪 Experiment

All the following hooks are defined within the ``functional.experiment.Experiment`` class and are therefore part of 
the default computational experiment workflow. These are the main starting points for modification of main 
pycomex functionality.

## ``experiment_constructed(config: Config, experiment: Experiment)``

Called at the end of the constructor of each ``functional.experiment.Experiment`` object. Receives the experiment 
object iself as an argument.

## ``after_experiment_initialize(config: Config, experiment: Experiment)``

Called after all the steps in ``Experiment.initialize`` have been completed. This includes for example the creation
of the archive folder, the copying of the experiment code and the printing of the start message.

## ``after_experiment_finalize(config: Config, experiment: Experiment)``

Called after all the steps in ``Experiment.finalize`` have been completed. This includes for example the copying of the
experiment results to the archive folder and the printing of the end message.

## ``experiment_commit_fig(config: Config, experiment, Experiment, fig: Figure, name: str)``

Called at the end of the ``Experiment.commit_fig`` method. Receives the figure itself, the designated file name and 
the experiment object as arguments.

## ``experiment_commit_json(config: Config, experiment: Experiment, data: dict, name: str)``

Called at the end of the ``Experiment.commit_json`` method. Expects the data dictionary, the designated file name and
the experiment object as arguments.

## ``experiment_commit_raw(config: Config, experiment: Experiment, content: str, name: str)``

Called at the end of the ``Experiment.commit_raw`` method. Expects the data string, the designated file name and the
experiment object as arguments.

## ``experiment_track(config: Config, experiment: Experiment, name: str, value: float)``

Called at the end of the ``Experiment.track`` method. Expects the name of the tracked value and the value itself as
arguments.

---

# 🛠️ Config

The following hooks are defined within the ``config.Config`` class and are a "meta" perspective of influence 
the behavior of the global config singleton / the plugin system itself.

## ``plugin_registered(config: Config, name: str, plugin: Plugin)``

Called after a plugin has been registered with the pycomex plugin system. Received the plugin name and the plugin object 
itself as arguments.

---