"""
Tests for the INHERIT sentinel value for explicit parameter inheritance.

This test module verifies that the INHERIT system works correctly, including:
- Singleton behavior and class hierarchy
- resolve() with transforms, chains, and error cases
- Integration with Experiment.extend() and the full experiment lifecycle
- Metadata serialization of resolved values
"""
import json
import os
import sys
import tempfile

import pytest

from pycomex.functional.experiment import Experiment
from pycomex.functional.inherit import (
    INHERIT,
    Inherit,
    InheritBase,
    InheritError,
    _InheritSentinel,
    _UNSET,
)
from pycomex.testing import ConfigIsolation, ExperimentIsolation

from ..util import ASSETS_PATH


class TestInheritSentinel:
    """Tests for the INHERIT singleton and class hierarchy."""

    def test_inherit_is_singleton(self):
        """INHERIT should always be the same object."""
        assert INHERIT is _InheritSentinel()

    def test_inherit_is_inherit_base(self):
        """INHERIT sentinel should be an instance of InheritBase."""
        assert isinstance(INHERIT, InheritBase)

    def test_inherit_call_returns_inherit_instance(self):
        """Calling INHERIT(fn) should return an Inherit instance."""
        result = INHERIT(lambda x: x * 2)
        assert isinstance(result, Inherit)
        assert isinstance(result, InheritBase)
        assert result.transform is not None

    def test_inherit_call_with_non_callable_raises(self):
        """INHERIT(non_callable) should raise TypeError."""
        with pytest.raises(TypeError, match="callable"):
            INHERIT(42)

    def test_inherit_repr(self):
        """INHERIT repr should be readable."""
        assert repr(INHERIT) == "INHERIT"

    def test_inherit_instance_default_has_no_transform(self):
        """Inherit(transform=None) should have no transform."""
        obj = Inherit(transform=None)
        assert obj.transform is None
        assert obj.parent_value is _UNSET

    def test_inherit_importable_from_pycomex(self):
        """INHERIT should be importable from top-level pycomex package."""
        from pycomex import INHERIT as imported

        assert imported is INHERIT


class TestInheritResolve:
    """Tests for the Inherit.resolve() method."""

    def test_resolve_simple_value(self):
        """resolve() with no transform should return parent value."""
        obj = Inherit(transform=None)
        obj.parent_value = 42
        assert obj.resolve() == 42

    def test_resolve_with_transform(self):
        """resolve() with transform should apply it."""
        obj = Inherit(transform=lambda x: x * 2)
        obj.parent_value = 10
        assert obj.resolve() == 20

    def test_resolve_recursive_chain(self):
        """resolve() should handle multi-level inheritance chains."""
        child_inherit = Inherit(transform=lambda x: x * 2)
        child_inherit.parent_value = 10

        grandchild_inherit = Inherit(transform=None)
        grandchild_inherit.parent_value = child_inherit

        assert grandchild_inherit.resolve() == 20

    def test_resolve_recursive_chain_with_transforms(self):
        """Multi-level chain where each level has a transform."""
        child_inherit = Inherit(transform=lambda x: x + 10)
        child_inherit.parent_value = 5

        grandchild_inherit = Inherit(transform=lambda x: x * 3)
        grandchild_inherit.parent_value = child_inherit

        assert grandchild_inherit.resolve() == 45

    def test_resolve_with_none_parent_value(self):
        """resolve() should work when parent value is None."""
        obj = Inherit(transform=None)
        obj.parent_value = None
        assert obj.resolve() is None

    def test_resolve_unset_raises_inherit_error(self):
        """resolve() should raise InheritError when parent_value is _UNSET."""
        obj = Inherit(transform=None)
        with pytest.raises(InheritError, match="no parent value"):
            obj.resolve()

    def test_resolve_with_list_transform(self):
        """Users can use lambdas for list manipulation."""
        obj = Inherit(transform=lambda x: x + ["extra_item"])
        obj.parent_value = ["item1", "item2"]
        assert obj.resolve() == ["item1", "item2", "extra_item"]

    def test_resolve_with_dict_merge_transform(self):
        """Users can use lambdas for dict merging."""
        obj = Inherit(transform=lambda x: {**x, "new_key": "new_value"})
        obj.parent_value = {"key1": "val1"}
        assert obj.resolve() == {"key1": "val1", "new_key": "new_value"}


