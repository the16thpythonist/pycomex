"""
Mock experiment that uses @experiment.testing decorator.
Used to test that Experiment.extend() works with testing hooks.
"""
import typing as t

from pycomex.functional.experiment import Experiment
from pycomex.utils import file_namespace, folder_path

PARAMETER: str = "base_value"


@Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
    debug=True,
)
def experiment(e: Experiment) -> None:
    e.log("starting experiment...")
    e["metrics/parameter"] = e.PARAMETER


@experiment.testing
def testing(e: Experiment):
    e.PARAMETER = "testing_value"


experiment.run_if_main()
