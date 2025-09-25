"""Experiment caching system for PyComex.

This module provides a flexible caching system that allows expensive computations
to be cached to disk and reused across experiment runs. The system supports
multiple serialization backends (pickle, joblib, JSON) and provides a decorator-based
API for transparent caching of function results.

The caching system is designed to work with the PyComex experiment framework,
allowing computational results to be organized in a hierarchical folder structure
based on scope parameters. This enables fine-grained cache management and
organization of cached results.

Example:
    Basic usage with the ExperimentCache class:

    .. code-block:: python

        from pycomex.functional.cache import ExperimentCache

        # Initialize cache in experiment folder
        cache = ExperimentCache('/path/to/experiment/cache')

        # Use decorator to cache expensive function
        @cache.cached('expensive_computation', scope=('preprocessing',))
        def expensive_computation(data):
            # Some expensive computation
            return processed_data

        # First call computes and caches result
        result = expensive_computation(my_data)

        # Subsequent calls load from cache
        cached_result = expensive_computation(my_data)  # Loaded from disk

    Using different cache backends:

    .. code-block:: python

        from pycomex.functional.cache import CacheBackend

        # Cache using joblib (better for NumPy arrays)
        @cache.cached('ml_model', backend=CacheBackend.JOBLIB)
        def train_model(X, y):
            return trained_model

        # Cache using JSON (for simple data structures)
        @cache.cached('metadata', backend=CacheBackend.JSON)
        def compute_metadata():
            return {'count': 100, 'mean': 0.5}

    Dynamic scoping based on experiment parameters:

    .. code-block:: python

        def dynamic_scope(experiment):
            return ('model', experiment.get_parameter('model_type'))

        @cache.cached('training_data', scope=dynamic_scope)
        def prepare_training_data():
            return processed_training_data

Design Rationale:
    The caching system is designed to address common patterns in computational
    experiments where the same expensive operations are repeated across different
    experiment runs. By providing automatic caching with configurable backends
    and scope management, researchers can focus on their experiments rather than
    manual cache management.

    The hierarchical scope system allows for logical organization of cached
    results, making it easy to invalidate specific cache entries or understand
    the structure of cached data. This specifically enables individual experiments 
    to either maintain their own cache scope or share with others, as needed.
"""

import gzip
import os
import pickle
import subprocess
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, Optional

import joblib

from pycomex.functional.testing import MockExperiment


class CacheBackend(Enum):
    """Enumeration of supported cache serialization backends.

    This enum defines the different serialization methods available for
    caching data to disk. Each backend has different characteristics and
    use cases:

    - PICKLE: Python's native serialization format, good for general Python objects
    - JOBLIB: Optimized for NumPy arrays and scikit-learn objects, more efficient for large arrays
    - JSON: Human-readable format, limited to JSON-serializable data types

    :cvar PICKLE: Standard Python pickle serialization
    :cvar JOBLIB: Joblib serialization (optimized for scientific data)
    :cvar JSON: JSON serialization (human-readable, limited data types)
    """

    PICKLE = "pickle"
    JOBLIB = "joblib"
    JSON = "json"


