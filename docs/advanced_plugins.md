# Writing Plugins

The pycomex library is designed to be extensible through a plugin system. Plugins can be used to add new functionality, modify existing behavior, or integrate with external systems. This document provides guidelines for writing and integrating plugins into the pycomex library.

## The Hook System

Plugins are implemented using a *hook system*. During various stages of the experiment lifetime of the computational experiment, the pycomex library will call specific *"hook"* functions. These hook functions are primarily *placeholders* associated with a known and unique string identifier. Each new plugin has the option to register custom function implementations to these hooks such that this custom code will be executed at various stages of the experiment lifecycle.

Depending on the specific hook, these functions may receive various arguments or may be required to return specific values. These arguments and return values can then usually be used to modify the behavior of the pycomex library itself to achieve the intended functionality of the plugin.

As an example, one can imagine a very simple plugin that prints a simple "Hello World" message before the start of each experiment. For such a use case, it would make most sense to register a custom function to the `before_experiment` hook. This hook is called right before the experiment starts.

To implement an intended plugin functionality, one necessary step is therefore to familiarize oneself with the available hooks that are provided by the pycomex library.

## Plugin Discovery

The discovery of plugins is done as one of the very first steps of the pycomex library. The discovery is basically split into an *internal* and an *external* discovery step.

**Internal Plugins.** These are the plugins which are shipped together with the pycomex library itself. These plugins are the default plugins that come with the library and are located in the `pycomex/plugins` directory. Each folder in this plugins directory is assumed to be its own plugin.

**External Plugins.** These are the plugins which can be installed by the user. During the plugin discovery stage, the library will assume every Python package that is installed in the current environment starting with the string `pycomex_` to be its own plugin.

## Creating a Plugin

Based on the previous section, the primary method of creating a new plugin is to create a new Python package whose name starts with the prefix `pycomex_`. This package can then contain any number of Python modules, which can implement the intended functionality of the plugin, but it *must* contain a `main.py` module which acts as the entry point for the plugin managment system.

The `main.py` module should implement a subclass of the `pycomex.plugins.Plugin` class. This subclass is where the plugin's functionality is defined, and it should register the necessary hooks that the plugin will use. This class may have any name, so long as it inherits from the `pycomex.plugins.Plugin` class.

**Example.** As an example, we'll consider a simple plugin that adds additional messages at the beginning and end of each experiment. The plugin will be called `pycomex_hello_world`.

```python title="pycomex_hello_world/main.py"
from pycomex.plugins import Plugin, hook

class HelloWorldPlugin(Plugin):

    @hook('before_experiment', priority=0)
    def before_experiment(self, *args, **kwargs):
        print('Hello World! The experiment is about to start.')

    @hook('after_experiment', priority=0)
    def after_experiment(self, *args, **kwargs):
        print('Goodbye World! The experiment has finished.')
```

To complete the plugin, you'll need to ensure that the package is installed in your Python environment. This can be done by creating an appropriate `pyproject.toml` or `setup.py` file.

!!! info "Plugin Initialization"

    Do not use the default python `__init__` constructor of your custom plugin class, as the actual plugin object instance will be automatically created by the plugin system internally. Instead use the `init` hook to perform any necessary setup operations which would usually be done in the constructor. This hook will be called right after the plugin object instance is created. 

**Summary.** To summarize a plugin can be created by the following steps:

1. Create a new Python package with the name starting with `pycomex_`.
2. Create a `main.py` module inside this package.
3. Implement a subclass that inherits from the `pycomex.plugins.Plugin` class inside the `main.py` module.
4. Register the necessary hooks inside of this subclass.

