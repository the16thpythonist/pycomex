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
* Documentation: https://pycomex.readthedocs.io.

Features
--------

* Automatically create (nested) folder structure for results of each run of an experiment
* Simply attach metadata such as performance metrics to experiment object and they will be automatically
  stored as JSON file
* Easily attach file artifacts such as ``matplotlib`` figures to experiment records
* Log messages to stdout as well as permanently store into log file

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

Upon entering the context, a new storage folder for each run of the experiment is created.

Storage of metadata, file artifacts and error handling is automatically managed on context exit.

.. literalinclude:: pycomex/examples/quickstart.py
    :language: python


This example would create the following folder structure:

.. code-block:: text

    tmp
    |- results
       |- example
          |- 000
             |+ experiment_log.txt
             |+ experiment_data.json
             |+ hello_world.txt

For more information and more interesting examples visit the Documentation: https://pycomex.readthedocs.io !

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
