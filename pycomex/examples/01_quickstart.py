"""
This doc string will be saved as the "description" meta data of the experiment records
"""

import os

from pycomex import Experiment, file_namespace, folder_path

# Experiment parameters can simply be defined as uppercase global variables.
# These are automatically detected and can possibly be overwritten in command
# line invocation
HELLO: str = "hello "
WORLD: str = "world!"

# There are certain special parameters which will be detected by the experiment
# such as this, which will put the experiment into debug mode.
# That means instead of creating a new archive for every execution, it will always
# create/overwrite the "debug" archive folder.
__DEBUG__: bool = True

# An experiment is essentially a function. All of the code that constitutes
# one experiment should ultimately be called from this one function...


# The main experiment function has to be decorated with the "Experiment"
# decorator, which needs three main arguments:
# - base_path: The absolute string path to an existing FOLDER, where the
#   archive structure should be created
# - namespace: This is a relative path which defines the concrete folder
#   structure of the specific archive folder for this specific experiment
# - glob: The globals() dictionary for the current file
@Experiment(base_path=os.getcwd(), namespace="results/001_quickstart", glob=globals())
def experiment(e: Experiment):
    # Internally saved into automatically created nested dict
    # {'strings': {'hello_world': '...'}}
    e["strings/hello_world"] = e.HELLO + e.WORLD

    # Alternative to "print". Message is printed to stdout as well as
    # recorded to log file
    e.log("some debug message")

    # Automatically saves text file artifact to the experiment record folder
    file_name = "hello_world.txt"
    e.commit_raw(file_name, e.HELLO + e.WORLD)
    # e.commit_fig(file_name, fig)
    # e.commit_png(file_name, image)
    # ...


@experiment.analysis
def analysis(e: Experiment):
    # And we can access all the internal fields of the experiment object
    # and the experiment parameters here!
    print(e.HELLO, e.WORLD)
    print(e["strings/hello_world"])
    # logging will print to stdout but not modify the log file
    e.log("analysis done")


# This needs to be put at the end of the experiment. This method will
# then actually execute the main experiment code defined in the function
# above.
# NOTE: The experiment will only be run if this module is directly
# executed (__name__ == '__main__'). Otherwise the experiment will NOT
# be executed, which implies that the experiment module can be imported
# from somewhere else without triggering experiment execution!
experiment.run_if_main()
