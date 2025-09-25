=======
History
=======

0.1.0 (09.07.2022)
------------------

* First release on PyPI.

0.1.1 (11.07.2022)
------------------

* Added the "poetry_bumpversion" plugin https://github.com/monim67/poetry-bumpversion to update the version
  strings in all the relevant files
* Using "black" for code formatting
* Using "flake9" for linting

0.2.0 (12.07.2022)
------------------

* Every experiment file now has a command line interface realized with `argparse`
    * It is possible to pass in either a .JSON or a .PY file which are able to modify the default
      experiment parameters defined in the experiment file
    * It is possible to retrieve the destination path when invoking an experiment file over the command line
* A copy of the actual experiment file is copied as a snapshot to the experiment record folder
* It is possible to define additional jinja templates which are rendered as additional files into the
  experiment record folder
    * One default template which is rendered this way is "analysis.py" module, which provides a boilerplate
      starting point for further analysis on the experiment results.

0.2.1 (12.07.2022)
------------------

* Now it is possible to commit matplotlib Figures directly to the experiment with `Experiment.commit_fig`
* File artifact paths are now automatically tracked as metadata
* Added a default template `annotations.rst` to be rendered for each experiment which provides a
  boilerplate starting point for additional thoughts to be added

0.3.0 (17.07.2022)
------------------

* Added `Experiment.commit_json` to directly store dict data as json file artifacts for the experiment
  records
* Improved the `analysis.py` templating for experiments
    * Using the context manager `Experiment.analysis` within the experiment file can be used to not only
      directly execute the analysis right after the experiment is completed but also all the code within
      that context managers content block is copied into the analysis template of that run and it will
      work as it is
    * This is due to the fact, that `Experiment` now automatically realizes if it is being imported
      from a `snapshot.py` within an existing record folder. In that case it populates internal fields
      such as `Experiment.data` by loading the persistent file artifact.
* Added `examples/analysis.py` which documents / explains the previously mentioned process

0.3.1 (20.08.2022)
------------------

* Fixed bug that `e.info()` could not be used inside the `analysis.py` file
* Decided to add `numpy` and `matplotlib` to the dependencies after all. Originally I did not want to
  include them because I don't strictly need them and they are quite big packages. But honestly, what kind
  of computational experiment works without those two nowadays?
* Renamed the template files with better naming scheme
* Updated readme

0.4.0 (21.08.2022)
------------------

* Added `pycomex.experiment.ArchivedExperiment` which makes it possible to load an arbitrary experiment
  instance from the archived folder and use it much like it is possible from within `analysis.py`
* Added `pycomex.experiment.ExperimentRegistry` which can be used to load an experiment base path and
  automatically discover all the (nested) namespace folders within which contain actual experiment run
  archives.
    * Added `pycomex.experiment.NamespaceFolder` which represents and allows to work with namespace
      folders, for example by easily getting the `ArchivedExperiment` instance according to an experiment
      run (numeric) index.
* Added `psutil` to dependencies to implement hardware resource monitoring as an additional feature
  when printing the intermediate status of the experiment run with `Experiment.status()`

0.4.1 (12.09.2022)
------------------

* Fixed a bug which broke the `with e.analysis:` functionality in Python 3.10. Rewrote `RecordCode`
  such that it no longer uses the deprecated functionality and now also works for the new version.
* `with e.analysis:` can now also be used on the indent level as the experiment context manager itself
  which is more intuitive. Using it this way also solves some unwanted interaction with the error catching
  behavior of the experiment context.

0.5.0 (14.09.2022)
------------------

* By fixing the previous bug, I introduced a new one: Essentially now that I moved the analysis context
  manager to the same logical level as the experiment context manager I was facing the same problem: It got
  executed when merely importing the module, which had all sorts of bad side effects. This bug is fixed now.
* While fixing that bug, I accidentally stumbled on a much better method of how to make context managers
  skippable, which I find so good that I moved the experiment context manager to use the same mechanism
  as well, which gets rid of the need for calling `Experiment.prepare()`. But this means some
  backwards incompatible API changes.

0.5.1 (14.09.2022)
------------------

* If numpy arrays are added to the internal data store, they are automatically converted to lists, so that
  they can be json serialized later.

