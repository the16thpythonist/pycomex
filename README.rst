.. image:: https://img.shields.io/pypi/v/pycomex.svg
        :target: https://pypi.python.org/pypi/pycomex

.. image:: https://readthedocs.org/projects/pycomex/badge/?version=latest
        :target: https://pycomex.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status

.. image:: https://img.shields.io/badge/docs-gh--pages-blue.svg
        :target: https://the16thpythonist.github.io/pycomex/
        :alt: GitHub Pages Documentation

=============================================
☄️ PyComex - Python Computational Experiments
=============================================

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
* Configuration files: Create YAML config files to run parameter variations without duplicating code

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

    # my_experiment.py
    """
    A minimal example demonstrating PyComex experiment structure.
    This docstring is saved as experiment metadata.
    """
    from pycomex.functional.experiment import Experiment
    from pycomex.utils import file_namespace, folder_path

    # Experiment parameters (uppercase variables are auto-detected)
    MESSAGE: str = "Hello PyComex!"
    ITERATIONS: int = 5

    # Debug mode: reuses same archive folder for development
    __DEBUG__ = True

    @Experiment(
        base_path=folder_path(__file__),     # Results stored relative to this file
        namespace=file_namespace(__file__),  # Creates folder based on filename
        glob=globals(),                      # Provides access to parameters
    )
    def experiment(e: Experiment) -> None:
        e.log("Starting experiment...")

        # Store structured data (creates nested JSON structure)
        e["config/message"] = MESSAGE
        e["config/iterations"] = ITERATIONS

        # Run experiment loop
        for i in range(ITERATIONS):
            metric = i * 0.1
            e.track("metrics/value", metric)  # Track time-series data
            e.log(f"Iteration {i}: {MESSAGE} (metric: {metric})")

        # Save final results and artifacts
        e["results/final_metric"] = metric
        e.commit_raw("results.txt", f"Final result: {metric}")

    # Run experiment when executed directly
    experiment.run_if_main()


**Running the Experiment:**

.. code-block:: console

    # print help
    python my_experiment.py --help

    # Basic execution
    python my_experiment.py

    # Override parameters via command line
    python my_experiment.py --MESSAGE "Custom message!" --ITERATIONS 10

This example would create the following folder structure:

.. code-block:: text

    my_experiment/
    └── debug/
        ├── experiment_out.log      # Complete execution log
        ├── experiment_meta.json    # Experiment metadata and parameters
        ├── experiment_data.json    # All tracked data and stored values
        ├── experiment_code.py      # Snapshot of the original experiment code
        ├── results.txt            # Custom artifact saved via commit_raw()
        └── .track/                # Time-series visualizations
            └── metrics_value_001.png  # Auto-generated plot of tracked metrics


**Key Features:**

* **Automatic Archiving**: Each experiment run creates a timestamped folder with complete execution records
* **Parameter Management**: Uppercase variables are automatically detected as configurable parameters
* **Command-line Overrides**: Parameters can be modified without editing code
* **Structured Data Storage**: Nested data organization using path-like keys (e.g., ``"config/learning_rate"``)
* **Time-series Tracking**: Built-in support for tracking metrics over time with automatic visualization
* **Artifact Management**: Easy saving of files, figures, and custom data formats

==========================
🔧 Command Line Interface
==========================

PyComex provides a powerful CLI accessible via the ``pycomex`` command:

**Creating New Experiments:**

.. code-block:: console

    # Create a new experiment module from template
    pycomex template experiment my_new_experiment.py

    # Create a configuration file from an existing experiment
    pycomex template config -e experiment.py -n config_name

**Running Experiments:**

.. code-block:: console

    # Run an experiment directly
    pycomex run experiment.py

    # Run a configuration file
    pycomex run config.yml

**Managing Experiment Archives:**

.. code-block:: console

    # List recent experiments
    pycomex archive list

    # Show detailed information about an experiment
    pycomex archive overview 

    # Compress and archive old experiments
    pycomex archive compress results/

For more command line options use ``pycomex --help``.
 
**NOTE.** For an introduction to more advanced features take a look at the examples in 
``pycomex/examples`` ( https://github.com/the16thpythonist/pycomex/tree/master/pycomex/examples )

================
📖 Documentation
================

Complete documentation is available at: https://the16thpythonist.github.io/pycomex/

Additional details on specific topics can be found in the ``DOCUMENTATION.rst`` file.

The ``pycomex/examples`` ( https://github.com/the16thpythonist/pycomex/tree/master/pycomex/examples ) folder
contains practical example modules that illustrate key features of the framework.

==========
🤝 Credits
==========

PyComex is built on top of these excellent open source libraries:

* Click_ - Command line interface toolkit
* Rich_ - Rich text and beautiful formatting in the terminal
* Jinja2_ - Modern and designer-friendly templating language
* NumPy_ - The fundamental package for scientific computing
* Matplotlib_ - Comprehensive 2D plotting library
* pytest_ - Testing framework

.. _Click: https://click.palletsprojects.com/
.. _Rich: https://rich.readthedocs.io/
.. _Pydantic: https://docs.pydantic.dev/latest/
.. _Jinja2: https://palletsprojects.com/p/jinja/
.. _NumPy: https://numpy.org/
.. _Matplotlib: https://matplotlib.org/
.. _PyYAML: https://pyyaml.org/
.. _Hatchling: https://hatch.pypa.io/latest/
.. _pytest: https://pytest.org/
