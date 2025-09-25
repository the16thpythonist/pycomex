"""
This example very simply shows how it is possible to execute an experiment through the code.
"""

import os
import pathlib

from pycomex import Experiment, get_experiment

PATH = pathlib.Path(__file__).parent.absolute()


if __name__ == "__main__":
    # The only thing that is needed is the absolute string path to the experiment module.
    experiment_path = os.path.join(PATH, "03_analyzing.py")

    # Given the absolute string path, this method will return the actual Experiment object instance
    # that is defined in that module.
    experiment: Experiment = get_experiment(experiment_path)

    # Contrary to the actual experiment files, here we can use the "run" function to force the
    # execution of the experiment even if it was imported rather than directly executed.
    experiment.run()
