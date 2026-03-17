# Changelog

## 0.28.2 (2026-03-17)

### Bug Fixes

- Fixed a bug where the `INHERIT` import artifact would escape cleanup in multi-level
  inheritance chains (Base -> Middle -> Grandchild) when both middle and grandchild
  experiments do `from pycomex import INHERIT`. The artifact's `parent_value` would point
  to the middle level's own unresolved artifact instead of being `_UNSET`, causing the
  `_UNSET`-based cleanup condition to miss it and raising a spurious `InheritError` at
  runtime. Fixed by making the `name == 'INHERIT'` check unconditional — a parameter
  literally named `INHERIT` is always an import artifact regardless of its internal state.
- Fixed a bug where `PARAM = INHERIT(lambda x: x * 2)` in a direct experiment (not
  created via `Experiment.extend()`) would be silently removed instead of raising
  `InheritError`. The `Inherit` object created by `INHERIT(fn)` bypassed the
  sentinel-to-Inherit conversion where `_from_sentinel` gets set, causing the artifact
  cleanup to misidentify it as an import artifact. Fixed by marking all user-created
  `Inherit` objects with `_from_sentinel=True` during parameter processing.

## 0.28.1 (2026-02-12)

### Bug Fixes

- Fixed a bug where `from pycomex import INHERIT` in a sub-experiment would cause an
  `InheritError` at runtime. The `INHERIT` name is uppercase, so parameter discovery
  treated it as a real parameter. The import artifact cleanup failed to catch this case
  because the `_from_sentinel` marker was set to `True` during sentinel-to-Inherit
  conversion, making the cleanup logic treat it as a genuine user assignment. Fixed by
  explicitly checking for the parameter name `"INHERIT"`, which is always an import
  artifact.
- `InheritError` messages now include the name of the parameter that failed to resolve.

## 0.28.0 (2026-02-11)

### Experiment Features

- Added the `INHERIT` sentinel value for explicit parameter inheritance in sub-experiments.
  When extending a parent experiment with `Experiment.extend()`, sub-experiments can now use
  `INHERIT` to explicitly reference the parent's parameter value, optionally applying a
  transformation function. This enables patterns like doubling a learning rate
  (`LEARNING_RATE = INHERIT(lambda x: x * 2)`) or extending a list parameter
  (`DATA_PATHS = INHERIT(lambda x: x + ["/extra/path"])`). `INHERIT` works across
  arbitrary levels of experiment inheritance and resolves lazily at experiment start time,
  correctly interacting with CLI overrides and other late parameter modifications.
- Added the `pycomex.functional.inherit` module containing the `INHERIT` singleton,
  `Inherit` value class, `InheritBase` base class, and `InheritError` exception.
- Added architecture decision record `docs/architecture_decisions/06_inherit_parameter_sentinel.md`.

### Bug Fixes

- Fixed a bug where `Experiment.extend()` would crash with
  `TypeError: object of type 'function' has no len()` when the base experiment uses
  the `@experiment.testing` decorator. The root cause was that `Experiment.testing()`
  stored the callback as a bare function in `hook_map`, while `read_module_metadata()`
  assumed all `hook_map` entries are lists. Fixed by wrapping the testing callback in a
  list, consistent with `Experiment.hook()`.

## 0.27.0 (2025-11-13)

### Experiment Features

- Added the `__INCLUDE__` special parameter which allows to specify experiment
  mixin modules to be included. This crucially allows to supply mixins via the
  command line calling of experiment modules.
- Added another line to the end of experiment panel which directly links to the
  experiment archive folder.

## 0.26.2 (2025-11-10)

- Removed the debug messages that were shown when a plugin failed to load.

## 0.26.1 (2025-10-31)

### Bug Fixes

- Fixed a display bug in the `optuna info` command

### Plugins

- Added the `optuna report` command which can be used to generate some standard plots
  for an existing optuna study such as optimization history, parameter importance etc.
- Added some unittests for the optuna report functionality

### Testing

- Re-organized the folder structure for the unittests to now have a more clear
  separation between tests for the core functionality and tests for the plugins.

## 0.26.0 (2025-10-21)

### Command Line Interface

