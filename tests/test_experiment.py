import unittest
from pycomex.experiment import Experiment


class TestExperiment(unittest.TestCase):
    """
    This is a docstring
    """

    def test_construction_basically_works(self):
        experiment = Experiment(base_path='')
        self.assertIsInstance(experiment, Experiment)

