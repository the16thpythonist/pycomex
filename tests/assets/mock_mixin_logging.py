"""
Logging test mixin with before_run and after_run hooks.

This mixin logs messages at the start and end of experiments.
"""

from pycomex.functional.mixin import ExperimentMixin

# Mixin parameters
LOG_PREFIX: str = "[TestMixin]"
ENABLE_LOGGING: bool = True

# Create the mixin instance
mixin = ExperimentMixin(glob=globals())


@mixin.hook("before_run", replace=False)
def log_experiment_start(e):
    """Log when experiment starts."""
    prefix = e.parameters.get("LOG_PREFIX", "[TestMixin]")
    e.data["_mixin_start_logged"] = True
    e.log(f"{prefix} Experiment starting")


@mixin.hook("after_run", replace=False)
def log_experiment_end(e):
    """Log when experiment ends."""
    prefix = e.parameters.get("LOG_PREFIX", "[TestMixin]")
    e.data["_mixin_end_logged"] = True
    e.log(f"{prefix} Experiment completed")


@mixin.hook("custom_validation", replace=False)
def validate_data(e, value: int, threshold: int = 10):
    """Custom hook for data validation."""
    return value >= threshold
