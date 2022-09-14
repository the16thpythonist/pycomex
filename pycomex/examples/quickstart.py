#! /usr/bin/env python3
"""
This doc string will be saved as the "description" meta data of the experiment records
"""
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
with Skippable(), (e := Experiment("/tmp", "example/quickstart", globals())):

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