- Added the "pycomex archive scan" command which can be used to analyze the contents of an
  experiment archive by grouping the experiments by certain group selection keys and
  showing the properties of these groups in a table in the output.
- Changed the --help string to now display all of the commands in a flat manner instead
  of the individual command groups.
- Modified the command line interface to now also load the Plugin Manager during the construction
  of the `CLI` class and added a system hook which allows plugins to inject custom command line
  commands to the CLI.

### Plugins

- Added the `OptunaPlugin` which can be used to directly facilitate Optuna hyperparameter optimization
  for experiment modules.
  - Extended the command line interface with the new `optuna` command group which can be used to
    start optimization experiments, inspect existing studies, view information about hyperparameter sweeps etc.
  - Is not installed by default - can be installed with the `pycomex[full]` suite

### Bug Fixes

- When the `__CACHING__ = False` is set, the cached functions no longer save to the cache, which
  was previously the case.

## 0.25.1 (2025-10-16)

### Bug Fixes

- Fixed a bug where the `pycomex run` command on a config file would produce an archive where the
  config yaml file content would be copied into the "experiment_code.py" file instead of the
  actual base experiment module code.

## 0.25.0 (2025-10-13)

### Refactoring

- Added the `functional/base.py` module which contains the `ExperimentBase` class which now
  acts as the base class for `Experiment` and `ExperimentMixin` to manage the joint features
  regarding the hook system and the parameter discovery mechanism.
- Removed the old, non-functional experiment system which was based on the context manager API
  from the code completely now.
  - Removed the `experiment.py` module
  - Removed the `work.py` module
  - Removed several test cases and test assets
  - Removed the corresponding elements from the `utils.py` module
- Split the 3000+ lines long monolithic `cli.py` module into several smaller modules within the
  new `cli/` sub package.

### Experiment Logging

- The experiment start and end panels now use `rich` to make the output look pretty
- The `log_parameters` now uses `rich` to make the output look pretty

### Experiment Mixins

- Added the `ExperimentMixin` class which can be used to define reusable mixins for experiments.
  Mixins can define parameters and hooks just like experiments and can be added to an experiment
  with the `Experiment.include` method. These mixins can be used to share hook implementations
  outside of the experiment inheritance system.
- Added the `examples/11_experiment_mixins.py` example which demonstrates the usage of experiment
  experiment mixins.
- Added documentation about experiment mixins to `docs/basics_mixins.md`
- Added various unittests for the experiment mixin functionality

### Bug Fixes

- Fixed a bug where the command line override of experiment parameters with the `pycomex run` command
  did not work correctly for the special parameters such as `__DEBUG__` or `__PREFIX__` since it was
  not calling the `Experiment.set_special_parameter` method.

## 0.24.0 (2025-10-09)

### CLI

- Added the `archive modify` command which can be used to batch-modify parameters or metadata
  of archived experiments. Supports `--select` for filtering, `--modify-parameters` and
  `--modify-metadata` for applying Python code modifications, `--dry-run` for previewing
  changes, and `--verbose` for detailed progress output.

### Miscellaneous

- Added the `vscode_extension` folder which implements a custom VSCode extension for pycomex
  can be used to directly start pycomex config yaml files from the editor window as well as
  changes the icon for the results folder archive to a custom icon.

### Documentation

- Moved the documentation files from the `docs/docs` folder to the root `docs` folder
  to make it easier to find them.
- Moved the `docs/mkdocs.yml` file to the root folder.
- Added a documentation page which introduces the VSCode extension and explains the features.

## 0.23.1 (2025-09-30)

### Bug Fixes

- Fixed a display bug in the `archive overview` command
- The `archive list` command is now sorted by the experiment start time
- The caching mechanism now unzips the files into a unique temporary file which is not inside
  the cache folder itself. Because for multiple parallel experiments this previously led to
  cache collisions and exceptions in some rare cases.
- Removed the warning about the deprecated pkg_resources library which was printed at the beginning
  of each command.

## 0.23.0 (2025-09-30)

### CLI

- Added the `archive list` command which can be used to list the archive folder locations of
  all the experiments in the archive or a subset using the `--select` option.
