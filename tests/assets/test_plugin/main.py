from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.plugin import Plugin, hook


class TestPlugin(Plugin):

    @hook("plugin_registered", priority=0)
    def plugin_registered(
        self,
        config: Config,
        name: str,
        plugin: Plugin,
    ) -> None:
        if "plugin_count" not in config.data:
            config.data["plugin_count"] = 0

        config.data["plugin_count"] += 1

    @hook("experiment_constructed", priority=0)
    def experiment_constructed(self, config: Config, experiment: Experiment) -> None:
        config.data["experiment_name"] = experiment.name