0.5.2 (18.09.2022)
------------------

* Extended `run_experiment` such that it can be called in a non-blocking manner and such that it relays
  the output of the experiment subprocess to stdout in the main process

0.6.0 (19.09.2022)
------------------

* Added `pycomex.cli.ExperimentCLI` class which can be used to automatically create a computational
  experiment command line interface for a project by simply providing the folder path at which all the
  experiment modules are located. They will automatically be discovered and the CLI will automatically
  be built based on those experiments. Currently supported are `list` command which will
  show an overview of experiments, `info` which will print more details and `run` which will prompt
  the execution of an experiment.
* Made some changes in the `Experiment` class. Most importantly it now sets `__experiment__` global
  variable in the original module namespace, which makes it easier to detect whether any given
  python module contains an experiment or not.

0.6.1 (28.11.2022)
------------------

* Fixed a bug where numpy arrays within the storage would cause an exception during the serialization
  process by using a custom json encoder class which first converts all numpy arrays to nested lists

0.7.0 (03.01.2023)
------------------

* Added the `experiment.SubExperiment` class which implements experiment inheritance! This class now
  allows to refer to a different experiment module to run as parent experiment, but with parameter
  modifications.
* Added a hook system to experiments, which allows for parent experiment modules to define certain points
  at which custom code from child experiments may be injected.

* changed the datetime format in `HISTORY.rst` to the only sane option
* Fixed a minor windows compatibility problem with the automatic pathing determining for experiments.
* Added the module `pycomex.testing` to contain all of the utility functions and classes which are needed
  to facilitate the unittests such as the `ExperimentIsolation` context manager.
* Refactored most unittests to use `pytest` instead of `unittest`
* Fixed a bunch of unittests that were not updated for the new API
* Fixed a rather serious bug in `testing.ExperimentIsolation` which left permanent modifications in
  in the globals dict and thus introduced side-effects in between different unittests.

**INTERFACE CHANGES**

* changed functionality and signature of `experiment.run_experiment`. Previously this function executed
  an existing experiment module by using `subprocessing.run` and returned the completed process instance.
  Now, this works by using `experiment.SubExperiment` and the function actually returns an experiment
  instance.
* Do to the change above, the same now applies to `experiment.run_example`.

0.7.1 (17.01.2023)
------------------

* Slightly changed the hook mechanic to allow the possibility of defining overwritable default
  implementations for hooks.

0.8.0 (20.01.2023)
------------------

* Removed the standard prints during the call of a hook, because they proved annoying in practice.
* Fixed the bug, where a sub experiment snapshot would not be executable because it was missing the the
  base experiment. The base experiment script is now copied into the archive folder as well.
* Added the dependency system: It is now possible to define files which an experiment execution depends on
  via the special `DEPENDENCY_PATHS` dict parameter. These files will be copied into the created archive
  folders.

0.8.1 (27.01.2023)
------------------

* Added `Experiment.p` as a shorthand for `Experiment.parameters` because that got really annoying to
  write so often.
* Fixed a serious bug, where the `snapshot.py` file in the archive folder of an experiment was not in
  fact the sub experiment but the lowest level base experiment!

0.8.2 (09.02.2023)
------------------

* Updated Readme file

0.8.3 (13.02.2023)
------------------

* Fixed the problem that when an exception occurs within the RecordCode context manager that this is not
  properly printed. Now the entire traceback for every error is printed to the logger stream
* Moved the entire analysis RecordCode functionality from Experiment to AbstractExperiment so that it
  can also be used in SubExperiment
* Fixed the bug that the analysis.py file within the archive folder would not work at all for
  SubExperiment runs
* SubExperiments can now also define analysis context and those will be additive, meaning that the code
  from those will be added to he end of all the analysis code that was previously created by the parent
  experiment

0.8.4 (16.02.2023)
------------------

* Added the feature of "parameter hooks". Now it is possible to register a hook with the name of a parameter
  in a sub experiment to modify that parameter before the start of the experiment...

0.8.7 (27.03.2023)
------------------

* Fixed a bug where the inspect module would not be working correctly in executions of SubExperiment
* Fixed the version dependency for "click"
* Fixed the version dependency for "numpy"