class TestInheritInExperiment:
    """Integration tests: INHERIT used with Experiment.extend()."""

    def test_basic_inherit_pass_through(self):
        """
        PARAM = INHERIT in a sub-experiment should result in the parent's value
        being used after resolution during initialize().
        """
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            iso.glob["PARAM_A"] = INHERIT

            experiment = Experiment.extend(
                experiment_path=base_path,
                base_path=iso.path,
                namespace="test_inherit",
                glob=iso.glob,
            )

            # Before resolution, the parameter should be an Inherit object
            assert isinstance(experiment.parameters["PARAM_A"], Inherit)

            @experiment
            def run(e):
                # During execution, INHERIT should have been resolved
                assert e.PARAM_A == 10

            experiment.run()

            # After run, parameter should be the resolved concrete value
            assert experiment.parameters["PARAM_A"] == 10

    def test_inherit_with_transform(self):
        """PARAM = INHERIT(fn) should apply fn to the parent's value."""
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            iso.glob["PARAM_A"] = INHERIT(lambda x: x * 3)

            experiment = Experiment.extend(
                experiment_path=base_path,
                base_path=iso.path,
                namespace="test_inherit_transform",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                assert e.PARAM_A == 30  # 10 * 3

            experiment.run()

            assert experiment.parameters["PARAM_A"] == 30

    def test_inherit_list_append(self):
        """INHERIT with a list-extending transform should work."""
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            iso.glob["PARAM_B"] = INHERIT(lambda x: x + [4, 5])

            experiment = Experiment.extend(
                experiment_path=base_path,
                base_path=iso.path,
                namespace="test_inherit_list",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                assert e.PARAM_B == [1, 2, 3, 4, 5]

            experiment.run()

    def test_inherit_mixed_with_overrides(self):
        """
        Some params use INHERIT, others are overridden normally.
        Non-INHERIT params should work as before.
        """
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            iso.glob["PARAM_A"] = INHERIT
            iso.glob["PARAM_C"] = "overridden"

            experiment = Experiment.extend(
                experiment_path=base_path,
                base_path=iso.path,
                namespace="test_inherit_mixed",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                assert e.PARAM_A == 10
                assert e.PARAM_C == "overridden"

            experiment.run()

    def test_inherit_missing_parent_parameter_raises(self):
        """
        Using INHERIT for a parameter that does not exist in the parent
        should raise InheritError when resolving.
        """
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            iso.glob["NONEXISTENT_PARAM"] = INHERIT

            experiment = Experiment.extend(
                experiment_path=base_path,
                base_path=iso.path,
                namespace="test_inherit_missing",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            with pytest.raises(InheritError, match="NONEXISTENT_PARAM"):
                experiment.run()

    def test_inherit_getattr_before_resolve_raises(self):
        """
        Accessing an INHERIT parameter via experiment.PARAM before
        initialize() should raise RuntimeError.
        """
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            iso.glob["PARAM_A"] = INHERIT

            experiment = Experiment.extend(
                experiment_path=base_path,
                base_path=iso.path,
                namespace="test_inherit_guard",
                glob=iso.glob,
            )

            with pytest.raises(RuntimeError, match="unresolved INHERIT"):
                _ = experiment.PARAM_A

    def test_inherit_resolved_values_in_metadata(self):
        """
        After resolution, concrete values (not Inherit objects) should
        appear in experiment_meta.json.
        """
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
            iso.glob["PARAM_A"] = INHERIT(lambda x: x + 5)

            experiment = Experiment.extend(
                experiment_path=base_path,
                base_path=iso.path,
                namespace="test_inherit_meta",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Read the saved metadata file
            with open(experiment.metadata_path, "r") as f:
                metadata = json.load(f)

            param_meta = metadata["parameters"]["PARAM_A"]
            assert param_meta["value"] == 15  # 10 + 5
            assert param_meta["usable"] is True

    def test_multi_level_inherit(self):
        """
        Base(PARAM_A=10) -> Child(PARAM_A=INHERIT(x*2)) -> Grandchild(PARAM_A=INHERIT)
        should resolve Grandchild's PARAM_A to 20.
        """
        base_path = os.path.join(ASSETS_PATH, "mock_inherit_base_experiment.py")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create child experiment file that uses INHERIT
            child_path = os.path.join(temp_dir, "child_experiment.py")
            with open(child_path, "w") as f:
                f.write(f"""
from pycomex.functional.experiment import Experiment
from pycomex.functional.inherit import INHERIT
from pycomex.utils import file_namespace, folder_path

PARAM_A = INHERIT(lambda x: x * 2)

experiment = Experiment.extend(
    experiment_path="{base_path}",
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)

experiment.run_if_main()
""")

            # Now create grandchild that extends the child
            with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
                iso.glob["PARAM_A"] = INHERIT

                experiment = Experiment.extend(
                    experiment_path=child_path,
                    base_path=iso.path,
                    namespace="test_grandchild",
                    glob=iso.glob,
                )

                @experiment
                def run(e):
                    assert e.PARAM_A == 20  # 10 * 2 from child

                experiment.run()

                assert experiment.parameters["PARAM_A"] == 20
