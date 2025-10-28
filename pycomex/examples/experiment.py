from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

# :param PARAM1:
#       This is a parameter that can be used in the experiment.
PARAM1: int = 100

# :param WANDB_PROJECT:
#      The name of the wandb project to which the experiment should be logged.
#      This is required to activate the weights and biases integration!
WANDB_PROJECT: str = 'test'

__DEBUG__ = True

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)

@experiment.hook('plot_results')
def plot_results(e: Experiment, param1: int):
    print("hello")


@experiment.hook('train_model', default=False, replace=True)
def train_model():
    
    print('training model with new hook')


@experiment
def experiment(e: Experiment):
    
    print(e.path)
    print(e.PARAM1) 
    e.log('this message will be logged')
    
    e.apply_hook('plot_results', param1=300)
    
    e.commit_fig(fig, 'figure.png')
    
    
experiment.run_if_main()