class ExperimentCache:
    """Main caching interface for PyComex experiments.

    This class provides a comprehensive caching system that allows expensive
    computations to be cached to disk and reused across experiment runs.
    The cache organizes data in a hierarchical folder structure based on
    scope parameters, enabling fine-grained cache management.

    The class supports multiple serialization backends and provides both
    decorator-based and direct API access for caching operations. It's
    designed to integrate seamlessly with PyComex experiments while being
    flexible enough for standalone use.

    Key Features:
        - Multiple serialization backends (pickle, joblib, JSON)
        - Optional gzip compression to reduce storage space
        - Hierarchical organization using scope tuples
        - Decorator-based transparent caching
        - Auto-discovery of cached files (both compressed and uncompressed)
        - Integration with PyComex experiment framework

    Example:
        Basic cache setup and usage:

        .. code-block:: python

            # Initialize cache in experiment directory with compression (default)
            cache = ExperimentCache('/path/to/experiment/cache')

            # Initialize cache without compression
            cache_uncompressed = ExperimentCache('/path/to/experiment/cache', compress=False)

            # Cache a function with static scope
            @cache.cached('preprocessing', scope=('data', 'clean'))
            def clean_data(raw_data):
                # Expensive data cleaning operation
                return cleaned_data

            # Cache with dynamic scope based on experiment
            def model_scope(exp):
                return ('models', exp.get_parameter('model_type'))

            @cache.cached('trained_model', scope=model_scope)
            def train_model(X, y):
                # Expensive model training
                return trained_model

    Design Rationale:
        The hierarchical scope system allows for logical organization of
        cached results, making it easy to understand cache structure and
        selectively invalidate cache entries. The decorator pattern provides
        a clean API that doesn't clutter function definitions while still
        providing powerful caching capabilities.

        Multiple backend support ensures that users can choose the most
        appropriate serialization method for their data types, optimizing
        both storage efficiency and loading performance.

    :ivar path: Base directory path for storing cache files
    :type path: str
    :ivar experiment: Optional reference to the associated experiment instance
    :type experiment: Optional['Experiment']
    :ivar compress: Whether to use gzip compression for cache files
    :type compress: bool
    :cvar DEFAULT_CACHE_BACKEND: Default serialization backend to use
    :type DEFAULT_CACHE_BACKEND: CacheBackend
    """

    DEFAULT_CACHE_BACKEND = CacheBackend.PICKLE

    def __init__(
        self,
        path: str,
        experiment: "Experiment" = MockExperiment(),
        compress: bool = True,
    ) -> None:
        """Initialize an ExperimentCache instance.

        Creates a new cache instance with the specified base directory and
        compression settings. If the directory doesn't exist, it will be
        created automatically.

        :param path: Absolute path to the base cache directory. This directory
                    will be created if it doesn't exist.
        :type path: str
        :param experiment: Reference to the associated experiment instance.
                          Used for dynamic scope resolution and logging.
                          Defaults to a mock experiment if not provided.
        :type experiment: 'Experiment'
        :param compress: Whether to use gzip compression for cache files.
                        When True, files are saved with .gz extensions and
                        compressed. When False, files are saved uncompressed.
                        Defaults to True for space efficiency.
        :type compress: bool

        :raises OSError: If the cache directory cannot be created due to
                        permission issues or invalid path.
        """

        self.path = path
        self.experiment = experiment
        self.compress = compress
        self.enabled = True  # Cache is enabled by default

        # We want to make sure that this path actually exists on the disk and if it does not
        # we want ot create it.
        os.makedirs(self.path, exist_ok=True)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable cache loading.

        When disabled, the cache will not load existing cached results, forcing
        recomputation. New results will still be saved to cache.

        :param enabled: True to enable cache loading, False to disable
        :type enabled: bool
        """
        self.enabled = enabled

    def _compress_file(self, file_path: str) -> bool:
        """Compress a file using pigz (parallelized gzip) or fallback to gzip.

        This method attempts to use pigz for faster parallelized compression.
        If pigz is not available, it falls back to standard gzip compression.

        :param file_path: Path to the file to compress
        :type file_path: str

        :returns: True if compression was successful, False otherwise
        :rtype: bool
        """
        compressed_path = f"{file_path}.gz"

        try:
            # Try to use pigz for faster parallelized compression
            result = subprocess.run(
                ["pigz", "-c", file_path],
                stdout=open(compressed_path, "wb"),
                stderr=subprocess.PIPE,
                check=True,
            )
            # Remove the original uncompressed file
            os.remove(file_path)
            return True

        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to standard gzip if pigz is not available
            try:
                with open(file_path, "rb") as f_in:
                    with gzip.open(compressed_path, "wb") as f_out:
                        f_out.writelines(f_in)
                # Remove the original uncompressed file
                os.remove(file_path)
                return True
            except Exception:
                # If compression fails completely, keep the uncompressed file
                if os.path.exists(compressed_path):
                    os.remove(compressed_path)
                return False

    def _decompress_file(self, compressed_path: str, output_path: str) -> bool:
        """Decompress a gzipped file.

        :param compressed_path: Path to the compressed file
        :type compressed_path: str
        :param output_path: Path where the decompressed file should be written
        :type output_path: str

        :returns: True if decompression was successful, False otherwise
        :rtype: bool
        """
        try:
            with gzip.open(compressed_path, "rb") as f_in:
                with open(output_path, "wb") as f_out:
                    f_out.writelines(f_in)
            return True
        except Exception:
            return False

    def cached(
        self,
        name: str,
        scope: Callable[["Experiment"], tuple] | tuple = tuple(),
        backend: CacheBackend = DEFAULT_CACHE_BACKEND,
    ) -> Callable:
        """Decorator for transparent function result caching.

        This decorator wraps a function to automatically cache its results
        to disk. On the first call, the function is executed and its result
        is saved to cache. Subsequent calls with the same cache key load
        the result directly from disk without executing the function.

        The cache key is determined by the combination of the name parameter
        and the resolved scope. The scope can be either a static tuple or
        a callable that dynamically determines the scope based on the
        experiment instance.

        Example:

        .. code-block:: python

            @cache.cached('data_processing', scope=('preprocessing', 'step1'))
            def process_raw_data(data):
                # Expensive processing operation
                time.sleep(10)  # Simulate expensive operation
                return processed_data

            # First call: executes function and caches result
            result1 = process_raw_data(my_data)

            # Second call: loads from cache instantly
            result2 = process_raw_data(my_data)  # Same result, no computation

        :param name: Unique identifier for the cached item within its scope.
                    Used as the base filename for the cached data.
        :type name: str
        :param scope: Either a tuple of strings defining the cache folder structure,
                     or a callable that takes an Experiment instance and returns
                     such a tuple. Empty tuple means root cache directory.
        :type scope: Callable[['Experiment'], tuple] | tuple
        :param backend: Serialization backend to use for caching the data.
                       Defaults to DEFAULT_CACHE_BACKEND.
        :type backend: CacheBackend

        :raises ValueError: If scope is neither a callable nor a tuple

        :returns: Decorator function that wraps the target function with caching logic
        :rtype: Callable
        """

        def decorator(func: Callable) -> Callable:
            """Inner decorator function that applies caching logic.

            :param func: The function to be wrapped with caching
            :type func: Callable
            :returns: Wrapped function with caching behavior
            :rtype: Callable
            """

            def wrapper(*args, **kwargs):
                """Wrapper function that implements the caching logic.

                This function first attempts to load cached results, and only
                executes the original function if no valid cache is found.
                After execution, results are automatically saved to cache.

                :param args: Positional arguments passed to the original function
                :param kwargs: Keyword arguments passed to the original function
                :returns: Either cached result or newly computed result
                :rtype: Any
                """

                # --- Determine scope ---
                # The scope usually would be a tuple of string values that indicate the folder structure
                # where to search for the cache file. But that may be limiting in certain cases so the
                # scope may also be a callback function that receives the experiment instance as a argument
                # and should then return a viable scope tuple.
                if callable(scope):
                    current_scope: tuple = scope(self.experiment)
                elif isinstance(scope, tuple):
                    current_scope: tuple = scope
                else:
                    raise ValueError("Scope must be a callable or a tuple")

                # --- Try to load from cache ---
                # This is the whole point of the cache. If the entity is already cached on the disk
                # we dont even execute the function but rather load the data from the disk.
                # However, this is only done if caching is enabled.
                if self.enabled:
                    try:
                        result = self.load(name=name, scope=current_scope)
                        self.experiment.log(f'Loaded "{name}" from cache!')
                        return result
                    except FileNotFoundError:
                        pass

                # --- Call the actual function ---
                # Only as a fallback option we actually call the function to compute the result.
                result = func(*args, **kwargs)

                # --- Save to cache ---
                # After we computed the result we want to save it to the disk so that next time
                # we can load it from the disk instead of recomputing it.
                time_start = time.time()
                self.save(
                    data=result,
                    name=name,
                    scope=current_scope,
                    backend=backend,
                )
                self.experiment.log(
                    f'Saved "{name}" to cache in {time.time() - time_start:.2f} seconds!'
                )

                return result

            return wrapper

        return decorator

    def save(
        self,
        data: Any,
        name: str,
        scope: tuple[str, ...],
        backend: CacheBackend = DEFAULT_CACHE_BACKEND,
    ) -> bool:
        """Save data to cache with scope-based organization. Saves the given `data`
        to the cache directory under a folder structure defined by the `scope` tuple.

        :param data: The data object to be cached. Must be serializable by
                    the chosen backend.
        :type data: Any
        :param name: Base name for the cache file (without extension).
                    Extensions are added automatically based on backend.
        :type name: str
        :param scope: Tuple of strings defining the nested folder structure
                     within the cache directory. Empty tuple saves to root.
        :type scope: tuple[str, ...]
        :param backend: Serialization backend to use for saving the data.
        :type backend: CacheBackend

        :raises OSError: If the cache directory structure cannot be created
                        due to permission issues.

        :returns: True if the file was successfully saved and exists on disk,
                 False otherwise.
        :rtype: bool
        """

        # --- constructing path from scope ---
        # What we get as the parameter of this method is the "scope" this is a tuple
        # of string values that indicates the folder structure where the cache file should be saved.
        # for example, the scope ('preprocessing', 'step1') would indicate that the file should be saved
        # in the folder "preprocessing/step1" inside the base cache path.
        folder_path = os.path.join(self.path, *scope)
        # This will make sure that this path actually exists.
        os.makedirs(folder_path, exist_ok=True)

        # --- saving the data ---
        # This method implements the actual saving of the data to the disk using the specified backend.
        return self.save_at(
            data=data,
            name=name,
            folder_path=folder_path,
            backend=backend,
        )

    def save_at(
        self,
        data: Any,
        name: str,
        folder_path: str,
        backend: CacheBackend = DEFAULT_CACHE_BACKEND,
    ) -> bool:
        """Save data directly to a specific folder path. Saves the given `data`
        to the specified absolute `folder_path` using the provided `name` as the
        base filename. The appropriate file extension is added automatically
        based on the chosen serialization `backend`.

        Backend-Specific Behavior:
            - PICKLE: Uses Python's pickle module with binary mode
            - JOBLIB: Uses joblib's optimized serialization
            - JSON: Uses standard JSON with UTF-8 encoding

        :param data: The data object to be serialized and saved.
                    Must be compatible with the chosen backend.
        :type data: Any
        :param name: Base filename without extension. The appropriate
                    extension (.pkl, .joblib, .json) is added automatically.
        :type name: str
        :param folder_path: Absolute path to the folder where the file
                           should be saved. Folder must exist.
        :type folder_path: str
        :param backend: Serialization backend to use for saving.
        :type backend: CacheBackend

        :raises ValueError: If an unsupported backend is specified
        :raises IOError: If file writing fails due to permissions or disk space
        :raises TypeError: If data is not serializable with the chosen backend

        :returns: True if the file was successfully written and exists,
                 False otherwise.
        :rtype: bool
        """

        # --- Cache backends ---
        # Based on the different cache backends we need to invoke different saving mechanisms.

        if backend == CacheBackend.PICKLE:
            file_name = f"{name}.pkl"
            path = os.path.join(folder_path, file_name)
            with open(path, "wb") as f:
                pickle.dump(data, f)

        elif backend == CacheBackend.JOBLIB:
            file_name = f"{name}.joblib"
            path = os.path.join(folder_path, file_name)
            joblib.dump(data, path)

        elif backend == CacheBackend.JSON:
            import json

            file_name = f"{name}.json"
            path = os.path.join(folder_path, file_name)
            with open(path, "w") as f:
                json.dump(data, f)

        # Apply compression if requested
        if self.compress:
            if self._compress_file(path):
                # Update path to point to compressed file
                path = f"{path}.gz"

        # --- checking if the file exists ---
        # The return value of the function should indicate whether it was possible to
        # wirte the file to the disk or not.
        return os.path.exists(path)

    def load_from(
        self,
        folder_path: str,
        name: str,
    ) -> Any:
        """
        Load cached data from a specific folder with auto-discovery. Loads the
        data with the given `name` (without file extension!) from the specified
        `folder_path`.

        :param folder_path: Absolute path to the folder containing the
                           cached file to load.
        :type folder_path: str
        :param name: Base name of the cached file (without extension).
                    The method will search for files with this base name
                    and supported extensions.
        :type name: str

        :raises FileNotFoundError: If no cache file with the specified name
                                  is found in the folder, with detailed
                                  information about the search location.
        :raises IOError: If the file exists but cannot be read due to
                        permissions or corruption.
        :raises ValueError: If the file format is recognized but contains
                           invalid data that cannot be deserialized.

        :returns: The deserialized data object loaded from the cache file.
        :rtype: Any
        """

        # --- Auto-discover which file extension exists ---
        # We check for all possible file extensions (both compressed and uncompressed) and use the one that exists
        possible_backends = [
            (CacheBackend.PICKLE, f"{name}.pkl.gz", True),
            (CacheBackend.PICKLE, f"{name}.pkl", False),
            (CacheBackend.JOBLIB, f"{name}.joblib.gz", True),
            (CacheBackend.JOBLIB, f"{name}.joblib", False),
            (CacheBackend.JSON, f"{name}.json.gz", True),
            (CacheBackend.JSON, f"{name}.json", False),
        ]

        found_backend = None
        found_path = None
        found_compressed = None

        for backend, file_name, is_compressed in possible_backends:
            file_path = os.path.join(folder_path, file_name)
            if os.path.exists(file_path):
                found_backend = backend
                found_path = file_path
                found_compressed = is_compressed
                break

        # --- Check if any file was found ---
        # If no file was found at all we need to inform the user that probably ghe given
        # name or scope was wrong.
        if found_backend is None:
            raise FileNotFoundError(
                f"No cache file found for '{name}' in folder '{folder_path}'"
            )

        # --- Load data based on discovered backend ---
        # If file is compressed, decompress it first to a temporary location
        actual_file_path = found_path
        temp_file_path = None

        if found_compressed:
            # Create temporary uncompressed file
            temp_file_path = found_path[:-3]  # Remove .gz extension
            if not self._decompress_file(found_path, temp_file_path):
                raise OSError(f"Failed to decompress cache file: {found_path}")
            actual_file_path = temp_file_path

        try:
            if found_backend == CacheBackend.PICKLE:
                with open(actual_file_path, "rb") as f:
                    return pickle.load(f)

            elif found_backend == CacheBackend.JOBLIB:
                return joblib.load(actual_file_path)

            elif found_backend == CacheBackend.JSON:
                import json

                with open(actual_file_path) as f:
                    return json.load(f)

        finally:
            # Clean up temporary file if it was created
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def load(
        self,
        name: str,
        scope: tuple[str, ...],
    ) -> Any:
        """
        High-level method for loading cached data using the same scope-based
        organization system used for saving. Loads and returns data with the
        given `name` - only from the scope represented by the `scope` tuple.

        :param name: Base name of the cached item to load (without extension).
                    This should match the name used when saving the data.
        :type name: str
        :param scope: Tuple of strings defining the nested folder path
                     within the cache directory. Must match the scope
                     used when saving the data.
        :type scope: tuple[str, ...]

        :raises FileNotFoundError: If no cache file is found at the
                                  specified scope and name combination.
        :raises IOError: If the cache file exists but cannot be read.
        :raises ValueError: If the cached data cannot be properly deserialized.

        :returns: The deserialized data object loaded from the cache.
        :rtype: Any
        """

        # --- Construct path from scope ---
        # Similar to save method, we construct the folder path from the scope tuple
        folder_path = os.path.join(self.path, *scope)

        # --- Use load_from to auto-discover and load the data ---
        return self.load_from(folder_path, name)
