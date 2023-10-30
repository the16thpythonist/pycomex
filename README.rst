.. image:: https://img.shields.io/pypi/v/pycomex.svg
        :target: https://pypi.python.org/pypi/pycomex

.. image:: https://readthedocs.org/projects/pycomex/badge/?version=latest
        :target: https://pycomex.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status

============================================
☄️ PyComex - Python Computational Experiments
============================================

Microframework to improve the experience of running and managing archival records of computational
experiments, such as machine learning and data science experiments, in Python.

===========
🔥 Features
===========

* Automatically create (nested) folder structure for results of each run of an experiment
* Simply attach metadata such as performance metrics to experiment object and they will be automatically
  stored as JSON file
* Easily attach file artifacts such as ``matplotlib`` figures to experiment records
* Log messages to stdout as well as permanently store into log file
* Ready-to-use automatically generated boilerplate code for the analysis and post-processing of
  experiment data after experiments have terminated.
* Experiment inheritance: Experiment modules can inherit from other modules and extend their functionality
  via parameter overwrites and hooks!

==========================
📦 Installation by Package
==========================

Install the stable version with ``pip``

.. code-block:: console

    pip3 install pycomex

=========================
📦 Installation by Source
=========================

Or the most recent development version by cloning the source:

.. code-block:: console

    git clone https://github.com/the16thpythonist/pycomex.git

and then installing with either pip 

.. code-block:: console

    cd pycomex
    pip3 install -e .

or poetry

.. code-block:: console

    cd pycomex
    poetry install

=============
🚀 Quickstart
=============

Each computational experiment has to be bundled as a standalone python module. Important experiment
parameters are placed at the top of this module. All variable names written in upper case will automatically
be detected as parameters of the experiment.

The actual implementation of the experiment execution is placed into a single file which will have to be
decorated with the ``Experiment`` decorator.

Upon execution the experiment, a new archive folder is automatically created. This archive folder can
be used to store all the file artifacts that are created during the experiment.
Some artifacts are stored automatically by default, such as a JSON file containing all data stored in the
main experiment storage, a snapshot of the experiment module and more...

Archiving of metadata, file artifacts and error handling is automatically managed on context exit.

.. code-block:: python

    # quickstart.py
    """
    This doc string will be saved as the "description" meta data of the experiment records
    """
    import os
    from pycomex.functional.experiment import Experiment
    from pycomex.utils import folder_path, file_namespace

    # Experiment parameters can simply be defined as uppercase global variables.
    # These are automatically detected and can possibly be overwritten in command
    # line invocation
    HELLO = "hello "
    WORLD = "world!"

    # There are certain special parameters which will be detected by the experiment
    # such as this, which will put the experiment into debug mode.
    # That means instead of creating a new archive for every execution, it will always
    # create/overwrite the "debug" archive folder.
    __DEBUG__ = True

    # An experiment is essentially a function. All of the code that constitutes
    # one experiment should ultimately be called from this one function...

    # The main experiment function has to be decorated with the "Experiment"
    # decorator, which needs three main arguments:
    # - base_path: The absolute string path to an existing FOLDER, where the
    #   archive structure should be created
    # - namespace: This is a relative path which defines the concrete folder
    #   structure of the specific archive folder for this specific experiment
    # - glob: The globals() dictionary for the current file
    @Experiment(base_path=os.getcwd(),
                namespace='results/quickstart',
                glob=globals())
    def experiment(e: Experiment):
        # Internally saved into automatically created nested dict
        # {'strings': {'hello_world': '...'}}
        e["strings/hello_world"] = HELLO + WORLD

        # Alternative to "print". Message is printed to stdout as well as
        # recorded to log file
        e.log("some debug message")

        # Automatically saves text file artifact to the experiment record folder
        file_name = "hello_world.txt"
        e.commit_raw(file_name, HELLO + WORLD)
        # e.commit_fig(file_name, fig)
        # e.commit_png(file_name, image)
        # ...


    @experiment.analysis
    def analysis(e: Experiment):
        # And we can access all the internal fields of the experiment object
        # and the experiment parameters here!
        print(HELLO, WORLD)
        print(e['strings/hello_world'])
        # logging will print to stdout but not modify the log file
        e.log('analysis done')


    # This needs to be put at the end of the experiment. This method will
    # then actually execute the main experiment code defined in the function
    # above.
    # NOTE: The experiment will only be run if this module is directly
    # executed (__name__ == '__main__'). Otherwise the experiment will NOT
    # be executed, which implies that the experiment module can be imported
    # from somewhere else without triggering experiment execution!
    experiment.run_if_main()


This example would create the following folder structure:

.. code-block:: python

    cwd
    |- results
       |- quickstart
          |- debug
             |+ experiment_out.log     # Contains all the log messages printed by experiment
             |+ experiment_meta.json   # Meta information about the experiment
             |+ experiment_data.json   # All the data that was added to the internal exp. dict
             |+ hello_world.txt        # Text artifact that was committed to the experiment
             |+ code.py                # Copy of the original experiment python module
             |+ analysis.py            # boilerplate code to get started with analysis of results


The ``analysis.py`` file is of special importance. It is created as a boilerplate starting
place for additional code, which performs analysis or post processing on the results of the experiment.
This can for example be used to transform data into a different format or create plots for visualization.

Specifically note these two aspects:

1. The analysis file contains all of the code which was defined in the ``analysis`` function of the
   original experiment file! This code snippet is automatically transferred at the end of the experiment.
2. The analysis file actually imports the snapshot copy of the original experiment file. This does not
   trigger the experiment to be executed again! The ``Experiment`` instance automatically notices that it
   is being imported and not explicitly executed. It will also populate all of it's internal attributes
   from the persistently saved data in ``experiment_data.json``, which means it is still possible to access
   all the data of the experiment without having to execute it again!

.. code-block:: python

    # analysis.py

    # [...] imports omitted
    from code import *
    from pycomex.functional.experiment import Experiment

    PATH = pathlib.Path(__file__).parent.absolute()
    # "Experiment.load" is used to load the the experiment data from the
    # archive. it returns an "Experiment" object which will act exactly the
    # same way as if the experiment had just finished it's execution!
    CODE_PATH = os.path.join(PATH, 'code.py')
    experiment = Experiment.load(CODE_PATH)
    experiment.analyses = []

    # All of the following code is automatically extracted from main
    # experiment module itself and can now be edited and re-executed.
    # Re-execution of this analysis.py file will not trigger an
    # execution of the experiment but all the stored results will be
    # available anyways!
    @experiment.analysis
    def analysis(e: Experiment):
        # And we can access all the internal fields of the experiment
        # object and the experiment parameters here!
        print(HELLO, WORLD)
        print(e['strings/hello_world'])
        # logging will print to stdout but not modify the log file
        e.info('analysis done')


    # This method will execute only the analysis code!
    experiment.execute_analyses()


For an introduction to more advanced features take a look at the examples in
``pycomex/examples`` ( https://github.com/the16thpythonist/pycomex/tree/master/pycomex/examples )

================
📖 Documentation
================

Unfortunately, there exists no dedicated documentation of the project yet. However, some additional details on some 
key topics can be found in the ``DOCUMENTATION.rst`` file.

Aside from that, the ``pycomex/examples`` ( https://github.com/the16thpythonist/pycomex/tree/master/pycomex/examples ) folder 
contains some example modules which illustrate some of the key features of the framework by practical example.

==========
🤝 Credits
==========

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
