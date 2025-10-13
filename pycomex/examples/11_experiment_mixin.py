"""
This example demonstrates how to use experiment mixins in PyComex.

Mixins provide reusable hook implementations that can be shared across multiple
experiments. Instead of copying the same hook code into different experiments,
you can create a mixin once and include it wherever needed.

This example shows:
1. How to extend a base experiment
2. How to include a mixin with one line of code
3. How mixin hooks work alongside your own hooks
"""

from pycomex import Experiment, file_namespace, folder_path

# Override some parameters from the base experiment
NUM_WORDS: int = 50
REPETITIONS: int = 5

__DEBUG__: bool = True

# Extend the base experiment
experiment = Experiment.extend(
    "02_basic.py",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

# Include the mixin - this adds the mixin's hooks to your experiment
experiment.include("11_experiment_mixin_mixin.py")

# You can still add your own hooks - they work together with the mixin's hooks
# Execution order: Base experiment → Mixin hooks → Your hooks


@experiment.hook("after_run", replace=False)
def custom_summary(e):
    """Add a custom summary at the end."""
    e.log("→ Custom: Generated files for all repetitions")


experiment.run_if_main()
