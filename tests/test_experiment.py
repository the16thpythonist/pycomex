import os
import time
import json
import unittest
from tempfile import TemporaryDirectory
from pycomex.experiment import Experiment


class TestExperiment(unittest.TestCase):
    """
    This is a docstring
    """

    def globals(self):
        glob = globals()
        glob["__name__"] = "__main__"
        return glob

    def test_how_does_string_split_behave(self):
        string = "hello/world"
        self.assertListEqual(["hello", "world"], string.split("/"))

        string = "hello"
        self.assertListEqual(["hello"], string.split("/"))

    def test_what_is_part_of_globals(self):
        glob = self.globals()
        self.assertIsInstance(glob, dict)
        self.assertEqual("__main__", glob["__name__"])

    def test_folder_creation_basically_works(self):
        with TemporaryDirectory() as base_path:
            with Experiment(base_path=base_path, namespace="test", glob=self.globals()) as e:
                e.prepare()

            # After the construction, the folder path should already exist
            self.assertIsInstance(e.path, str)
            self.assertTrue(os.path.exists(e.path))
            self.assertTrue(os.path.isdir(e.path))

    def test_folder_creation_nested_namespace_works(self):
        with TemporaryDirectory() as base_path:
            with Experiment(base_path=base_path, namespace="main/sub/test", glob=self.globals()) as e:
                e.prepare()

            # After the construction, the folder path should already exist
            self.assertIsInstance(e.path, str)
            self.assertTrue(os.path.exists(e.path))
            self.assertTrue(os.path.isdir(e.path))

    def test_logger_basically_works(self):
        with TemporaryDirectory() as base_path:
            with Experiment(base_path=base_path, namespace="test", glob=self.globals()) as e:
                e.prepare()
                log_message = "hello world!"
                e.info(log_message)

            # First we try again if the folder exists
            self.assertTrue(os.path.exists(e.path))

            # Now we should be able to find the previously logged message within the log file
            self.assertTrue(os.path.exists(e.log_path))
            with open(e.log_path, mode="r") as file:
                content = file.read()
                self.assertIn(log_message, content)

    def test_progress_tracking_basically_works(self):
        with TemporaryDirectory() as base_path:
            with Experiment(base_path=base_path, namespace="test", glob=self.globals()) as e:
                e.prepare()
                e.work = 5
                for i in range(e.work - 1):
                    time.sleep(0.1)
                    e.update()

                    self.assertNotEqual(0, e.work_tracker.remaining_time)

    def test_not_executing_code_when_not_main(self):
        with TemporaryDirectory() as base_path:
            flag = True
            # Here we purposefully change the value of the __name__ field to NOT be __main__. This should
            # prevent any of the code within the context manager from actually being executed!
            glob = globals()
            glob["__name__"] = "test"
            with Experiment(base_path=base_path, namespace="test", glob=glob) as e:
                e.prepare()
                flag = False

            # Thus the flag should still be True
            self.assertTrue(flag)

    def test_data_manipulation_basically_works(self):
        with TemporaryDirectory() as base_path:
            with Experiment(base_path=base_path, namespace="test", glob=self.globals()) as e:
                e.prepare()

                # Using dict style indexing to access the internal data dict should work:
                self.assertIsInstance(e["start_time"], float)

                # The setting operation should also work with a simple key
                e["new_value"] = 10
                self.assertEqual(10, e["new_value"])

                # More importantly, complex query-like keys for nested structures should also work. Even
                # if the nested structures do not yet exists, they should be automatically created
                e["metrics/exp/loss"] = 10
                self.assertEqual(10, e["metrics"]["exp"]["loss"])

                # This is how list logging would work:
                e["metrics/acc"] = []
                e["metrics/acc"].append(10)
                e["metrics/acc"].append(20)
                self.assertListEqual([10, 20], e["metrics/acc"])

            # Now we also check if the data file exists and if it also contains these values
            self.assertTrue(os.path.exists(e.data_path))
            with open(e.data_path, mode="r") as json_file:
                d = json.load(json_file)
                self.assertEqual(10, d["metrics"]["exp"]["loss"])

    def test_discover_parameters_basically_works(self):
        with TemporaryDirectory() as base_path:
            PARAMETER = 10
            glob = globals()
            glob["__name__"] = "__main__"
            with Experiment(base_path=base_path, namespace="test", glob=glob) as e:
                e.prepare()
                self.assertIn("PARAMETER", e.parameters)
                self.assertEqual(10, e.parameters["PARAMETER"])
                self.assertEqual(10, PARAMETER)

    def test_discover_description_works(self):
        with TemporaryDirectory() as base_path:
            glob = globals()
            glob["__name__"] = "__main__"
            glob["__doc__"] = "some description"
            with Experiment(base_path=base_path, namespace="test", glob=glob) as e:
                e.prepare()
                self.assertIn("description", e.data)
                self.assertEqual("some description", e["description"])
