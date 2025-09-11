import json
import os
import pickle
import tempfile
from unittest.mock import Mock, patch

import joblib
import pytest

from pycomex.functional.cache import CacheBackend, ExperimentCache


class TestExperimentCache:
    """
    Test suite for the ExperimentCache class functionality including
    caching decorators, save/load operations, and backend support.
    """

    def test_init_creates_cache_directory(self):
        """
        ExperimentCache should create the cache directory if it doesn't exist
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = os.path.join(temp_dir, "cache")
            assert not os.path.exists(cache_path)

            cache = ExperimentCache(path=cache_path)

            assert os.path.exists(cache_path)
            assert cache.path == cache_path

    def test_init_with_existing_directory(self):
        """
        ExperimentCache should work with existing directories
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)

            assert cache.path == temp_dir
            assert os.path.exists(temp_dir)

    def test_save_at_pickle_backend(self):
        """
        save_at should save data using pickle backend correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = {"key": "value", "number": 42}

            result = cache.save_at(
                data=test_data,
                name="test_data",
                folder_path=temp_dir,
                backend=CacheBackend.PICKLE,
            )

            assert result is True
            expected_file = os.path.join(temp_dir, "test_data.pkl")
            assert os.path.exists(expected_file)

            # Verify data can be loaded back
            with open(expected_file, "rb") as f:
                loaded_data = pickle.load(f)
            assert loaded_data == test_data

    def test_save_at_joblib_backend(self):
        """
        save_at should save data using joblib backend correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = [1, 2, 3, 4, 5]

            result = cache.save_at(
                data=test_data,
                name="test_data",
                folder_path=temp_dir,
                backend=CacheBackend.JOBLIB,
            )

            assert result is True
            expected_file = os.path.join(temp_dir, "test_data.joblib")
            assert os.path.exists(expected_file)

            # Verify data can be loaded back
            loaded_data = joblib.load(expected_file)
            assert loaded_data == test_data

    def test_save_at_json_backend(self):
        """
        save_at should save data using JSON backend correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = {"json_key": "json_value", "list": [1, 2, 3]}

            result = cache.save_at(
                data=test_data,
                name="test_data",
                folder_path=temp_dir,
                backend=CacheBackend.JSON,
            )

            assert result is True
            expected_file = os.path.join(temp_dir, "test_data.json")
            assert os.path.exists(expected_file)

            # Verify data can be loaded back
            with open(expected_file) as f:
                loaded_data = json.load(f)
            assert loaded_data == test_data

    def test_save_with_scope_creates_nested_folders(self):
        """
        save method should create nested folder structure based on scope
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = "test_data"
            scope = ("level1", "level2", "level3")

            result = cache.save(
                data=test_data,
                name="nested_data",
                scope=scope,
                backend=CacheBackend.PICKLE,
            )

            assert result is True
            expected_folder = os.path.join(temp_dir, "level1", "level2", "level3")
            expected_file = os.path.join(expected_folder, "nested_data.pkl")

            assert os.path.exists(expected_folder)
            assert os.path.exists(expected_file)

    def test_load_from_pickle_file(self):
        """
        load_from should load data from pickle files correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = {"load_test": "pickle_data"}

            # First save data
            cache.save_at(
                data=test_data,
                name="load_test",
                folder_path=temp_dir,
                backend=CacheBackend.PICKLE,
            )

            # Then load it
            loaded_data = cache.load_from(temp_dir, "load_test")
            assert loaded_data == test_data

    def test_load_from_joblib_file(self):
        """
        load_from should load data from joblib files correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = [10, 20, 30]

            # First save data
            cache.save_at(
                data=test_data,
                name="load_test",
                folder_path=temp_dir,
                backend=CacheBackend.JOBLIB,
            )

            # Then load it
            loaded_data = cache.load_from(temp_dir, "load_test")
            assert loaded_data == test_data

    def test_load_from_json_file(self):
        """
        load_from should load data from JSON files correctly
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = {"json_load_test": True, "number": 100}

            # First save data
            cache.save_at(
                data=test_data,
                name="load_test",
                folder_path=temp_dir,
                backend=CacheBackend.JSON,
            )

            # Then load it
            loaded_data = cache.load_from(temp_dir, "load_test")
            assert loaded_data == test_data

    def test_load_from_auto_discovers_backend(self):
        """
        load_from should auto-discover the correct backend based on file extension
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)

            # Save data with different backends
            pickle_data = "pickle_content"
            joblib_data = "joblib_content"
            json_data = "json_content"

            cache.save_at(pickle_data, "pickle_file", temp_dir, CacheBackend.PICKLE)
            cache.save_at(joblib_data, "joblib_file", temp_dir, CacheBackend.JOBLIB)
            cache.save_at(json_data, "json_file", temp_dir, CacheBackend.JSON)

            # Load and verify each one is loaded correctly
            assert cache.load_from(temp_dir, "pickle_file") == pickle_data
            assert cache.load_from(temp_dir, "joblib_file") == joblib_data
            assert cache.load_from(temp_dir, "json_file") == json_data

    def test_load_from_raises_filenotfound_for_missing_file(self):
        """
        load_from should raise FileNotFoundError when no cache file exists
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)

            with pytest.raises(FileNotFoundError) as excinfo:
                cache.load_from(temp_dir, "nonexistent_file")

            assert "No cache file found for 'nonexistent_file'" in str(excinfo.value)

    def test_load_with_scope(self):
        """
        load method should construct correct path from scope and load data
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            test_data = "scoped_data"
            scope = ("scope1", "scope2")

            # Save data with scope
            cache.save(test_data, "scoped_file", scope, CacheBackend.PICKLE)

            # Load data with scope
            loaded_data = cache.load("scoped_file", scope)
            assert loaded_data == test_data

    def test_cached_decorator_caches_function_result(self):
        """
        cached decorator should cache function results and return cached value on subsequent calls
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            call_count = 0

            @cache.cached("expensive_function")
            def expensive_function(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            # First call should execute function
            result1 = expensive_function(5)
            assert result1 == 10
            assert call_count == 1

            # Second call should use cache
            result2 = expensive_function(5)
            assert result2 == 10
            assert call_count == 1  # Function not called again

    def test_cached_decorator_with_tuple_scope(self):
        """
        cached decorator should work with tuple scopes
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            call_count = 0

            @cache.cached("scoped_function", scope=("test", "scope"))
            def scoped_function(value):
                nonlocal call_count
                call_count += 1
                return f"processed_{value}"

            # First call
            result1 = scoped_function("data")
            assert result1 == "processed_data"
            assert call_count == 1

            # Verify cache file exists in correct location
            cache_file_path = os.path.join(
                temp_dir, "test", "scope", "scoped_function.pkl"
            )
            assert os.path.exists(cache_file_path)

            # Second call should use cache
            result2 = scoped_function("data")
            assert result2 == "processed_data"
            assert call_count == 1

    def test_cached_decorator_with_callable_scope(self):
        """
        cached decorator should work with callable scopes
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_experiment = Mock()
            mock_experiment.parameter1 = "param1"
            mock_experiment.parameter2 = "param2"

            cache = ExperimentCache(
                path=temp_dir, experiment=mock_experiment, compress=False
            )
            call_count = 0

            def dynamic_scope(experiment):
                return (experiment.parameter1, experiment.parameter2)

            @cache.cached("dynamic_function", scope=dynamic_scope)
            def dynamic_function(x):
                nonlocal call_count
                call_count += 1
                return x + "_result"

            # First call
            result1 = dynamic_function("test")
            assert result1 == "test_result"
            assert call_count == 1

            # Verify cache file exists in correct location
            cache_file_path = os.path.join(
                temp_dir, "param1", "param2", "dynamic_function.pkl"
            )
            assert os.path.exists(cache_file_path)

            # Second call should use cache
            result2 = dynamic_function("test")
            assert result2 == "test_result"
            assert call_count == 1

    def test_cached_decorator_invalid_scope_raises_error(self):
        """
        cached decorator should raise ValueError for invalid scope types
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)

            with pytest.raises(ValueError) as excinfo:

                @cache.cached("test_function", scope="invalid_scope")
                def test_function():
                    return "test"

                test_function()

            assert "Scope must be a callable or a tuple" in str(excinfo.value)

    def test_cached_decorator_with_different_backends(self):
        """
        cached decorator should work with different cache backends
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)

            @cache.cached("pickle_func", backend=CacheBackend.PICKLE)
            def pickle_function():
                return {"backend": "pickle"}

            @cache.cached("joblib_func", backend=CacheBackend.JOBLIB)
            def joblib_function():
                return ["joblib", "backend"]

            @cache.cached("json_func", backend=CacheBackend.JSON)
            def json_function():
                return {"backend": "json"}

            # Call functions
            pickle_result = pickle_function()
            joblib_result = joblib_function()
            json_result = json_function()

            # Verify results
            assert pickle_result == {"backend": "pickle"}
            assert joblib_result == ["joblib", "backend"]
            assert json_result == {"backend": "json"}

            # Verify correct files were created
            assert os.path.exists(os.path.join(temp_dir, "pickle_func.pkl"))
            assert os.path.exists(os.path.join(temp_dir, "joblib_func.joblib"))
            assert os.path.exists(os.path.join(temp_dir, "json_func.json"))

    def test_cache_backend_enum_values(self):
        """
        CacheBackend enum should have correct string values
        """
        assert CacheBackend.PICKLE.value == "pickle"
        assert CacheBackend.JOBLIB.value == "joblib"
        assert CacheBackend.JSON.value == "json"

    def test_default_cache_backend(self):
        """
        ExperimentCache should use PICKLE as default backend
        """
        assert ExperimentCache.DEFAULT_CACHE_BACKEND == CacheBackend.PICKLE

    def test_cached_decorator_caches_by_function_name_not_arguments(self):
        """
        cached decorator caches by function name only, not by arguments.
        This means all calls to the same cached function return the same cached result.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ExperimentCache(path=temp_dir, compress=False)
            call_count = 0

            @cache.cached("arg_function")
            def arg_function(a, b, c=None, d="default"):
                nonlocal call_count
                call_count += 1
                return f"{a}-{b}-{c}-{d}"

            # First call with specific arguments
            result1 = arg_function(1, 2)
            assert result1 == "1-2-None-default"
            assert call_count == 1

            # Subsequent calls with different arguments should return cached result
            result2 = arg_function(1, 2, c=3)  # Different args but same cache key
            result3 = arg_function(
                1, 2, d="custom"
            )  # Different args but same cache key

            # All results should be the same as the first cached result
            assert result2 == "1-2-None-default"  # Same as result1 (cached)
            assert result3 == "1-2-None-default"  # Same as result1 (cached)
            assert call_count == 1  # Function only called once

            # Verify cache file exists
            cache_file = os.path.join(temp_dir, "arg_function.pkl")
            assert os.path.exists(cache_file)
