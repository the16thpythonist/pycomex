from pycomex.plugin import PluginManager, StopHook
from pycomex.testing import MockConfig


class TestPluginManager:

    def test_construction_basically_works(self):

        config = MockConfig()
        pm = PluginManager(config=config)
        assert isinstance(pm, PluginManager)

    def test_register_hook_basically_works(self):
        """
        The most basic way to use the plugin system is to first register a function with the register_hook
        method and then later query it with the apply_hook method.
        """
        config = MockConfig()
        pm = PluginManager(config=config)

        def hook(config, **kwargs):
            config.data["hook"] = True

        pm.register_hook(hook_name="test_hook", function=hook)
        pm.apply_hook(hook_name="test_hook")

        # In the hook we add this property to the config object, so it has to exist if the hook
        # was actually executed
        assert "hook" in config.data
        assert config.data["hook"] is True

    def test_hook_priority_works(self):
        """
        Additional to the hook name, it is possible to specify a priority for the hook as well
        this priority determines in which order functions get executed when there are multiple
        hooks registered for the same hook name.
        """
        config = MockConfig()
        pm = PluginManager(config=config)

        config.data["list"] = []

        @pm.hook("test_hook", priority=1)
        def low_prio(config, **kwargs):
            config.data["list"].append(2)

        @pm.hook("test_hook", priority=2)
        def high_prio(config, **kwargs):
            config.data["list"].append(1)

        pm.apply_hook(hook_name="test_hook")

        # if the hooks were executed in the order of registration then the list would be (2, 1) but
        # if the priority was respected then the list would be (1, 2)
        assert tuple(config.data["list"]) == (1, 2)

    def test_stop_hook_works(self):
        """
        It is possible to stop the execution of a hook chain by raising a StopHook exception. This
        exception should be caught by the plugin manager and the execution of the hook chain should
        be stopped at that point.
        """
        config = MockConfig()
        pm = PluginManager(config=config)

        @pm.hook("test_hook", priority=1)
        def set_true(config, **kwargs):
            config.data["hook1"] = True
            raise StopHook(value=True)

        @pm.hook("test_hook", priority=0)
        def set_false(config, **kwargs):
            config.data["hook2"] = False

        result = pm.apply_hook(hook_name="test_hook")
        assert result is True

        # The first hook should be executed and the second one should not be executed because the
        # first hook raises a StopHook exception which then finally results in the value being True
        assert "hook1" in config.data
        assert config.data["hook1"] is True
        assert "hook2" not in config.data
