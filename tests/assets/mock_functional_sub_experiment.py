import os

from pycomex.functional.experiment import Experiment
from pycomex.utils import file_namespace, folder_path

PARAMETER = "sub experiment"

experiment = Experiment.extend(
    experiment_path="mock_functional_experiment.py",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)


@experiment.hook("hook")
def hook(e, parameter):
    e.log(f"sub experiment hook implementation, parameter: {parameter}")
    e.log(f"PARAMETER: {e.PARAMETER}")


@experiment.analysis
def analysis(e: Experiment):
    e.log("more analysis...")


experiment.run_if_main()
