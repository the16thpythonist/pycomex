import os
import unittest
import subprocess
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
