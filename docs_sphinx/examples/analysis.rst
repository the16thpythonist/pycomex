Analysis Example
================

This page will showcase how ``pycomex`` tries to simplify the analysis of the results of an experiment which
has already been completed and filed away.

Motivation
----------

Ask yourself the following question: *When conducting a computational experiment, where do you put the code
for the analysis of the results?*

We conduct computational experiments mainly to gather data, which we can then further process into rich
visualizations or more advanced metrics of sorts. There are primarily two choices for where to put the code
which does this post-experiment analysis:

- *at the end of the experiment*. We can put the code for the analysis at the end of the file which
  executes the experiment itself. This is a neat and direct solution, but just consider how often you had
  to fix a typo in the plot title, tweak the value range or compute just one more metric *after* looking at
  the results. Obviously we cant just repeat the experiment all over again.
- *into a separate file*. Thus, we might find it more comfortable to put the analysis into a separate file
  from the beginning. But these kinds of files can become real time sinks over time, as they contain a
  large amount of boilerplate code. Just think of all the standard imports... And then there is the code
  to load all the data from the JSON files into which you previously saved it. You have to use different
  variable names and possibly even different data structures since you dont have the *same* environment as
  in the experiment file.

``pycomex`` combines both methods and gets rid of the disadvantages of either.

Templating analysis files into the results folder
-------------------------------------------------

The core idea is this: Whenever an experiment is completed, an ``analysis.py`` file is automatically
generated and placed into the results folder as well. This file will already contain most of the
boilerplate code to get started with analysing the results of that specific experiment run.

At the end of the page there is an example of such a generated file. Note how it imports from a module
called ``snapshot``. This is actually a copy of the experiment script as it were at the exact moment of
execution for this run. It can be imported without triggering the main content of the experiment to be
executed! Moreover, it automatically detects that it is in fact just a snapshot which is being imported
and automatically populate the internal data storage from the saved json file! This means you can use the
experiment object from the experiment file, as if it were just the end of the experiment.

Defining analysis code at the end of the experiment
---------------------------------------------------

It is also possible to define some analysis code at the end of the experiment itself. If you do that, you
might want to wrap it with the ``Experiment.analysis`` context manager. The code within will be executed
just fine.

Moreover, all of the code defined within this context manager will automatically be copied to the
``analysis.py`` file as well. Under some light restrictions (see below) that code will *just work*.
So, if you need to fix some typo in the header of a plot, you literally just have to change that line in
the analysis file and run it again to recreate all of your analysis results!

Example
-------

The following example file shows how this works. Specifically note how you can define analysis code within
the actual experiment script by wrapping it in the ``Experiment.analysis`` context manager. That code is
then automatically copied into the ``analysis.py*`` file and will work *as is*!

(So long as it only uses the experiment's internally stored data or the upper case experiment variables
defined *above* the experiment context)

.. literalinclude:: ../../pycomex/examples/analysis.py
    :language: python

When executed, the above file produces the following output:

.. command-output:: python ../pycomex/examples/analysis.py
    :shell:

The following file contents belong the the ``analysis.py`` file which was created by the above run of the
experiment:

.. literalinclude:: /assets/analysis.py
    :language: python
    :caption: generated analysis.py