- Added another panel to the `archive overview` command which shows the most common error types
  among the failed experiments.

## 0.22.0 (2025-09-29)

### CLI

- Renamed the `archive info` command to `archive overview` to better reflect what it is
  about
- Added a new `archive info` command which can be used to print the summary statistics of the
  full experiment archive or a subset of the experiment archive using the `--select` option.

## 0.21.0 (2025-09-23)

### Dependencies

- Extended the support of the package from Python 3.8 to Python 3.12 (previously it was only 3.10+)

### Cache Control

- Added the `__CACHING__` special parameter to control experiment cache behavior. When set to `False`,
  the cache system will not load existing cached results, forcing recomputation while still saving new
  results to cache. Defaults to `True` to maintain backward compatibility.
- Added `ExperimentCache.set_enabled()` method to programmatically control cache loading behavior.
- The `__CACHING__` parameter can be changed dynamically during experiment execution and takes effect
  immediately.

### Logging Methods

- Added the `Experiment.log_parameters` method which can be used to log either all experiment parameters
  or only specific parameters in the format " * {parameter_name}: {parameter_value}". The method includes
  safeguards for complex objects that cannot be directly logged.
- Added the `Experiment.log_pretty` method which uses rich.pretty to log pretty formatted representations
  of complex data structures.

### Rich Panel Experiment Logging

- Enhanced experiment start and end logging with Rich panels featuring colored borders, emojis, and improved formatting
- Replaced plain text templates `functional_experiment_start.out.j2` and `functional_experiment_end.out.j2` with Rich Panel-based logging
- Added `_create_experiment_start_panel()` method that generates a green-bordered panel with emojis showing namespace, start time, archive path, debug mode, parameters count, Python version, and platform information
- Added `_create_experiment_end_panel()` method that generates either a green panel (success) or red panel (error) showing duration, start/end times, error status, parameters count, and data size
- Added `console_width` parameter to Experiment constructor (default: 120) to control panel width and ensure consistent visual presentation
- Panels are now forced to use the exact specified console width with `expand=True` and `width` parameters
- Duration formatting automatically shows appropriate units (seconds/minutes/hours) based on experiment length
- Data size is displayed in human-readable format (bytes/KB/MB)
- Both console output and log files now display properly rendered Rich panels instead of object representations

### CLI

- Added a logo image to be printed to the console in ANSI Art

### Tests

- Added comprehensive unit tests for both new logging methods
- Added comprehensive test suite `TestExperimentRichPanels` with 8 test cases covering panel creation, console output, log file writing, error handling, duration formatting,
  and console width customization

### Documentation

- Added some more documentation
  - `docs/introduction.md` - added instructions on the installation and the quickstart guide
  - `docs/philosophy.md` - added some general information about the philosophy behind the design
    of the package.
  - `docs/basics_hooks.md` - added some more detailed information about the basic usage
    of the package and the hook system.

## 0.20.0 (2025-09-11)

- Added the `ExperimentCache` class which can be used to cache the results of expensive function calls
  within an experiment. The cache is stored in the experiment archive folder and can be configured to
  use different backends such as `joblib` or `pickle`.
- Added the `Experiment.cache.cached` decorator which can be used to easily cache the results of a function
  within an experiment implementation.
- Added the example `10_caching.py` which demonstrates the caching functionality.
- Applied Ruff formatting

### Tests

- Added unittests for the caching functionality

## 0.19.2 (2025-09-10)

- Fixed some problems and styling with the `render_latex_table` util function

## 0.19.0 (2025-09-10)

### Command Line Interface

- Added the `archive compress` command which can be used to compress the results of an experiment run
  into a zip file.

### Utils

- Added the `render_latex_table` function which can be used to render a latex table from a PrettyTable
  object instance.
- Added `CLAUDE.md` which contains the prompts that were used to generate some of the code
  in this project using the Claude AI assistant.

### Tests

- Fixed the unittests which were broken
- Updated the `noxfile.py` to use `uv` instead of `poetry`

## 0.18.0 (2025-09-08)

### Command Line Interface

- Added the `template experiment` command which can be used to create a new experiment module from a
  template file.