0.9.0 (27.04.2023)
------------------

Introduced the new **functional API**. This is a completely new way to use the pycomex framework which
will slowly replace the old way. In this new method the whole thing is implemented with decorators instead
of context managers, which makes the entire implementation approximately 100x easier and less riddled with
side effects and bugs.

- Already changed the README example to use the functional API
- Slowly started replacing the examples with the functional API

0.9.1 (28.04.2023)
------------------

CRITICAL FIX: The prevsious package did not actually contain the "functional" sub package, but this one
does now!

- Added some more functionalities to `functional.Experiment`
- Changed all the example files to use the functional interface now
- Some more code documentation

0.9.2 (28.04.2023)
------------------

- Fixed a bug that sub experiment modules with relative paths to base experiments would cause errors when
  the current working directory was not their parent directory

0.9.3 (05.05.2023)
------------------

- Fixed an important bug in `dynamic_import` which prevented `inspect` from working properly in the
  imported modules

0.9.4 (08.05.2023)
------------------

- In the functional interface, added the crucial feature of default hook implementations
- Fixed an important bug to make analysis.py files work with sub experiments

0.9.5 (04.07.2023)
------------------

- I had to change the name of the experiment file copy that is placed in the artifacts folder from "code.py" 
  to "experiment_code.py" because there was a very weird naming collision with tensorflow internals
- Also adjusted the anylsis file template accordingly.

0.10.0 (27.10.2023)
-------------------

Added the "testing" functionality as it's own feature to the Experiment class

- it is now possible to define the hook with the necessary code to put the experiment into testing mode using 
  the `Experiment.testing` function and the `__TESTING__` magic parameter.
- Added a dedicated example that illustrates the testing mode `05_testing_mode.py`

Command line interface

- fixed the command line interface. `ExperimentCLI` should now be working with the new pycomex functional API
- Switched to using python `rich` package for the CLI printing
- Changed the styling of the "list" and "info" commands to rich formatting

Other changes

- During construction an `Experiment` instance will now attempt to automatically parse the parameter description strings from the 
  module's comments and the parameter typing information from the type hints annotations dict. This information will then be stored 
  in `Experiment.metadata` dictionary.
- Added some more docstrings
- Updated the `README.rst`
- Added the `DOCUMENTATION.rst` and started to compile some additional documentation that is not immediately 
  relevant to the README

0.10.1 (05.11.2023)
-------------------

- Fixed a breaking bug during the construction of Experiment instances 
- Added information about possible hooks to the `info` cli command as well

0.10.2 (08.11.2023)
-------------------

- fixed a crucial bug that would break the experiment modules if no module level doc string exists
- Added the `get_experiment` method which allows to easily get the Experiment object instance based 
  on a given absolute experiment module path.
- Added the example `07_meta_experiments.py`

0.11.0 (27.06.2024)
-------------------

Added a *Plugin System* to the pycomex framework. This is a major new feature which allows to extend the
functionality of the framework in a modular way. The plugin system is custom and implemented via hooks that 
are accessible through a global singleton config instance.

- Added the `pycomex.plugin` module which contains the `Plugin` class and the `PluginManager` class
- Added the `pycomex.config` decorator which can be used to define hooks in the plugin modules
- Added the "weights_biases" plugin which is a simple example of how to use the plugin system. It implements 
  a weights and biases integration for the pycomex experimentation framework. In addition to the local artifact 
  folders it is now also possible to log the resuls to the online dashboard of weights and biases.
- Added some unittests for the config and plugin system

0.11.1 (28.06.2024)
-------------------

- Added the `Experiment.track_many` method which can be conveniently used to track multiple artifacts at once
- Changed the track function generally to store the values in a list instead of replacing the value each time.

0.12.0 (02.07.2024)
-------------------

- Extended the `Experiment.track` method to be able to track figures as well by storing them into a specific 
  folder within the experiment archive folder.
- The `Experiment.metadata` dict now contains the "__track__" entry which is used to store the names of all 
  the tracked quantities.
- Added the `plot_track` plugin which is mainly executed after each experiment and will automatically plot all
  the tracked quantities into separate visualizations. Numeric quantities will be plotted as line plots and
  figures will be stitched together into a video.
