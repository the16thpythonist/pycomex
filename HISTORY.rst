=======
History
=======

0.1.0 (2022-07-09)
------------------

* First release on PyPI.

0.1.1 (2022-07-11)
------------------

* Added the "poetry_bumpversion" plugin https://github.com/monim67/poetry-bumpversion to update the version
  strings in all the relevant files
* Using "black" for code formatting
* Using "flake9" for linting

0.2.0 (2022-07-12)
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

0.2.1 (2022-07-12)
------------------

* Now it is possible to commit matplotlib Figures directly to the experiment with ``Experiment.commit_fig``
* File artifact paths are now automatically tracked as metadata
* Added a default template ``annotations.rst`` to be rendered for each experiment which provides a
  boilerplate starting point for additional thoughts to be added

0.3.0 (2022-07-17)
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

0.3.1 (2022-08-20)
------------------

* Fixed bug that ``e.info()`` could not be used inside the ``analysis.py`` file
* Decided to add ``numpy`` and ``matplotlib`` to the dependencies after all. Originally I did not want to
  include them because I don't strictly need them and they are quite big packages. But honestly, what kind
  of computational experiment works without those two nowadays?
* Renamed the template files with better naming scheme
* Updated readme

0.4.0 (2022-08-21)
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

0.4.1 (2022-09-12)
------------------

* Fixed a bug which broke the ``with e.analysis:`` functionality in Python 3.10. Rewrote ``RecordCode``
  such that it no longer uses the deprecated functionality and now also works for the new version.
* ``with e.analysis:`` can now also be used on the indent level as the experiment context manager itself
  which is more intuitive. Using it this way also solves some unwanted interaction with the error catching
  behavior of the experiment context.

0.5.0 (2022-09-14)
------------------

* By fixing the previous bug, I introduced a new one: Essentially now that I moved the analysis context
  manager to the same logical level as the experiment context manager I was facing the same problem: It got
  executed when merely importing the module, which had all sorts of bad side effects. This bug is fixed now.
* While fixing that bug, I accidentally stumbled on a much better method of how to make context managers
  skippable, which I find so good that I moved the experiment context manager to use the same mechanism
  as well, which gets rid of the need for calling ``Experiment.prepare()``. But this means some
  backwards incompatible API changes.

0.5.1 (2022-09-14)
------------------

* If numpy arrays are added to the internal data store, they are automatically converted to lists, so that
  they can be json serialized later.

0.5.2 (2022-09-18)
------------------

* Extended ``run_experiment`` such that it can be called in a non-blocking manner and such that it relays
  the output of the experiment subprocess to stdout in the main process