- Added the `template extend` command which can be used to create a new experiment module which extends
  an existing experiment module.
- Added the `template config` command which can be used to create a new experiment config file which
  extends an existing experiment module.
- Improved the overall `help` message of the command line interface.
- Added the `archive tail` command which can be used to print information about the last few runs that
  were executed in the archive.

## 0.17.0 (2025-06-18)

### Command Line Interface

- Added the `template` command group to the CLI which can be used to template various common files.
  - Currently only `template analysis` is implemented which will create a new analysis.ipynb notebook

## 0.16.0 (2025-05-18)

- Added the possibility to use pycomex config files to define experiment variations. These config files
  are YAML files which can be used to `extend` existing experiment python modules and which may be used
  to overwrite the parameters of the experiment. This change has been motivated by the fact that there are
  many cases where sub-experiments were defined without implementing any hooks but simply with other parameter
  values - in which case it is unnecessarily complicated to define a new python module for that.
- Added the `run` command to the CLI which can be used to run an experiment module or a config file
  from the command line.

## 0.15.0 (2024-11-08)

- Fixed a bug where `__PREFIX__` did not have an initial value when the experiment object is created
- Added the `Experiment.import_from` class method which can be used to dynamically import the experiment
  object from the relative/absolute path of an experiment module such that it can subsequently be
  executed with the "run" method from within another experiment module, for example.
- When adding data to the experiment storage keys which start with an underscore are now excluded from being
  exported to the persistent JSON file inside the archive folder and can therefore be used to exchange
  data between hooks for example.

## 0.14.2 (2024-11-07)

- Fixed a bug which caused the experiment to crash if a parameter was defined without a type annotation.

## 0.14.1 (2024-11-07)

- Added the `uv` dependency to the `pyproject.toml` file

## 0.14.0 (2024-11-07)

- Added `reproducible` mode to the experiment, which can be enabled by setting the magic parameter `__REPRODUCIBLE__=True`.
  This mode will export the dependencies of the experiment explicitly into the archive folder as well.
- Added the `reproduce` command to the CLI which can be used to reproduce an experiment run based on the experiment
  archive folder, if the experiment was executed in reproducible mode.
- Switched to using `uv` for development instead of poetry.
- Added the `ActionableParameterType` interface which can be used to define custom type annotations for experiment parameters
  with custom get and set behavior when interacting with the parameters via the experiment instance.

## 0.13.2 (2024-10-02)

- Reworked the `ExperimentArgumentParser`
  - Now uses the `rich` package for the rendering of the help message.
  - The parameters are also now ordered alphabetically in the help message.

## 0.13.1 (2024-10-02)

- Added the special `__PREFIX__` parameter which can be used to add a string prefix to the experiment archive folder
  name. This is useful for example when running multiple experiments in parallel and you want to distinguish between
  them in the file system.

## 0.13.0 (2024-10-01)

- Fixed an issue with the experiment command line argument parsing where parameters of sub experiments (defined by
  Experiment.extend) would not show up in the help message. Solved by re-constructing the ExperimentArgumentParser
  in the extend method.
- The help command will now also show the default values of experiment parameters (if their string representation is
  below a certain length.)
- Cleaned up the unittests. In this version all of the unittests actually passed before the publish
- "notify" plugin
  - Can now actually be disabled using the `__NOTIFY__` special parameter
- "weights_biases" plugin
  - Now actually correctly handles when the `WANDB_PROJECT` parameter is incorrectly set.

## 0.12.3 (2024-08-06)

- Ported the notification implementation as a plugin instead of having it in the main code
- Clicking a notification will now open the experiment record folder in the file explorer
- Disabled the notifications for Windows.

## 0.12.2 (2024-08-06)

- Removed the Python 3.10 Union type hint from the experiments module to restore compatibility with Python 3.9
- Added a try block for the loading of plugins such that they re-cast errors as warnings and don't actively break
  the system such as when an import error in a plugin module occurs (aka we don't want to have to include all the plugin
  dependencies in the main package)

## 0.12.1 (2024-07-03)

- In the wandb plugin: Moved the login of the project into the "after_initialize" hook because there was an issue
  with not being able to overwrite the WANDB_PROJECT parameter for sub experiments...

