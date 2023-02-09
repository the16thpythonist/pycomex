.. image:: https://img.shields.io/pypi/v/pycomex.svg
        :target: https://pypi.python.org/pypi/pycomex

.. image:: https://readthedocs.org/projects/pycomex/badge/?version=latest
        :target: https://pycomex.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status

PyComex - Python Computational Experiments
================================================

Microframework to improve the experience of running and managing records of computational experiments,
such as machine learning and data science experiments, in Python.

* Free software: MIT license

Features
--------

* Automatically create (nested) folder structure for results of each run of an experiment
* Simply attach metadata such as performance metrics to experiment object and they will be automatically
  stored as JSON file
* Easily attach file artifacts such as ``matplotlib`` figures to experiment records
* Log messages to stdout as well as permanently store into log file
* Ready-to-use automatically generated boilerplate code for the analysis and post-processing of
  experiment data after experiments have terminated.
* Experiment inheritance: Experiment modules can inherit from other modules and extend their functionality
  via parameter overwrites and hooks!

Installation
------------

Install stable version with ``pip``

.. code-block:: console

    pip3 install pycomex

Or the most recent development version

.. code-block:: console

    git clone https://github.com/the16thpythonist/pycomex.git
    cd pycomex ; pip3 install .

Quickstart
----------

Each computational experiment has to be bundled as a standalone python module. Important experiment
parameters are placed at the top. Actual execution of the experiment is placed within the ``Experiment``
context manager.

Upon entering the context, a new archive folder for each run of the experiment is created.

Archiving of metadata, file artifacts and error handling is automatically managed on context exit.

.. code-block:: python

    # quickstart.py
    """
    This doc string will be saved as the "description" meta data of the experiment records
    """
    import os
    from pycomex.experiment import Experiment
    from pycomex.util import Skippable

    # Experiment parameters can simply be defined as uppercase global variables.
    # These are automatically detected and can possibly be overwritten in command
    # line invocation
    HELLO = "hello "
    WORLD = "world!"

    # Experiment context manager needs 3 positional arguments:
    # - Path to an existing folder in which to store the results
    # - A namespace name unique for each experiment
    # - access to the local globals() dict
    with Skippable(), (e := Experiment(os.getcwd(), "results/example/quickstart", globals())):

        # Internally saved into automatically created nested dict
        # {'strings': {'hello_world': '...'}}
        e["strings/hello_world"] = HELLO + WORLD

        # Alternative to "print". Message is printed to stdout as well as
        # recorded to log file
        e.info("some debug message")

        # Automatically saves text file artifact to the experiment record folder
        file_name = "hello_world.txt"
        e.commit_raw(file_name, HELLO + WORLD)
        # e.commit_fig(file_name, fig)
        # e.commit_png(file_name, image)
        # ...

    # All the code inside this context will be copied to the "analysis.py"
    # file which will be created as an experiment artifact.
    with Skippable(), e.analysis:
        # And we can access all the internal fields of the experiment object
        # and the experiment parameters here!
        print(HELLO, WORLD)
        print(e['strings/hello_world'])
        # logging will print to stdout but not modify the log file
        e.info('analysis done')

This example would create the following folder structure:

.. code-block:: python

    cwd
    |- results
       |- example
          |- 000
             |+ experiment_log.txt     # Contains all the log messages printed by experiment
             |+ experiment_meta.txt    # Meta information about the experiment
             |+ experiment_data.json   # All the data that was added to the internal exp. dict
             |+ hello_world.txt        # Text artifact that was committed to the experiment
             |+ snapshot.py            # Copy of the original experiment python module
             |+ analysis.py            # boilerplate code to get started with analysis of results

The ``analysis.py`` file is of special importance. It is created as a boilerplate starting
place for additional code, which performs analysis or post processing on the results of the experiment.
This can for example be used to transform data into a different format or create plots for visualization.

Specifically note these two aspects:

1. The analysis file contains all of the code which was defined in the ``e.analysis`` context of the
   original experiment file! This code snippet is automatically transferred at the end of the experiment.
2. The analysis file actually imports the snapshot copy of the original experiment file. This does not
   trigger the experiment to be executed again! The ``Experiment`` instance automatically notices that it
   is being imported and not explicitly executed. It will also populate all of it's internal attributes
   from the persistently saved data in ``experiment_data.json``, which means it is still possible to access
   all the data of the experiment without having to execute it again!

.. code-block:: python

    # analysis.py

    # [...] imports omitted
    # Importing the experiment itself
    from snapshot import *

    PATH = pathlib.Path(__file__).parent.absolute()
    DATA_PATH = os.path.join(PATH, 'experiment_data.json')
    # Load the all raw data of the experiment
    with open(DATA_PATH, mode='r') as json_file:
        DATA: Dict[str, Any] = json.load(json_file)


    if __name__ == '__main__':
        print('RAW DATA KEYS:')
        pprint(list(DATA.keys()))

        # ~ The analysis template from the experiment file
        # And we can access all the internal fields of the experiment object
        # and the experiment parameters here!
        print(HELLO, WORLD)
        print(e['strings/hello_world'])
        # logging will print to stdout but not modify the log file
        e.info('analysis done')


For an introduction to more advanced features take a look at the examples in
``pycomex/examples`` ( https://github.com/the16thpythonist/pycomex/tree/master/pycomex/examples )

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
