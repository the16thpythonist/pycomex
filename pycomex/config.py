import importlib
import inspect
import os
import pkgutil
import warnings

from pycomex.plugin import Plugin, PluginManager
from pycomex.utils import PLUGINS_PATH, dynamic_import


class Singleton(type):
    """
    This is metaclass definition, which implements the singleton pattern. The objective is that whatever
    class uses this as a metaclass does not work like a traditional class anymore, where upon calling the
    constructor a NEW instance is returned. This class overwrites the constructor behavior to return the
    same instance upon calling the constructor. This makes sure that always just a single instance
    exists in the runtime!

    **USAGE**
    To implement a class as a singleton it simply has to use this class as the metaclass.
    .. code-block:: python
        class MySingleton(metaclass=Singleton):
            def __init__(self):
                # The constructor still works the same, after all it needs to be called ONCE to create the
                # the first and only instance.
                pass
        # All of those actually return the same instance!
        a = MySingleton()
        b = MySingleton()
        c = MySingleton()
        print(a is b) # true
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(metaclass=Singleton):
    """
    The config singleton for the class. This instance is globally acessible and can be used to store
    all the data that is relevant for the configuration of the pycomex experiments and it provided
    access to the plugin system.

    To access the config instance simply call the class constructor like this. Due to the singleton
    metaclass, this will actually always return the *same* instance.

    .. code-block:: python

        config = Config()

    """

    def __init__(self):

        # This dictionary is used to store all the data that is relevant for the configuration of the
        # pycomex experiments. This can be anything from parameters to global variables that are used
        # throughout the experiment. It may even act as a data exchange between different layers of
        # abstraction for example.
        self.data: dict[str, "any"] = {}

        # ~ plugin system
        # The config singleton maintains the access to the pycomex plugin system.

        self.plugins: dict[str, Plugin] = {}
        self.pm: PluginManager = PluginManager(config=self)

        # Only when the config is constructed the very first time we actually load the plugins.
        # Should a state reset of the config instance happen at some point, this will have to be
        # called manually to reload the plugins.
        self.load_plugins()

        # A hook that could be used for some meta functionality in which some plugins may modify other
        # plugins themselves or even enable/disable plugins based on some criteria.
        self.pm.apply_hook("after_plugins_loaded", config=self, plugins=self.plugins)

    def load_plugins(self) -> None:
        """
        This method loads all the pycomex plugins that are currently available on the system and populates
        the plugin manager ``self.pm`` and the plugin dictionary ``self.plugins``.

        There are two types of plugins:
        - *native plugins* - these are the ones that are defined as subfolders in the "plugins" folder
          in this package itself. They are always shipped with the pycomex core package as well.
        - *external plugins* - these are plugins that can be installed externally. They are defined as
          all python packages that start with the prefix "pycomex_". Every package that is currently
          installed on the system and starts with that is considered as a plugin to be loaded.
        """

        # ~ native plugins
        # These are subfolders in the "plugins" folder of this package.
        for element_name in os.listdir(PLUGINS_PATH):

            element_path = os.path.join(PLUGINS_PATH, element_name)
            module_path = os.path.join(element_path, "main.py")
            if os.path.exists(module_path) and os.path.isfile(module_path):
                try:
                    module = dynamic_import(module_path)
                    self.load_plugin_from_module(name=element_name, module=module)
                except ImportError as exc:
                    warnings.warn(
                        f'Failed to load plugin from module "{module_path}" due to {exc}'
                    )

        # ~ external plugins
        # Iterate over all installed modules/packages in the current Python runtime

        for finder, name, ispkg in pkgutil.iter_modules():
            if name.startswith("pycomex_"):
                try:
                    # Try to import the "main" module from the package
                    module_name = f"{name}.main"
                    try:
                        module = importlib.import_module(module_name)
                        self.load_plugin_from_module(name=name, module=module)
                    except ModuleNotFoundError:
                        # If "main.py" does not exist, skip this plugin
                        continue

                except Exception as exc:
                    warnings.warn(
                        f'Failed to load external plugin "{name}" due to {exc}'
                    )

    def load_plugin_from_module(self, name: str, module: object) -> None:
        """
        Given the ``name`` of a plugin and a ``module`` instance, this method will register all the
        ``Plugin`` subclasses that are defined in that module with the config's plugin manager.
        """

        for attribute_name in dir(module):

            obj = getattr(module, attribute_name)
            if inspect.isclass(obj):
                if issubclass(obj, Plugin) and not obj == Plugin:
                    plugin: Plugin = obj(config=self)
                    plugin.register()
                    self.plugins[name] = plugin

                    # This hook can be used to modify plugins right after they have been registered
                    # with the plugin manager and the config
                    self.pm.apply_hook(
                        "plugin_registered",
                        name=name,
                        plugin=plugin,
                    )

                    # This hook is called with the name of the actual plugin! Likely only the plugin itself
                    # will know this hook and will be able to use this to perform additional setup actions.
                    self.pm.apply_hook(
                        f"plugin_registered__{name}",
                        plugin=plugin,
                    )

    # ~ testability utils
    # The following methods provide some utility functionality for handling the config instance
    # which are primarly useful for testing purposes. The methods allow the current state of the
    # the config object to be exported, imported and reset. This can be used to store the state
    # of the config object before a test is run, reset it to a blank state and then restore it
    # after the test.

    def export_state(self) -> dict:
        """
        Returns a dictionary that represents the current state of the config object.
        """
        return {"data": self.data, "plugins": self.plugins, "pm": self.pm}

    def import_state(self, state: dict) -> None:
        """
        Given a previously exported config ``state`` dict, this method will restore the internal
        variables of the config object to the state defined there.
        """
        self.data = state["data"]
        self.plugins = state["plugins"]
        self.pm = state["pm"]

    def reset_state(self) -> None:
        """
        Completely resets the internal config state such that the data dict and plugin manager
        etc. are completely empty.
        """
        self.data = {}
        self.plugins = {}
        self.pm = PluginManager(config=self)