## 0.12.0 (2024-07-02)

- Extended the `Experiment.track` method to be able to track figures as well by storing them into a specific
  folder within the experiment archive folder.
- The `Experiment.metadata` dict now contains the "__track__" entry which is used to store the names of all
  the tracked quantities.
- Added the `plot_track` plugin which is mainly executed after each experiment and will automatically plot all
  the tracked quantities into separate visualizations. Numeric quantities will be plotted as line plots and
  figures will be stitched together into a video.
- Added `moviepy` to the dependencies

## 0.11.1 (2024-06-28)

- Added the `Experiment.track_many` method which can be conveniently used to track multiple artifacts at once
- Changed the track function generally to store the values in a list instead of replacing the value each time.

## 0.11.0 (2024-06-27)

- Added a *Plugin System* to the pycomex framework. This is a major new feature which allows to extend the
  functionality of the framework in a modular way. The plugin system is custom and implemented via hooks that
  are accessible through a global singleton config instance.
- Added the `pycomex.plugin` module which contains the `Plugin` class and the `PluginManager` class
- Added the `pycomex.config` decorator which can be used to define hooks in the plugin modules
- Added the "weights_biases" plugin which is a simple example of how to use the plugin system. It implements
  a weights and biases integration for the pycomex experimentation framework. In addition to the local artifact
  folders it is now also possible to log the results to the online dashboard of weights and biases.
- Added some unittests for the config and plugin system

## 0.10.2 (2023-11-08)

- Fixed a crucial bug that would break the experiment modules if no module level doc string exists
- Added the `get_experiment` method which allows to easily get the Experiment object instance based
  on a given absolute experiment module path.
- Added the example `07_meta_experiments.py`

## 0.10.1 (2023-11-05)

- Fixed a breaking bug during the construction of Experiment instances
- Added information about possible hooks to the `info` cli command as well

## 0.10.0 (2023-10-27)

Added the "testing" functionality as its own feature to the Experiment class

- It is now possible to define the hook with the necessary code to put the experiment into testing mode using
  the `Experiment.testing` function and the `__TESTING__` magic parameter.
- Added a dedicated example that illustrates the testing mode `05_testing_mode.py`

### Command Line Interface

- Fixed the command line interface. `ExperimentCLI` should now be working with the new pycomex functional API
- Switched to using python `rich` package for the CLI printing
- Changed the styling of the "list" and "info" commands to rich formatting

### Other Changes

- During construction an `Experiment` instance will now attempt to automatically parse the parameter description strings from the
  module's comments and the parameter typing information from the type hints annotations dict. This information will then be stored
  in `Experiment.metadata` dictionary.
- Added some more docstrings
- Updated the `README.rst`
- Added the `DOCUMENTATION.rst` and started to compile some additional documentation that is not immediately
  relevant to the README

## 0.9.5 (2023-07-04)

- Changed the name of the experiment file copy that is placed in the artifacts folder from "code.py"
  to "experiment_code.py" because there was a very weird naming collision with tensorflow internals
- Also adjusted the analysis file template accordingly.

## 0.9.4 (2023-05-08)

- In the functional interface, added the crucial feature of default hook implementations
- Fixed an important bug to make analysis.py files work with sub experiments

## 0.9.3 (2023-05-05)

- Fixed an important bug in `dynamic_import` which prevented `inspect` from working properly in the
  imported modules

## 0.9.2 (2023-04-28)

- Fixed a bug that sub experiment modules with relative paths to base experiments would cause errors when
  the current working directory was not their parent directory

## 0.9.1 (2023-04-28)

CRITICAL FIX: The previous package did not actually contain the "functional" sub package, but this one
does now!

- Added some more functionalities to `functional.Experiment`
- Changed all the example files to use the functional interface now
- Some more code documentation

## 0.9.0 (2023-04-27)

Introduced the new **functional API**. This is a completely new way to use the pycomex framework which
will slowly replace the old way. In this new method the whole thing is implemented with decorators instead
of context managers, which makes the entire implementation approximately 100x easier and less riddled with
side effects and bugs.

