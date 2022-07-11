"""
This is a module level docstring

Header
======

is this ok?

"""
import os
import sys
import time
import json
import shutil
import logging
import traceback
from datetime import datetime

from typing import List, Type, Optional

from pycomex.work import AbstractWorkTracker
from pycomex.work import NaiveWorkTracker


class NoExperimentExecution(Exception):
    def __call__(self):
        raise self


class Experiment:
    """

    **This has to be a heading**

    This is an example:

    .. code-block:: python
        :caption: A cool example

        import click
        print('hello world')

    :ivar str base_path: The absolute path to the base folder.

    :param str base_path: The thingy
            which is really important

    """

    def __init__(
        self,
        base_path: str,
        namespace: str,
        glob: dict,
        debug_mode: bool = False,
        work_tracker_class: Type[AbstractWorkTracker] = NaiveWorkTracker,
    ):
        self.base_path = base_path
        self.namespace = namespace
        self.glob = glob
        self.debug_mode = debug_mode
        self.work_tracker_class = work_tracker_class

        self.data = {}
        self.parameters = {}
        self.error: Optional[Exception] = None
        self.prevent_execution = False
        self.description: Optional[str] = None

        self.discover_parameters()
        self.path_list: List[str] = self.determine_path()
        self.path = os.path.join(self.base_path, *self.path_list)

        self.data_path = os.path.join(self.path, "experiment_data.json")
        self.error_path = os.path.join(self.path, "experiment_error.txt")
        self.log_path = os.path.join(self.path, "experiment_log.txt")
        self.logger: Optional[logging.Logger] = None

        self.work_tracker = self.work_tracker_class(0)

    def prepare_logger(self) -> None:
        self.logger = logging.Logger(self.namespace)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        handlers = [logging.FileHandler(self.log_path), logging.StreamHandler(sys.stdout)]
        for handler in handlers:
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def determine_path(self) -> List[str]:
        # ~ resolving the namespace
        # "self.namespace" is a string which uniquely characterizes this very experiment in the broader
        # scope of the base path. It may contain slashes to indicate a nested folder structure.
        names: List[str] = self.namespace.split("/")

        path_list = names
        namespace_path = os.path.join(self.base_path, *path_list)
        if self.debug_mode:
            path_list.append("debug")

        elif not os.path.exists(namespace_path):
            path_list.append("000")

        else:
            contents = os.listdir(namespace_path)
            indices = []
            for path in contents:
                try:
                    name = os.path.basename(path)
                    indices.append(int(name))
                except ValueError:
                    pass

            index = max(indices) + 1
            path_list.append(f"{index:03d}")

        return path_list

    def prepare_path(self) -> None:
        # ~ Make sure the path exists
        # If the nested structure provided by "self.namespace" does not exist, we create it here
        current_path = self.base_path
        for name in self.path_list:
            current_path = os.path.join(current_path, name)
            if not os.path.exists(current_path):
                os.mkdir(current_path)

        # In debug mode always the same special folder path is being used and we need to make sure to
        # get rid of any potential remaining previous instance of this folder to start with a clean slate.
        if self.debug_mode and os.path.exists(current_path):
            shutil.rmtree(current_path)
            os.mkdir(current_path)

    def discover_parameters(self) -> None:
        for key, value in self.glob.items():
            if key.isupper():
                self.parameters[key] = value

        # ~ Detecting special parameters
        if "__doc__" in self.glob and isinstance(self.glob["__doc__"], str):
            self.data["description"] = self.glob["__doc__"]

        if "DEBUG" in self.glob and isinstance(self.glob["DEBUG"], bool):
            self.debug_mode = self.glob["DEBUG"]

    def __getitem__(self, key):
        keys = key.split("/")
        current = self.data
        for key in keys:
            if key in current:
                current = current[key]
            else:
                raise KeyError(f'The namespace "{key}" does not exist within the experiment data storage')

        return current

    def __setitem__(self, key, value):
        keys = key.split("/")
        current = self.data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}

            current = current[key]

        current[keys[-1]] = value

    def prepare(self):
        if self.prevent_execution:
            raise NoExperimentExecution()

    def open(self, name: str, mode: str = "w"):
        file_path = os.path.join(self.path, name)
        return open(file_path, mode=mode)

    def commit_raw(self, name: str, content: str):
        with self.open(name) as file:
            file.write(content)

    def __enter__(self):
        if self.glob["__name__"] != "__main__":
            self.prevent_execution = True
            return self

        self.prepare_path()
        self.prepare_logger()

        self.work_tracker.start()

        self.data["start_time"] = time.time()
        self.data["path"] = self.path
        self.data["artifacts"] = {}

        # ~ logging the experiment start
        self.logger.info("=" * 80)
        self.logger.info("EXPERIMENT STARTED")
        self.logger.info(f"   namespace: {self.namespace}")
        self.logger.info(f'   start time: {datetime.fromtimestamp(self.data["start_time"])}')
        self.logger.info(f'   path: {self.data["path"]}')
        self.logger.info(f"   debug mode: {self.debug_mode}")
        self.logger.info("=" * 80)

        return self

    def __exit__(self, exc_type, exc_value, exc_tb):

        if isinstance(exc_value, NoExperimentExecution):
            return True

        self.data["end_time"] = time.time()
        self.data["elapsed_time"] = self.data["end_time"] - self.data["start_time"]

        if isinstance(exc_value, Exception):
            self.save_experiment_error(exc_value, exc_tb)
            self.error = exc_value

        # ~ Saving the metadata into file
        self.save_experiment_data()

        # ~ logging the experiment end
        self.logger.info("=" * 80)
        self.logger.info("EXPERIMENT ENDED")
        self.logger.info(f'   end time: {datetime.fromtimestamp(self.data["end_time"])}')
        self.logger.info(f'   elapsed time: {self.data["elapsed_time"]/3600:.2f}h')
        self.logger.info(f"   error: {self.error}")
        self.logger.info("=" * 80)

        return True

    def save_experiment_data(self):
        with open(self.data_path, mode="w") as json_file:
            json.dump(self.data, json_file)

    def save_experiment_error(self, exception_value, exception_traceback) -> None:
        with open(self.error_path, mode="w") as file:
            file.write(f"{exception_value.__class__.__name__.upper()}: {exception_value}")
            file.write("\n\n")
            tb = traceback.format_tb(exception_traceback)
            file.writelines(tb)

        self.info(f"saved experiment error to: {self.error_path}")
        self.info("\n".join(tb))

    @property
    def work(self) -> int:
        return self.work_tracker.total_work

    @work.setter
    def work(self, value: int) -> None:
        self.work_tracker.set_total_work(value)

    def info(self, message: str):
        self.logger.info(message)

    def update(self, n: int = 1, weight: float = 1.0, monitor_resources=True):
        self.work_tracker.update(n, weight)

        self.logger.info(
            f"({self.work_tracker.completed_work}/{self.work_tracker.total_work}) DONE - "
            f"ETA: {datetime.fromtimestamp(self.work_tracker.eta)} "
            f"(remaining time: {self.work_tracker.remaining_time/3600:.3f}h)"
        )

        if monitor_resources:
            pass
