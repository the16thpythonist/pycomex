import os
import pathlib

from pycomex.experiment import run_experiment


PATH = pathlib.Path(__file__).parent.absolute()
EXPERIMENT_PATH = os.path.join(PATH, 'inheritance.py')
print(os.path.exists(EXPERIMENT_PATH))

run_experiment(EXPERIMENT_PATH)
