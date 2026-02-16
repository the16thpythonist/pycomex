"""Base experiment for INHERIT testing."""
from pycomex.functional.experiment import Experiment
from pycomex.utils import file_namespace, folder_path

PARAM_A = 10
PARAM_B = [1, 2, 3]
PARAM_C = {"key": "value"}


@Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
    debug=True,
)
def experiment(e: Experiment) -> None:
    e.log("base experiment running")


experiment.run_if_main()
