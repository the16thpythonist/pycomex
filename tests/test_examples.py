import os
import unittest
import subprocess
import importlib.util
from typing import Tuple

from pycomex.util import PATH
from pycomex.experiment import Experiment
from pycomex.experiment import run_experiment


class TestExamples(unittest.TestCase):

    def run_example(self, file_name: str) -> Tuple[str, subprocess.CompletedProcess]:
        path = os.path.join(PATH, "examples", file_name)
        return run_experiment(path)

    def test_example_quickstart(self):
        # It is important that we can import the experiment module without actually triggering the
        # execution of the main experiment code. We can check this by checking if the experiment path exists
        # or not.
        # This is possible because the experiment path itself is determined within the constructor of
        # "Experiment" but the path itself is only created on __enter__!
        import pycomex.examples.quickstart as experiment

        self.assertIsInstance(experiment.HELLO, str)
        self.assertIsInstance(experiment.e, Experiment)
        self.assertFalse(os.path.exists(experiment.e.path))

        # First of all, we should be able to execute the example without an exception
        path, p = self.run_example("quickstart.py")
        self.assertEqual(0, p.returncode)

    def test_example_basic(self):
        import pycomex.examples.basic as experiment

        self.assertIsInstance(experiment.e, Experiment)
        self.assertFalse(os.path.exists(experiment.e.path))

        path, p = self.run_example("basic.py")
        self.assertEqual(0, p.returncode)
        print(p.stdout.decode())

    def test_example_analysis(self):
        import pycomex.examples.basic as experiment

        self.assertIsInstance(experiment.e, Experiment)
        self.assertFalse(os.path.exists(experiment.e.path))

        path, p = self.run_example("analysis.py")
        self.assertEqual(0, p.returncode)

    def test_experiment_can_be_imported_from_snapshot(self):
        path, p = self.run_example('quickstart.py')
        self.assertTrue(os.path.exists(path))

        snapshot_path = os.path.join(path, 'snapshot.py')
        self.assertTrue(os.path.exists(snapshot_path))

        spec = importlib.util.spec_from_file_location('snapshot', snapshot_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # It should be possible to import the 'e' object from the experiment snapshot. For this example it
        # is the main Experiment object. If this experiment is imported rather than being executed, it
        # should still populate the "data" property from the saved JSON file which is also located in the
        # records folder
        self.assertIsInstance(module.e, Experiment)
