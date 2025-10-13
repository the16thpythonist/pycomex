"""
Simple test mixin with minimal functionality.

This mixin provides one parameter and one hook for testing purposes.
"""

from pycomex.functional.mixin import ExperimentMixin

# Mixin parameter
MIXIN_VALUE: int = 42

# Create the mixin instance
mixin = ExperimentMixin(glob=globals())


@mixin.hook("test_hook", replace=False)
def test_hook_impl(e):
    """A simple test hook implementation."""
    e.data["_mixin_executed"] = True
    return "mixin_result"
