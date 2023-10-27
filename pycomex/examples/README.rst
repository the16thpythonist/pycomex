=============
Example Files
=============

This folder contains example files, which are supposed to explain the most important features of the library.
It is recommended to review the examples in the following order:

*  ``01_quickstart.py``: A very rudimentary explanation of the most basic features. This files is also the one
   used in the projects overall README.
*  ``02_basics.py``: More detailed explanations of the concepts already indicated in the previous example.
*  ``03_analysing.py``: More in-depth explanations for the "analysis" feature of the library, where a
   separate "analysis.py" boilerplate file is created in the archive folder of every experiment run.
*  ``04_inheritance.py``: Explains how the "SubExperiment" class can be used to inherit main functionality from
   other "parent" experiments, but overwrite certain parameters and inject custom code via filter and
   action hooks.
*  ``05_testing_mode.py``: Illustrates how to use the testing mode using the __TESTING__ magic parameter, which
   provides a convenient method of running a quick mock execution of an experiment to check for potential errors 
   in the later stages of the experiment.
