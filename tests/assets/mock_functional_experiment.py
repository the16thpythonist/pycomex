"""
This is the description of the module
"""

import typing as t

from pycomex.functional.experiment import Experiment
from pycomex.utils import file_namespace, folder_path

# testing comment - do not remove

# :param PARAMETER:
#       This is a parameter description. If this description is given in the particular
#       format, it should technically show up in the parameter
PARAMETER: str | None = "experiment"

# :param PARAMETER2:
#       This is a nother description
PARAMETER2: str = "hello world"

print(__annotations__)


@Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
    debug=True,
)
def experiment(e: Experiment) -> None:
    # Some random comment that is not important
    e.log("starting experiment...")
    # :hook hook:
    #       This is a hook description. If given in this format, it should technically be discoverable
    #       and added to the typing dict.
    e.apply_hook("hook", parameter=10)
    # This is some random other string that is not important.
    e["metrics/parameter"] = e.PARAMETER
    e.log(e["metrics/parameter"])


@experiment.analysis
def analysis(e: Experiment):
    e.log("starting analysis...")


experiment.run_if_main()
