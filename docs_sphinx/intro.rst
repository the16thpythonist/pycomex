Introduction
============

Welcome to the documentation of the ``pycomex`` package for computational experiments in python! This page
contains some general remarks about the design choices of the project, how it can be installed and finally
a quickstart code example.

More detailed explanations of the various features of the package are provided as a series of annotated
code :ref:`examples`.

Main Philosophy
---------------

This package aims to improve the experience of conducting and managing records of computational experiments
as they are often required in academia regarding fields such as algorithm engineering, data science or
machine learning.

The main presumption made in this context is that each individual experiment is/can be defined within it's
own python code file. These experiment files will act as the basic units of code encapsulation and concern
separation. Think of these files as having the same basic purpose as encapsulating complex code into reusable
functions.

The basic goals of this approach are the following:

- *Improved management of records/artifacts*. Every run of an experiment creates new data, be it in the form
  of logged metrics, result plots, images or other kinds of file artifacts. This package creates a wrapping
  layer around each experiment, which automatically takes care of these menial "housekeeping" tasks. For
  every run of each experiment a new folder is automatically created. This folder will contain all the
  relevant artifacts and data created during the run.
- *Improve repeatability*. A core goal of any kind of experiment is reproducibility of results. However,
  the reproducibility of various intermediate results is often lost as the experiment code or parameters
  are irreversibly changed over time. Pycomex saves a snapshot of the exact original code used to
  produce the results, so that every experiment can be repeated in the future.

.. note::

    **Why not use functions?**

    As mentioned, the rationale behind the experiment files is basically the same as encapsulating various
    pieces of code into their own functions. Why not just have experiments be functions then?

    That certainly would have been possible and a lot of this comes down to arbitrary design choices /
    personal preference. That being said, I think there are some advantages to using files:

    - Files are more self-contained than just functions or classes. Being able to execute one file as a (more
      or less) standalone makes implementing the repeatability of experiments easier.
    - Code for computational experiments can become rather complex to the point where additional functions
      and classes specific to an individual experiment may have to be defined. Having to define local
      functions/classes within another function may be considered bad practice and decrease readability.

Installation
------------

Stable release
~~~~~~~~~~~~~~

To install pycomex, run this command in your terminal:

.. code-block:: console

    $ pip install pycomex

This is the preferred method to install pycomex, as it will always install the most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
~~~~~~~~~~~~

The sources for pycomex can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/the16thpythonist/pycomex

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ cd pycomex
    $ pip3 install .

.. command-output:: python -m pycomex.cli --version

.. _Github repo: https://github.com/the16thpythonist/pycomex
.. _tarball: https://github.com/the16thpythonist/pycomex/tarball/master

Getting Started
---------------

To get started, you only need to create a fresh python file to contain the experiment code and
import the ``Experiment`` content manager from the ``pycomex`` package. At the top of the file, you may
define any kinds of imports as usual. Then at the top you should also define the concrete values of
experiment parameters, functions etc.

The main logic of the experiment should go into the ``with`` block of the context manager. Upon entering
the context manager, the experiment folder for this particular run is created. The ``Experiment`` context
manager also manages error handling (and saving to a file), storing and saving of the main associative
data store among other things.

.. literalinclude:: ../pycomex/examples/quickstart.py
    :language: python

For a more detailed introduction of the various features look at the series of :ref:`examples`
in the next chapter!