- Already changed the README example to use the functional API
- Slowly started replacing the examples with the functional API

## 0.8.7 (2023-03-27)

- Fixed a bug where the inspect module would not be working correctly in executions of SubExperiment
- Fixed the version dependency for "click"
- Fixed the version dependency for "numpy"

## 0.8.4 (2023-02-16)

- Added the feature of "parameter hooks". Now it is possible to register a hook with the name of a parameter
  in a sub experiment to modify that parameter before the start of the experiment...

## 0.8.3 (2023-02-13)

- Fixed the problem that when an exception occurs within the RecordCode context manager that this is not
  properly printed. Now the entire traceback for every error is printed to the logger stream
- Moved the entire analysis RecordCode functionality from Experiment to AbstractExperiment so that it
  can also be used in SubExperiment
- Fixed the bug that the analysis.py file within the archive folder would not work at all for
  SubExperiment runs
- SubExperiments can now also define analysis context and those will be additive, meaning that the code
  from those will be added to the end of all the analysis code that was previously created by the parent
  experiment

## 0.8.2 (2023-02-09)

- Updated Readme file

## 0.8.1 (2023-01-27)

- Added `Experiment.p` as a shorthand for `Experiment.parameters` because that got really annoying to
  write so often.
- Fixed a serious bug, where the `snapshot.py` file in the archive folder of an experiment was not in
  fact the sub experiment but the lowest level base experiment!

## 0.8.0 (2023-01-20)

- Removed the standard prints during the call of a hook, because they proved annoying in practice.
- Fixed the bug, where a sub experiment snapshot would not be executable because it was missing the
  base experiment. The base experiment script is now copied into the archive folder as well.
- Added the dependency system: It is now possible to define files which an experiment execution depends on
  via the special `DEPENDENCY_PATHS` dict parameter. These files will be copied into the created archive
  folders.

## 0.7.1 (2023-01-17)

- Slightly changed the hook mechanic to allow the possibility of defining overwritable default
  implementations for hooks.

## 0.7.0 (2023-01-03)

- Added the `experiment.SubExperiment` class which implements experiment inheritance! This class now
  allows to refer to a different experiment module to run as parent experiment, but with parameter
  modifications.
- Added a hook system to experiments, which allows for parent experiment modules to define certain points
  at which custom code from child experiments may be injected.
- Changed the datetime format in `HISTORY.rst` to the only sane option
- Fixed a minor windows compatibility problem with the automatic pathing determining for experiments.
- Added the module `pycomex.testing` to contain all of the utility functions and classes which are needed
  to facilitate the unittests such as the `ExperimentIsolation` context manager.
- Refactored most unittests to use `pytest` instead of `unittest`
- Fixed a bunch of unittests that were not updated for the new API
- Fixed a rather serious bug in `testing.ExperimentIsolation` which left permanent modifications in
  the globals dict and thus introduced side-effects in between different unittests.

### Interface Changes

- Changed functionality and signature of `experiment.run_experiment`. Previously this function executed
  an existing experiment module by using `subprocessing.run` and returned the completed process instance.
  Now, this works by using `experiment.SubExperiment` and the function actually returns an experiment
  instance.
- Due to the change above, the same now applies to `experiment.run_example`.

## 0.6.1 (2022-11-28)

- Fixed a bug where numpy arrays within the storage would cause an exception during the serialization
  process by using a custom json encoder class which first converts all numpy arrays to nested lists

## 0.6.0 (2022-09-19)

- Added `pycomex.cli.ExperimentCLI` class which can be used to automatically create a computational
  experiment command line interface for a project by simply providing the folder path at which all the
  experiment modules are located. They will automatically be discovered and the CLI will automatically
  be built based on those experiments. Currently supported are `list` command which will
  show an overview of experiments, `info` which will print more details and `run` which will prompt
  the execution of an experiment.
- Made some changes in the `Experiment` class. Most importantly it now sets `__experiment__` global
  variable in the original module namespace, which makes it easier to detect whether any given
  python module contains an experiment or not.

## 0.5.2 (2022-09-18)

- Extended `run_experiment` such that it can be called in a non-blocking manner and such that it relays
  the output of the experiment subprocess to stdout in the main process