- Added `moviepy` to the dependencies

0.12.1 (03.07.2024)
-------------------

- In the wandb plugin: Moved the login of the project into the "after_initialize" hook because there was an issue 
  with not being able to overwrite the WANDB_PROJECT parameter for sub experiments...

0.12.2 (06.08.2024)
-------------------

- Removed the Python 3.10 Union type hint from the experiments module to restore compatibility with Python 3.9
- Added a try block for the loading of plugins such that they re-cast errors as warnings and don't actively break 
  the system such as when an import error in a plugin module occurs (aka we dont want to have to include all the plugin 
  dependencies in the main package)

0.12.3 (06.08.2024)
-------------------

- Ported the notification implementation as a plugin instead of having it in the main code
- Clicking a notification will now open the experiment record folder in the file explorer
- Disabled the notifications for the windows.

0.13.0 (01.10.2024)
-------------------

- Fixed an issue with the experiment command line argument parsing where parameters of sub experiments (defined by 
  Experiment.extend) would not show up in the help message. Solved by re-constructing the ExperimentArgumentParser 
  in the extend method.
- The help command will now also show the default values of experiment parameters (if their string representation is 
  below a certain length.)
- Cleaned up the unittests. In this version all of the unitests actually passed before the publish
- "notify" plugin
  - can now actually be disabled using the `__NOTIFY__` special parameter
- "weights_biases" plugin
  - Now actually correctly handles when the `WANDB_PROJECT` parameter is incorrectly set.
  
0.13.1 (02.10.2024)
-------------------

- Added the special `__PREFIX__` parameter which can be used to add a string prefix to the experiment archive folder 
  name. This is useful for example when running multiple experiments in parallel and you want to distinguish between 
  them in the file system.

0.13.2 (02.10.2024)
-------------------

- Reworked the `ExperimentArgumentParser` 
  - now uses the `rich` package for the rendering of the help message.
  - The parameters are also now ordered alphabetically in the help message.  

0.14.0 (07.11.2024)
-------------------

- Added `reproducible` mode to the experiment, which can be enabled by setting the magic parameter `__REPRODUCIBLE__=True`.
  This mode will export the dependencies of the experiment explicitly into the archive folder as well.
- Added the `reproduce` command to the CLI which can be used to reproduce an experiment run based on the experiment
  archive folder, if the experiment was executed in reproducible mode.
- Switched to using `uv` for development instead of poetry.
- Added the `ActionableParameterType` interface which can be used to define custom type annotations for experiment parameters 
  with custom get and set behavior when interacting with the parameters via the experiment instance.

0.14.1 (07.11.2024)
-------------------

- Added the `uv` dependency to the `pyproject.toml` file

0.14.2 (07.11.2024)
-------------------

- Fixed a bug which caused the experiment to crash if a parameter was defined without a type annotation.

0.15.0 (08.11.2024)
-------------------

- Fixed a bug where `__PREFIX__` did not have an initial value when the experiment object is created
- Added the `Experiment.import_from` class method which can be used to dynamically import the experiment 
  object from the relative/absolute path of an experiment module such that it can subsequently be 
  executed with the "run" method from within another experiment module, for example.
- When adding data to the experiment storage keys which start with an underscore are now excluded from being 
  exported to the persistent JSON file inside the archive folder and can therefore be used to exchange 
  data between hooks for example.


0.16.0 (18.05.2025)
-------------------

- Added the possibility to use pycomex config files to define experiement variations. These config files 
  are YAML file which can be used to `extend` existing experiment python modules and which may be used 
  to overwrite the parameters of the experiment. This change has been motivated by the fact that there are 
  many cases where sub-experiments were defined without implementing any hooks but simply with other parameter 
  values - in which case it is unnecessarily complicated to define a new python module for that.
- Added the `run` command to the CLI which can be used to run an experiment module or a config file 
  from the command line.

0.17.0 (18.06.2025)
-------------------

Command Line Interface

- Added the `template` command group to the CLI which can be used to template various common files.
  - currently only `template analysis` is implemented which will create a new analysis.ipynb notebook 

0.18.0 (08.09.2025)
-------------------

