"""
Unit tests for the Experiment Mixin system.

This test module verifies that the mixin system works correctly, including:
- Mixin creation and import
- Parameter merging
- Hook registration and execution
- Hook execution order
- Multiple mixin support
"""

import os
import sys
import tempfile

import pytest

from pycomex.functional.experiment import Experiment
from pycomex.functional.mixin import ExperimentMixin
from pycomex.testing import ConfigIsolation, ExperimentIsolation

from .util import ASSETS_PATH


class TestExperimentMixin:
    """Test the core ExperimentMixin functionality."""

    def test_mixin_construction_works(self):
        """
        Basic mixin instantiation should work and discover parameters.
        """
        # Create a simple mixin with parameters
        glob = {
            "__file__": "/tmp/test_mixin.py",
            "PARAM_A": 10,
            "PARAM_B": "test",
            "not_a_param": "lowercase",
        }

        mixin = ExperimentMixin(glob=glob)

        assert isinstance(mixin, ExperimentMixin)
        assert "PARAM_A" in mixin.parameters
        assert "PARAM_B" in mixin.parameters
        assert mixin.parameters["PARAM_A"] == 10
        assert mixin.parameters["PARAM_B"] == "test"
        # Lowercase variables should not be parameters
        assert "not_a_param" not in mixin.parameters

    def test_mixin_hook_registration(self):
        """
        Hooks can be registered on a mixin using the @mixin.hook() decorator.
        """
        glob = {"__file__": "/tmp/test_mixin.py"}
        mixin = ExperimentMixin(glob=glob)

        @mixin.hook("test_hook", replace=False)
        def test_hook_func(e):
            return "test_result"

        assert "test_hook" in mixin.hook_map
        assert len(mixin.hook_map["test_hook"]) == 1
        assert mixin.hook_map["test_hook"][0] == test_hook_func

    def test_mixin_import_from_file(self):
        """
        ExperimentMixin.import_from() should successfully import a mixin from a file.
        """
        mixin_path = os.path.join(ASSETS_PATH, "mock_mixin_simple.py")
        glob = {"__file__": "/tmp/test.py"}

        mixin = ExperimentMixin.import_from(mixin_path, glob=glob)

        assert isinstance(mixin, ExperimentMixin)
        # Check parameter was discovered
        assert "MIXIN_VALUE" in mixin.parameters
        assert mixin.parameters["MIXIN_VALUE"] == 42
        # Check hook was registered
        assert "test_hook" in mixin.hook_map

    def test_experiment_include_single_mixin(self):
        """
        experiment.include() should successfully merge a mixin into an experiment.
        """
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            mixin_path = os.path.join(ASSETS_PATH, "mock_mixin_simple.py")
            experiment.include(mixin_path)

            # Check that mixin was added to mixins list
            assert len(experiment.mixins) == 1
            assert isinstance(experiment.mixins[0], ExperimentMixin)

            # Check that hook was merged
            assert "test_hook" in experiment.hook_map
            assert len(experiment.hook_map["test_hook"]) > 0

    def test_mixin_parameters_as_defaults(self):
        """
        Mixin parameters should be used as fallback defaults.
        Experiment parameters should take precedence over mixin parameters.
        """
        mixin_path = os.path.join(ASSETS_PATH, "mock_mixin_logging.py")

        # Test 1: Mixin parameter used when experiment doesn't define it
        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            experiment.include(mixin_path)

            # Mixin parameter should be added as default
            assert "LOG_PREFIX" in experiment.parameters
            assert experiment.parameters["LOG_PREFIX"] == "[TestMixin]"

        # Test 2: Experiment parameter takes precedence
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod={"LOG_PREFIX": "[MyExperiment]"}
        ) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            experiment.include(mixin_path)

            # Experiment parameter should NOT be overwritten by mixin
            assert experiment.parameters["LOG_PREFIX"] == "[MyExperiment]"

    def test_mixin_hooks_execute(self):
        """
        Hooks from a mixin should actually execute during experiment run.
        """
        mixin_path = os.path.join(ASSETS_PATH, "mock_mixin_simple.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            experiment.include(mixin_path)

            @experiment
            def run(e):
                # Apply the test hook
                result = e.apply_hook("test_hook")

            experiment.run()

            # Check that mixin hook executed
            assert "_mixin_executed" in experiment.data
            assert experiment.data["_mixin_executed"] is True

    def test_multiple_mixins_work(self):
        """
        Including multiple mixins sequentially should work correctly.
        """
        mixin_simple = os.path.join(ASSETS_PATH, "mock_mixin_simple.py")
        mixin_logging = os.path.join(ASSETS_PATH, "mock_mixin_logging.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            # Include both mixins
            experiment.include([mixin_simple, mixin_logging])

            # Check that both mixins were added
            assert len(experiment.mixins) == 2

            # Check that parameters from both mixins are present
            assert "MIXIN_VALUE" in experiment.parameters
            assert "LOG_PREFIX" in experiment.parameters

            # Check that hooks from both mixins are present
            assert "test_hook" in experiment.hook_map
            assert "before_run" in experiment.hook_map

    def test_hook_execution_order(self):
        """
        Hooks should execute in order: base experiment → mixin → current experiment.
        """
        # Create a base experiment file dynamically
        with tempfile.TemporaryDirectory() as temp_dir:
            base_exp_path = os.path.join(temp_dir, "base_exp.py")
            with open(base_exp_path, "w") as f:
                f.write("""
from pycomex import Experiment, folder_path, file_namespace

ORDER = []

experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

@experiment.hook("test_order", replace=False)
def base_hook(e):
    e.data.setdefault('_order', []).append('base')
""")

            # Create a mixin file dynamically
            mixin_path = os.path.join(temp_dir, "mixin.py")
            with open(mixin_path, "w") as f:
                f.write("""
from pycomex.functional.mixin import ExperimentMixin

mixin = ExperimentMixin(glob=globals())

@mixin.hook("test_order", replace=False)
def mixin_hook(e):
    e.data.setdefault('_order', []).append('mixin')
""")

            # Create sub experiment
            with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
                # Import base experiment
                from pycomex.functional.experiment import Experiment
                experiment = Experiment.extend(
                    experiment_path=base_exp_path,
                    base_path=iso.path,
                    namespace="test_sub",
                    glob=iso.glob,
                )

                # Include mixin
                experiment.include(mixin_path)

                # Add current experiment hook
                # Note: Must set default=False to add to existing hooks
                @experiment.hook("test_order", replace=False, default=False)
                def current_hook(e):
                    e.data.setdefault('_order', []).append('current')

                @experiment
                def run(e):
                    e.apply_hook("test_order")

                experiment.run()

                # Verify execution order
                assert "_order" in experiment.data
                assert experiment.data["_order"] == ['base', 'mixin', 'current']

    def test_mixin_saved_in_dependencies(self):
        """
        Mixin files should be copied to the experiment archive folder.
        """
        mixin_path = os.path.join(ASSETS_PATH, "mock_mixin_simple.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            experiment.include(mixin_path)

            @experiment
            def run(e):
                pass

            experiment.run()

            # Check that mixin file was copied to archive
            mixin_filename = os.path.basename(mixin_path)
            archived_mixin_path = os.path.join(experiment.path, mixin_filename)
            assert os.path.exists(archived_mixin_path)

    def test_custom_hook_from_mixin(self):
        """
        Custom hooks defined in a mixin can be called using apply_hook().
        """
        mixin_path = os.path.join(ASSETS_PATH, "mock_mixin_logging.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            experiment.include(mixin_path)

            @experiment
            def run(e):
                # Call custom validation hook from mixin
                result1 = e.apply_hook("custom_validation", value=15, threshold=10)
                result2 = e.apply_hook("custom_validation", value=5, threshold=10)

                e["validation_15_passes"] = result1
                e["validation_5_passes"] = result2

            experiment.run()

            # Check that custom hook worked correctly
            assert experiment["validation_15_passes"] is True
            assert experiment["validation_5_passes"] is False

    def test_mixin_hooks_run_during_experiment(self):
        """
        before_run and after_run hooks from mixin should execute during experiment lifecycle.
        """
        mixin_path = os.path.join(ASSETS_PATH, "mock_mixin_logging.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="test_experiment",
                glob=iso.glob,
            )

            experiment.include(mixin_path)

            @experiment
            def run(e):
                # Just run the experiment
                e["test_value"] = 123

            experiment.run()

            # Check that mixin hooks executed
            assert "_mixin_start_logged" in experiment.data
            assert "_mixin_end_logged" in experiment.data
            assert experiment.data["_mixin_start_logged"] is True
            assert experiment.data["_mixin_end_logged"] is True
