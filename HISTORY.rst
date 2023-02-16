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

* Every experiment file now has a command line interface realized with ``argparse``
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

* Now it is possible to commit matplotlib Figures directly to the experiment with ``Experiment.commit_fig``
* File artifact paths are now automatically tracked as metadata
* Added a default template ``annotations.rst`` to be rendered for each experiment which provides a
  boilerplate starting point for additional thoughts to be added

0.3.0 (17.07.2022)
------------------

* Added ``Experiment.commit_json`` to directly store dict data as json file artifacts for the experiment
  records
* Improved the ``analysis.py`` templating for experiments
    * Using the context manager ``Experiment.analysis`` within the experiment file can be used to not only
      directly execute the analysis right after the experiment is completed but also all the code within
      that context managers content block is copied into the analysis template of that run and it will
      work as it is
    * This is due to the fact, that ``Experiment`` now automatically realizes if it is being imported
      from a ``snapshot.py`` within an existing record folder. In that case it populates internal fields
      such as ``Experiment.data`` by loading the persistent file artifact.
* Added ``examples/analysis.py`` which documents / explains the previously mentioned process

0.3.1 (20.08.2022)
------------------

* Fixed bug that ``e.info()`` could not be used inside the ``analysis.py`` file
* Decided to add ``numpy`` and ``matplotlib`` to the dependencies after all. Originally I did not want to
  include them because I don't strictly need them and they are quite big packages. But honestly, what kind
  of computational experiment works without those two nowadays?
* Renamed the template files with better naming scheme
* Updated readme

0.4.0 (21.08.2022)
------------------

* Added ``pycomex.experiment.ArchivedExperiment`` which makes it possible to load an arbitrary experiment
  instance from the archived folder and use it much like it is possible from within ``analysis.py``
* Added ``pycomex.experiment.ExperimentRegistry`` which can be used to load an experiment base path and
  automatically discover all the (nested) namespace folders within which contain actual experiment run
  archives.
    * Added ``pycomex.experiment.NamespaceFolder`` which represents and allows to work with namespace
      folders, for example by easily getting the ``ArchivedExperiment`` instance according to an experiment
      run (numeric) index.
* Added ``psutil`` to dependencies to implement hardware resource monitoring as an additional feature
  when printing the intermediate status of the experiment run with ``Experiment.status()``

0.4.1 (12.09.2022)
------------------

* Fixed a bug which broke the ``with e.analysis:`` functionality in Python 3.10. Rewrote ``RecordCode``
  such that it no longer uses the deprecated functionality and now also works for the new version.
* ``with e.analysis:`` can now also be used on the indent level as the experiment context manager itself
  which is more intuitive. Using it this way also solves some unwanted interaction with the error catching
  behavior of the experiment context.

0.5.0 (14.09.2022)
------------------

* By fixing the previous bug, I introduced a new one: Essentially now that I moved the analysis context
  manager to the same logical level as the experiment context manager I was facing the same problem: It got
  executed when merely importing the module, which had all sorts of bad side effects. This bug is fixed now.
* While fixing that bug, I accidentally stumbled on a much better method of how to make context managers
  skippable, which I find so good that I moved the experiment context manager to use the same mechanism
  as well, which gets rid of the need for calling ``Experiment.prepare()``. But this means some
  backwards incompatible API changes.

0.5.1 (14.09.2022)
------------------

* If numpy arrays are added to the internal data store, they are automatically converted to lists, so that
  they can be json serialized later.

0.5.2 (18.09.2022)
------------------

* Extended ``run_experiment`` such that it can be called in a non-blocking manner and such that it relays
  the output of the experiment subprocess to stdout in the main process

0.6.0 (19.09.2022)
------------------

* Added ``pycomex.cli.ExperimentCLI`` class which can be used to automatically create a computational
  experiment command line interface for a project by simply providing the folder path at which all the
  experiment modules are located. They will automatically be discovered and the CLI will automatically
  be built based on those experiments. Currently supported are ``list`` command which will
  show an overview of experiments, ``info`` which will print more details and ``run`` which will prompt
  the execution of an experiment.
* Made some changes in the ``Experiment`` class. Most importantly it now sets ``__experiment__`` global
  variable in the original module namespace, which makes it easier to detect whether any given
  python module contains an experiment or not.

0.6.1 (28.11.2022)
------------------

* Fixed a bug where numpy arrays within the storage would cause an exception during the serialization
  process by using a custom json encoder class which first converts all numpy arrays to nested lists

0.7.0 (03.01.2023)
------------------

* Added the ``experiment.SubExperiment`` class which implements experiment inheritance! This class now
  allows to refer to a different experiment module to run as parent experiment, but with parameter
  modifications.
* Added a hook system to experiments, which allows for parent experiment modules to define certain points
  at which custom code from child experiments may be injected.

* changed the datetime format in ``HISTORY.rst`` to the only sane option
* Fixed a minor windows compatibility problem with the automatic pathing determining for experiments.
* Added the module ``pycomex.testing`` to contain all of the utility functions and classes which are needed
  to facilitate the unittests such as the ``ExperimentIsolation`` context manager.
* Refactored most unittests to use ``pytest`` instead of ``unittest``
* Fixed a bunch of unittests that were not updated for the new API
* Fixed a rather serious bug in ``testing.ExperimentIsolation`` which left permanent modifications in
  in the globals dict and thus introduced side-effects in between different unittests.

**INTERFACE CHANGES**

* changed functionality and signature of ``experiment.run_experiment``. Previously this function executed
  an existing experiment module by using ``subprocessing.run`` and returned the completed process instance.
  Now, this works by using ``experiment.SubExperiment`` and the function actually returns an experiment
  instance.
* Do to the change above, the same now applies to ``experiment.run_example``.

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
  via the special ``DEPENDENCY_PATHS`` dict parameter. These files will be copied into the created archive
  folders.

0.8.1 (27.01.2023)
------------------

* Added ``Experiment.p`` as a shorthand for ``Experiment.parameters`` because that got really annoying to
  write so often.
* Fixed a serious bug, where the ``snapshot.py`` file in the archive folder of an experiment was not in
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
