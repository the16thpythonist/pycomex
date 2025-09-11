"""
Testing utilities for PyComex experiments.

This module provides mock implementations and testing utilities for PyComex experiments.
"""

import json
import os
import shutil
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Dict, List, Optional, Union
from unittest.mock import Mock


class MockExperiment:
    """
    Mock implementation of the Experiment class for testing purposes.

    This class provides simplified implementations of Experiment methods that avoid
    actual file I/O operations, making it suitable for unit testing.
    """

    def __init__(
        self,
        base_path: str = "/tmp/mock_experiment",
        namespace: str = "mock",
        glob: dict | None = None,
        debug: bool = True,
        **kwargs,
    ):
        """
        Initialize a MockExperiment instance.

        :param base_path: Mock base path for the experiment
        :param namespace: Mock namespace for the experiment
        :param glob: Mock global dictionary (defaults to empty dict if None)
        :param debug: Enable debug mode (always True for mock)
        :param kwargs: Additional keyword arguments (ignored)
        """
        self.base_path = base_path
        self.namespace = namespace
        self.glob = glob or {}
        self.debug = debug

        # Mock experiment state
        self.path = None
        self.name = None
        self.func = None
        self.parameters = {}
        self.data = {}
        self.metadata = {
            "status": None,
            "start_time": None,
            "end_time": None,
            "duration": None,
            "has_error": False,
            "base_path": str(base_path),
            "namespace": str(namespace),
            "description": "",
            "short_description": "",
            "parameters": {},
            "hooks": {},
            "__track__": [],
        }

        self.error = None
        self.tb = None
        self.is_running = False
        self.is_testing = False
        self.dependencies = []
        self.analyses = []
        self.hook_map = defaultdict(list)

        # Mock config and logger
        self.config = Mock()
        self.config.pm = Mock()
        self.config.pm.apply_hook = Mock()

        # Simple logger that just prints
        self.logger = Mock()

        # Mock cache
        self.cache_path = os.path.join(base_path, ".cache")
        self.cache = Mock()

    def log(self, message: str, **kwargs):
        """Mock log method - just prints the message."""
        print(f"[MOCK LOG] {message}")

    def log_lines(self, lines: list[str]):
        """Mock log_lines method - prints each line."""
        for line in lines:
            self.log(line)

    def log_parameters(self):
        """Mock log_parameters method - prints parameters."""
        self.log(f"Parameters: {self.parameters}")

    def hook(self, name: str, replace: bool = True, default: bool = True):
        """Mock hook decorator."""

        def decorator(func, *args, **kwargs):
            if replace:
                self.hook_map[name] = [func]
            else:
                self.hook_map[name] = self.hook_map[name] + [func]

        return decorator

    def apply_hook(self, name: str, default: Any | None = None, **kwargs):
        """Mock apply_hook method."""
        result = default
        if name in self.hook_map:
            for func in self.hook_map[name]:
                result = func(self, **kwargs)
        return result

    def testing(self, func: Callable) -> Callable:
        """Mock testing decorator."""
        self.hook_map["__TESTING__"] = func
        return func

    def analysis(self, func, *args, **kwargs):
        """Mock analysis method."""
        self.analyses.append(func)

    def execute_analyses(self):
        """Mock execute_analyses method."""
        for func in self.analyses:
            func(self)

    def initialize(self):
        """Mock initialize method - sets up basic state."""
        self.path = os.path.join(self.base_path, self.namespace, "mock_run")
        self.metadata["status"] = "running"
        self.metadata["start_time"] = time.time()
        self.log("Mock experiment initialized")

    def finalize(self):
        """Mock finalize method - updates metadata."""
        self.metadata["end_time"] = time.time()
        self.metadata["duration"] = (
            self.metadata["end_time"] - self.metadata["start_time"]
        )
        self.metadata["status"] = "done"
        self.log("Mock experiment finalized")

    def execute(self):
        """Mock execute method - runs the experiment function."""
        self.initialize()

        try:
            self.is_running = True
            self.apply_hook("before_run")

            if self.func:
                self.func(self)

            self.apply_hook("after_run")

        except Exception as error:
            self.error = error
            self.log(f"Mock experiment error: {error}")

        self.finalize()

        if self.error:
            raise self.error

    def run(self):
        """Mock run method."""
        self.execute()
        self.execute_analyses()

    def run_if_main(self):
        """Mock run_if_main method - always runs since it's a mock."""
        self.run()

    def __call__(self, func, *args, **kwargs):
        """Mock callable behavior."""
        self.func = func
        return self

    def is_main(self) -> bool:
        """Mock is_main method - returns True for testing."""
        return True

    def set_main(self):
        """Mock set_main method."""
        pass

    # Data storage methods
    def __getitem__(self, key):
        """Mock getitem for nested data access."""
        keys = key.split("/")
        current = self.data
        for k in keys:
            if k in current:
                current = current[k]
            else:
                raise KeyError(
                    f'The namespace "{k}" does not exist in mock data storage'
                )
        return current

    def __setitem__(self, key, value):
        """Mock setitem for nested data storage."""
        if not isinstance(key, str):
            raise ValueError("Mock experiment storage requires string keys")

        keys = key.split("/")
        current = self.data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def __getattr__(self, item: str) -> Any:
        """Mock getattr for parameter access."""
        if item.isupper():
            if item not in self.parameters:
                raise KeyError(f'Mock experiment has no parameter "{item}"')
            return self.parameters[item]
        else:
            raise AttributeError(f'Mock experiment has no attribute "{item}"')

    def __setattr__(self, key: str, value: Any) -> None:
        """Mock setattr for parameter setting."""
        if key.isupper():
            self.parameters[key] = value
            if hasattr(self, "glob"):
                self.glob[key] = value
        else:
            super().__setattr__(key, value)

    # File operations (mocked)
    def open(self, file_name: str, *args, **kwargs):
        """Mock file open - returns a temporary file."""
        return tempfile.NamedTemporaryFile(mode="w+", delete=False)

    def commit_fig(self, file_name: str, fig: Any):
        """Mock commit_fig - just logs the action."""
        self.log(f"Mock: Would save figure to {file_name}")

    def commit_json(self, file_name: str, data: dict | list, encoder_cls=None):
        """Mock commit_json - just logs the action."""
        self.log(f"Mock: Would save JSON data to {file_name}: {data}")

    def commit_raw(self, file_name: str, content: str):
        """Mock commit_raw - just logs the action."""
        self.log(f"Mock: Would save raw content to {file_name}: {content[:50]}...")

    def track(self, name: str, value: float | Any):
        """Mock track method - stores values in memory."""
        if name not in self.data:
            self[name] = []
            self.metadata["__track__"].append(name)

        self[name].append(value)
        self.log(f"Mock: Tracking {name} = {value}")

    def track_many(self, data: dict):
        """Mock track_many method."""
        for key, value in data.items():
            self.track(key, value)

    # Properties (mocked)
    @property
    def metadata_path(self) -> str:
        """Mock metadata path."""
        return "/tmp/mock_metadata.json"

    @property
    def data_path(self) -> str:
        """Mock data path."""
        return "/tmp/mock_data.json"

    @property
    def code_path(self) -> str:
        """Mock code path."""
        return "/tmp/mock_code.py"

    @property
    def log_path(self) -> str:
        """Mock log path."""
        return "/tmp/mock_log.txt"

    @property
    def analysis_path(self) -> str:
        """Mock analysis path."""
        return "/tmp/mock_analysis.py"

    # Utility methods
    def update_parameters(self):
        """Mock parameter update method."""
        for name, value in self.glob.items():
            if name.isupper():
                self.parameters[name] = value

    def save_metadata(self):
        """Mock save metadata - just logs."""
        self.log("Mock: Would save metadata")

    def save_data(self):
        """Mock save data - just logs."""
        self.log("Mock: Would save data")

    def save_code(self):
        """Mock save code - just logs."""
        self.log("Mock: Would save code")

    def save_dependencies(self):
        """Mock save dependencies - just logs."""
        self.log("Mock: Would save dependencies")

    def save_analysis(self):
        """Mock save analysis - just logs."""
        self.log("Mock: Would save analysis")