## 0.5.1 (2022-09-14)

- If numpy arrays are added to the internal data store, they are automatically converted to lists, so that
  they can be json serialized later.

## 0.5.0 (2022-09-14)

- By fixing the previous bug, a new one was introduced: Essentially now that the analysis context
  manager was moved to the same logical level as the experiment context manager, it got
  executed when merely importing the module, which had all sorts of bad side effects. This bug is fixed now.
- While fixing that bug, a much better method of how to make context managers
  skippable was discovered, which was so good that the experiment context manager was moved to use the same mechanism
  as well, which gets rid of the need for calling `Experiment.prepare()`. But this means some
  backwards incompatible API changes.

## 0.4.1 (2022-09-12)

- Fixed a bug which broke the `with e.analysis:` functionality in Python 3.10. Rewrote `RecordCode`
  such that it no longer uses the deprecated functionality and now also works for the new version.
- `with e.analysis:` can now also be used on the indent level as the experiment context manager itself
  which is more intuitive. Using it this way also solves some unwanted interaction with the error catching
  behavior of the experiment context.

## 0.4.0 (2022-08-21)

- Added `pycomex.experiment.ArchivedExperiment` which makes it possible to load an arbitrary experiment
  instance from the archived folder and use it much like it is possible from within `analysis.py`
- Added `pycomex.experiment.ExperimentRegistry` which can be used to load an experiment base path and
  automatically discover all the (nested) namespace folders within which contain actual experiment run
  archives.
  - Added `pycomex.experiment.NamespaceFolder` which represents and allows to work with namespace
    folders, for example by easily getting the `ArchivedExperiment` instance according to an experiment
    run (numeric) index.
- Added `psutil` to dependencies to implement hardware resource monitoring as an additional feature
  when printing the intermediate status of the experiment run with `Experiment.status()`

## 0.3.1 (2022-08-20)

- Fixed bug that `e.info()` could not be used inside the `analysis.py` file
- Decided to add `numpy` and `matplotlib` to the dependencies after all. Originally I did not want to
  include them because I don't strictly need them and they are quite big packages. But honestly, what kind
  of computational experiment works without those two nowadays?
- Renamed the template files with better naming scheme
- Updated readme

## 0.3.0 (2022-07-17)

- Added `Experiment.commit_json` to directly store dict data as json file artifacts for the experiment
  records
- Improved the `analysis.py` templating for experiments
  - Using the context manager `Experiment.analysis` within the experiment file can be used to not only
    directly execute the analysis right after the experiment is completed but also all the code within
    that context managers content block is copied into the analysis template of that run and it will
    work as it is
  - This is due to the fact, that `Experiment` now automatically realizes if it is being imported
    from a `snapshot.py` within an existing record folder. In that case it populates internal fields
    such as `Experiment.data` by loading the persistent file artifact.
- Added `examples/analysis.py` which documents / explains the previously mentioned process

## 0.2.1 (2022-07-12)

- Now it is possible to commit matplotlib Figures directly to the experiment with `Experiment.commit_fig`
- File artifact paths are now automatically tracked as metadata
- Added a default template `annotations.rst` to be rendered for each experiment which provides a
  boilerplate starting point for additional thoughts to be added

## 0.2.0 (2022-07-12)

- Every experiment file now has a command line interface realized with `argparse`
  - It is possible to pass in either a .JSON or a .PY file which are able to modify the default
    experiment parameters defined in the experiment file
  - It is possible to retrieve the destination path when invoking an experiment file over the command line
- A copy of the actual experiment file is copied as a snapshot to the experiment record folder
- It is possible to define additional jinja templates which are rendered as additional files into the
  experiment record folder
  - One default template which is rendered this way is "analysis.py" module, which provides a boilerplate
    starting point for further analysis on the experiment results.

## 0.1.1 (2022-07-11)

- Added the "poetry_bumpversion" plugin https://github.com/monim67/poetry-bumpversion to update the version
  strings in all the relevant files
- Using "black" for code formatting
- Using "flake9" for linting

## 0.1.0 (2022-07-09)

- First release on PyPI.
