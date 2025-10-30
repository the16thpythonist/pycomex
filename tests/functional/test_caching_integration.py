"""Integration tests for __CACHING__ parameter with Experiment class."""

import os
import sys
import tempfile

from pycomex.functional.cache import CacheBackend
from pycomex.functional.experiment import Experiment
from pycomex.testing import ConfigIsolation, ExperimentIsolation


def test_caching_parameter_disables_cache():
    """
    Test that setting __CACHING__ = False in experiment parameters
    properly disables both loading and saving of cache.
    """
    with ConfigIsolation() as config, ExperimentIsolation(
        sys.argv, glob_mod={"__CACHING__": False}
    ) as iso:
        # Create experiment with __CACHING__ = False
        experiment = Experiment(
            base_path=iso.path,
            namespace="test_caching",
            glob=iso.glob,
        )

        call_count = 0

        @experiment.cache.cached("test_function")
        def test_function():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # First call - should execute
        result1 = test_function()
        assert result1 == "result_1"
        assert call_count == 1

        # Verify NO cache file was created
        cache_dir = os.path.join(iso.path, ".cache")
        cache_file = os.path.join(cache_dir, "test_function.pkl")
        assert not os.path.exists(
            cache_file
        ), "Cache file should not exist when __CACHING__ = False"

        # Second call - should execute again (no caching)
        result2 = test_function()
        assert result2 == "result_2"
        assert call_count == 2

        # Still no cache file
        assert not os.path.exists(cache_file)


def test_caching_parameter_enabled_by_default():
    """
    Test that caching is enabled by default (backward compatibility).
    """
    with ConfigIsolation() as config, ExperimentIsolation(sys.argv) as iso:
        # Create experiment without explicitly setting __CACHING__
        experiment = Experiment(
            base_path=iso.path,
            namespace="test_caching_default",
            glob=iso.glob,
        )

        call_count = 0

        @experiment.cache.cached("default_function")
        def default_function():
            nonlocal call_count
            call_count += 1
            return "cached_result"

        # First call
        result1 = default_function()
        assert result1 == "cached_result"
        assert call_count == 1

        # Verify cache file WAS created (might be compressed)
        cache_dir = os.path.join(iso.path, ".cache")
        cache_file = os.path.join(cache_dir, "default_function.pkl")
        cache_file_gz = os.path.join(cache_dir, "default_function.pkl.gz")
        assert os.path.exists(cache_file) or os.path.exists(
            cache_file_gz
        ), "Cache file should exist by default"

        # Second call - should use cache
        result2 = default_function()
        assert result2 == "cached_result"
        assert call_count == 1  # Not called again


def test_caching_parameter_can_be_toggled():
    """
    Test that __CACHING__ parameter can be changed dynamically.
    """
    with ConfigIsolation() as config, ExperimentIsolation(
        sys.argv, glob_mod={"__CACHING__": True}
    ) as iso:
        # Start with caching enabled
        experiment = Experiment(
            base_path=iso.path,
            namespace="test_caching_toggle",
            glob=iso.glob,
        )

        call_count = 0

        @experiment.cache.cached("toggle_function")
        def toggle_function():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # First call with caching enabled
        result1 = toggle_function()
        assert result1 == "result_1"
        assert call_count == 1

        # Verify cache file exists (might be compressed)
        cache_dir = os.path.join(iso.path, ".cache")
        cache_file = os.path.join(cache_dir, "toggle_function.pkl")
        cache_file_gz = os.path.join(cache_dir, "toggle_function.pkl.gz")
        assert os.path.exists(cache_file) or os.path.exists(cache_file_gz)

        # Second call - should use cache
        result2 = toggle_function()
        assert result2 == "result_1"  # Same cached result
        assert call_count == 1

        # Now disable caching via parameter
        experiment.parameters["__CACHING__"] = False
        experiment.update_parameters_special()

        # Third call - should bypass cache and execute
        result3 = toggle_function()
        assert result3 == "result_2"  # New result
        assert call_count == 2

        # Re-enable caching
        experiment.parameters["__CACHING__"] = True
        experiment.update_parameters_special()

        # Fourth call - should use old cached result
        result4 = toggle_function()
        assert result4 == "result_1"  # Original cached result
        assert call_count == 2  # No new execution


def test_caching_with_compression_disabled():
    """
    Test that __CACHING__ = False works with compression disabled.
    """
    with ConfigIsolation() as config, ExperimentIsolation(
        sys.argv, glob_mod={"__CACHING__": False}
    ) as iso:
        experiment = Experiment(
            base_path=iso.path,
            namespace="test_no_compression",
            glob=iso.glob,
        )

        # Manually set compression to False
        experiment.cache.compress = False

        @experiment.cache.cached("no_compress_function")
        def no_compress_function():
            return "uncompressed_result"

        result = no_compress_function()
        assert result == "uncompressed_result"

        # Verify no cache files (compressed or uncompressed)
        cache_dir = os.path.join(iso.path, ".cache")
        cache_file = os.path.join(cache_dir, "no_compress_function.pkl")
        cache_file_gz = os.path.join(cache_dir, "no_compress_function.pkl.gz")

        assert not os.path.exists(cache_file)
        assert not os.path.exists(cache_file_gz)
