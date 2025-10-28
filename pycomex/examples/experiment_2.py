from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

PARAM1: int = 300

experiment = Experiment.extend(
    'experiment.py',
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('plot_results', default=False, replace=True)
def plot_results(e: Experiment,
                 param1: int):
    
    print('plotting new')
    
    
experiment.run_if_main()