Command Line Interface

- Added the `template experiment` command which can be used to create a new experiment module from a 
  template file.
- Added the `template extend` command which can be used to create a new experiment module which extends
  an existing experiment module.
- Added the `template config` command which can be used to create a new experiment config file which
  extends an existing experiment module.
- Improved the overall `help` message of the command line interface.
- Added the `archive tail` command which can be used to print information about the last few runs that 
  were executed in the archive.

0.19.0 (10.09.2025)
-------------------

Command Line Interface

- Added the `archive compress` command which can be used to compress the results of an experiment run 
  into a zip file.

Utils

- Added the `render_latex_table` function which can be used to render a latex table from a PrettyTable 
  object instance.
- Added `CLAUDE.md` which contains the prompts that were used to generate some of the code 
  in this project using the Claude AI assistant.

Tests

- Fixed the unittests which were broken
- Updated the `noxfile.py` to use `uv` instead of `poetry`

0.19.2 (10.09.2025)
-------------------

- Fixed some problems and styling with the `render_latex_table` util function

0.20.0 (11.09.2025)
-------------------

- Added the `ExperimentCache` class which can be used to cache the results of expensive function calls
  within an experiment. The cache is stored in the experiment archive folder and can be configured to
  use different backends such as `joblib` or `pickle`.
- Added the `Experiment.cache.cached` decorator which can be used to easily cache the results of a function
  within an experiment implementation.
- Added the example `10_caching.py` which demonstrates the caching functionality.
- Applied Ruff formatting

Tests

- Added unittests for the caching functionality

0.21.0 (23.09.2025)
-------------------

Dependencies

- Extended the support of the package from Python 3.8 to Python 3.12 (previously it was only 3.10+)

Cache Control

- Added the ``__CACHING__`` special parameter to control experiment cache behavior. When set to ``False``,
  the cache system will not load existing cached results, forcing recomputation while still saving new
  results to cache. Defaults to ``True`` to maintain backward compatibility.
- Added ``ExperimentCache.set_enabled()`` method to programmatically control cache loading behavior.
- The ``__CACHING__`` parameter can be changed dynamically during experiment execution and takes effect
  immediately.

Logging Methods

- Added the `Experiment.log_parameters` method which can be used to log either all experiment parameters
  or only specific parameters in the format " * {parameter_name}: {parameter_value}". The method includes
  safeguards for complex objects that cannot be directly logged.
- Added the `Experiment.log_pretty` method which uses rich.pretty to log pretty formatted representations
  of complex data structures.

Rich Panel Experiment Logging

- Enhanced experiment start and end logging with Rich panels featuring colored borders, emojis, and improved formatting
- Replaced plain text templates ``functional_experiment_start.out.j2`` and ``functional_experiment_end.out.j2`` with Rich Panel-based logging
- Added ``_create_experiment_start_panel()`` method that generates a green-bordered panel with 🚀 emoji showing namespace, start time, archive path, debug mode, parameters count, Python version, and platform information
- Added ``_create_experiment_end_panel()`` method that generates either a green panel with ✅ emoji (success) or red panel with ❌ emoji (error) showing duration, start/end times, error status, parameters count, and data size
- Added ``console_width`` parameter to Experiment constructor (default: 120) to control panel width and ensure consistent visual presentation
- Panels are now forced to use the exact specified console width with ``expand=True`` and ``width`` parameters
- Duration formatting automatically shows appropriate units (seconds/minutes/hours) based on experiment length
- Data size is displayed in human-readable format (bytes/KB/MB)
- Both console output and log files now display properly rendered Rich panels instead of object representations

CLI

- Added A logo image to be printed to the console in ANSII Art

Tests

- Added comprehensive unit tests for both new logging methods
- Added comprehensive test suite ``TestExperimentRichPanels`` with 8 test cases covering panel creation, console output, log file writing, error handling, duration formatting,
  and console width customization

Documentation

- Added some more documentation
  - `docs/introduction.md` - added instructions on the installation and the quickstart guide
  - `docs/philosophy.md` - added some general information about the philosophy behind the design 
    of the package.
  - `docs/basics_hooks.md` - added some more detailed information about the basic usage 
    of the package and the hook system.