import os
import pathlib

from pycomex.experiment import run_experiment


PATH = pathlib.Path(__file__).parent.absolute()
EXPERIMENT_PATH = os.path.join(PATH, '04_inheritance.py')

if __name__ == '__main__':
    run_experiment(EXPERIMENT_PATH)
