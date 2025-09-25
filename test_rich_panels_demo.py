#!/usr/bin/env python3
"""
Demo script to test the Rich panels functionality for experiment start/end logging.
This script creates a simple experiment to showcase the new Rich panel features.
"""
import time
from pycomex.functional.experiment import Experiment
from pycomex.utils import file_namespace, folder_path

# Simple experiment parameters
LEARNING_RATE = 0.001
EPOCHS = 3
MODEL_TYPE = "simple_neural_network"
__DEBUG__ = True

@Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)
def demo_experiment(experiment):
    """
    A simple demo experiment to showcase Rich panel start/end logging.
    """
    experiment.log("Starting demo experiment...")

    # Simulate some work with logging
    for epoch in range(EPOCHS):
        experiment.log(f"Training epoch {epoch + 1}/{EPOCHS}")
        time.sleep(0.5)  # Simulate training time

        # Log some mock metrics
        loss = 1.0 / (epoch + 1)  # Decreasing loss
        accuracy = 0.5 + (epoch * 0.2)  # Increasing accuracy

        experiment.data[f"epoch_{epoch + 1}"] = {
            "loss": loss,
            "accuracy": accuracy
        }

        experiment.log(f"Epoch {epoch + 1} - Loss: {loss:.3f}, Accuracy: {accuracy:.3f}")

    experiment.log("Demo experiment completed successfully!")
    return {"final_loss": loss, "final_accuracy": accuracy}

if __name__ == "__main__":
    demo_experiment.run_if_main()