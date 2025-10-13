"""
A simple logging mixin that adds start and end messages to experiments.

This mixin demonstrates the core concept of experiment mixins: reusable hook
implementations that can be shared across multiple experiments without code duplication.

When included in an experiment, this mixin will automatically log messages when
the experiment starts and completes.
"""

from pycomex.functional.mixin import ExperimentMixin

# Create the mixin instance
mixin = ExperimentMixin(glob=globals())


@mixin.hook("before_run", replace=False)
def log_start(e):
    """Log a message when the experiment starts."""
    e.log("→ Mixin: Experiment starting...")


@mixin.hook("after_run", replace=False)
def log_end(e):
    """Log a message when the experiment completes."""
    e.log("→ Mixin: Experiment finished!")
