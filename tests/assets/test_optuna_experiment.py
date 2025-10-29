"""
Test experiment for Optuna hyperparameter optimization.

This experiment demonstrates how to use the Optuna plugin to optimize parameters.
It includes all the required hooks and performs a simple optimization task.
"""
import numpy as np
from pycomex.functional.experiment import Experiment
from pycomex.utils import folder_path, file_namespace

# ~ Parameters to optimize
LEARNING_RATE: float = 0.1
BATCH_SIZE: int = 32
DROPOUT_RATE: float = 0.5

# ~ Other parameters
NUM_EPOCHS: int = 10
__DEBUG__: bool = True  # Use debug mode to create reusable archives

__OPTUNA_REPETITIONS__ = 2

# ~ Experiment setup
experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals()
)


@experiment.hook('__optuna_parameters__')
def define_search_space(e: Experiment, trial) -> dict:
    """
    Define the parameter search space for Optuna.

    This hook is called during experiment initialization when running with
    `pycomex optuna run`. It should return a dictionary mapping parameter names
    to trial suggestions.

    :param e: The experiment instance
    :param trial: Optuna trial object for suggesting parameters
    :returns: Dictionary of parameter suggestions
    """
    return {
        'LEARNING_RATE': trial.suggest_float('LEARNING_RATE', 1e-4, 1e-1, log=True),
        'BATCH_SIZE': trial.suggest_int('BATCH_SIZE', 16, 128, step=16),
        'DROPOUT_RATE': trial.suggest_float('DROPOUT_RATE', 0.1, 0.9)
    }


@experiment.hook('__optuna_objective__')
def extract_objective_value(e: Experiment) -> float:
    """
    Extract the objective value from the experiment results.

    This hook is called after experiment finalization. It should return
    a single numeric value that Optuna will try to optimize (maximize or minimize).

    :param e: The experiment instance with completed results
    :returns: Objective value to optimize
    """
    # Return the final accuracy (to be maximized)
    return e['results/final_accuracy']


@experiment.hook('__optuna_sampler__', replace=True)
def configure_sampler(e: Experiment):
    """
    Configure the Optuna sampler (optional).

    If not provided, the plugin uses TPESampler with default settings.

    :param e: The experiment instance
    :returns: Optuna sampler instance
    """
    import optuna
    return optuna.samplers.TPESampler(
        n_startup_trials=5,
        multivariate=True
    )


@experiment.hook('__optuna_direction__')
def optimization_direction(e: Experiment) -> str:
    """
    Specify optimization direction (optional).

    :param e: The experiment instance
    :returns: Either 'maximize' or 'minimize'
    """
    return 'maximize'


@experiment
def run_experiment(e: Experiment):
    """
    Main experiment function - simulates a machine learning training loop.

    In this example, we simulate training a model with the optimized hyperparameters
    and compute a simulated accuracy based on how close the parameters are to
    an "optimal" configuration.

    :param e: The experiment instance
    """
    e.log('Starting experiment with Optuna optimization...')
    e.log(f'Parameters: LR={e.LEARNING_RATE}, BS={e.BATCH_SIZE}, DR={e.DROPOUT_RATE}')

    # Simulate training epochs
    accuracies = []
    for epoch in range(e.NUM_EPOCHS):
        # Simulate training with these hyperparameters
        # The "optimal" parameters are: LR=0.01, BS=64, DR=0.3
        # We compute accuracy based on distance from optimal values

        lr_score = 1.0 - abs(np.log10(e.LEARNING_RATE) - np.log10(0.01)) / 2.0
        bs_score = 1.0 - abs(e.BATCH_SIZE - 64) / 64.0
        dr_score = 1.0 - abs(e.DROPOUT_RATE - 0.3) / 0.6

        # Combine scores with some randomness
        epoch_accuracy = (lr_score + bs_score + dr_score) / 3.0
        epoch_accuracy = max(0.0, min(1.0, epoch_accuracy + np.random.normal(0, 0.05)))

        accuracies.append(epoch_accuracy)

        e.log(f'Epoch {epoch + 1}/{e.NUM_EPOCHS}: Accuracy = {epoch_accuracy:.4f}')
        e.track(f'training/accuracy', epoch_accuracy)

    # Store final results
    final_accuracy = np.mean(accuracies[-3:])  # Average of last 3 epochs
    e['results/final_accuracy'] = final_accuracy
    e['results/all_accuracies'] = accuracies
    e['results/best_accuracy'] = max(accuracies)

    e.log(f'Training complete! Final accuracy: {final_accuracy:.4f}')

    # Create a simple plot
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(range(1, e.NUM_EPOCHS + 1), accuracies, marker='o')
    ax.set_xlabel('Epoch')
    ax.set_ylabel('Accuracy')
    ax.set_title(f'Training Progress (LR={e.LEARNING_RATE:.4f}, BS={e.BATCH_SIZE}, DR={e.DROPOUT_RATE:.2f})')
    ax.grid(True, alpha=0.3)
    e.commit_fig('training_progress.png', fig)

    return final_accuracy


if __name__ == '__main__':
    experiment.run_if_main()
