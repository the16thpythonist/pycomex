"""
This doc string will be saved as the "description" meta data of the experiment records
"""
from pycomex import Experiment

# Experiment parameters can simply be defined as uppercase global variables.
# These are automatically detected and can possibly be overwritten in command
# line invocation
HELLO = 'hello '
WORLD = 'world!'

# Experiment context manager needs 3 positional arguments:
# - Path to an existing folder in which to store the results
# - A namespace name unique for each experiment
# - access to the local globals() dict
with Experiment('/tmp/results', 'example', globals()) as e:
    e.prepare() # important!

    # Internally saved into automatically created nested dict
    # {'strings': {'hello_world': '...'}}
    e['strings/hello_world'] = HELLO + WORLD

    # Alternative to "print". Message is printed to stdout as well as
    # recorded to log file
    e.info('some debug message')

    # Automatically saves text file artifact to the experiment record folder
    file_name = 'hello_world.txt'
    e.commit_raw(file_name, HELLO + WORLD)
    # e.commit_fig(file_name, fig)
    # e.commit_png(file_name, image)
    # ...
