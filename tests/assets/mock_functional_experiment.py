"""
This is the description
"""
from pycomex.utils import folder_path, file_namespace
from pycomex.functional.experiment import Experiment

PARAMETER = 'experiment'


@Experiment(base_path=folder_path(__file__),
            namespace=file_namespace(__file__),
            glob=globals(),
            debug=True)
def experiment(e: Experiment):
    e.log('starting experiment...')

    e.apply_hook('hook', parameter=10)
    e['metrics/parameter'] = e.PARAMETER
    e.log(e['metrics/parameter'])


@experiment.analysis
def analysis(e: Experiment):
    e.log('starting analysis...')


experiment.run_if_main()

