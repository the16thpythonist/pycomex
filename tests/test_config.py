import os

import pytest

from pycomex.config import Config
from pycomex.plugin import Plugin
from pycomex.testing import ConfigIsolation
from pycomex.utils import dynamic_import

from .util import ASSETS_PATH


class TestConfig:
    """
    Tests the "Config" singleton class
    """

    def test_is_singleton(self):
        """
        The config class needs to be a "singleton" meaning that there ever only exists one instance of
        this object. The constructor is modified such that it will always return the same instance, if
        one already exists.
        """
        config1 = Config()
        config2 = Config()

        assert id(config1) == id(config2)

    def test_export_import_state(self):
        """
        It should be able to export the current state of the config (data, plugins etc.) with
        the "export_state" function, reset it and then later import that state back into the config
        with the "import_state" function.

        THIS TEST IS CRUCIAL FOR
        """
        config = Config()

        # First of all we populate the config state with some data
        config.data["string"] = "hello world"
        config.data["number"] = 3.14
        config.plugins["plugin"] = Plugin(config=config)
        assert len(config.data) != 0

        config_state = config.export_state()
        assert isinstance(config_state, dict)
        assert len(config_state) != 0

        # Now we reset the config object which should clear all the internal data
        config.reset_state()
        assert len(config.data) == 0
        assert len(config.plugins) == 0
        assert len(config.pm) == 0

        # And now we can import the state again into the config and see if that worked
        config.import_state(config_state)
        assert config.data["string"] == "hello world"
        assert config.data["number"] == 3.14
        assert "plugin" in config.plugins

        # Very important that at the end we clear the state again so that we have a properly
        # reset environment for the next tests...
        config.reset_state()

    def test_config_isolation(self):
        """
        The ConfigIsolation class is a context manager that can be used to temporarily isolate the
        config singleton object. This can be useful for testing purposes where we want to modify the
        config object for a test but then restore it to its original state after the test has been run.
        """
        with ConfigIsolation() as config:
            config.reset_state()
            config.data["string"] = "hello world"
            assert len(config.data) == 1
            assert config.data["string"] == "hello world"

        assert len(config.data) == 0

    def test_load_test_plugin(self):
        """
        It should be possible to use the "load_plugin_from_module" method of the config class to
        load a plugin from a module object. We test if this works using the test plugin which is part
        of the testing assets.
        """
        test_plugin_module_path = os.path.join(ASSETS_PATH, "test_plugin", "main.py")
        module = dynamic_import(test_plugin_module_path)

        with ConfigIsolation() as config:
            config.reset_state()
            config.load_plugin_from_module("test_plugin", module)
            assert "test_plugin" in config.plugins

            # We know that the test plugin registers a function with the "plugin_registered" hook
            # which counts the number of registered plugins. So we can check if that function was
            # called and if it did its job correctly.
            assert "plugin_count" in config.data
            assert config.data["plugin_count"] == 1

        assert len(config.plugins) == 0
        assert len(config.data) == 0
