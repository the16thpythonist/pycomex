import os
import unittest
import subprocess
import importlib.util
from typing import Tuple

from pycomex.util import PATH
from pycomex.experiment import AbstractExperiment, Experiment
from pycomex.experiment import run_experiment
from pycomex.testing import ArgumentIsolation


def run_example(file_name: str) -> AbstractExperiment:
    path = os.path.join(PATH, "examples", file_name)
    return run_experiment(path)


def test_example_quickstart():
    # It is important that we can import the experiment module without actually triggering the
    # execution of the main experiment code. We can check this by checking if the experiment path exists
    # or not.
    # This is possible because the experiment path itself is determined within the constructor of
    # "Experiment" but the path itself is only created on __enter__!
    import pycomex.examples.quickstart as module

    assert isinstance(module.HELLO, str)
    assert isinstance(module.e, Experiment)

    # First of all, we should be able to execute the example without an exception
    with ArgumentIsolation():
        experiment = run_example("quickstart.py")
        assert experiment.error is None
        assert os.path.exists(experiment.path)


def test_example_basic():
    import pycomex.examples.basic as module

    assert isinstance(module.e, Experiment)

    with ArgumentIsolation():
        experiment = run_example("basic.py")
        assert experiment.error is None
        assert os.path.exists(experiment.path)


def test_example_analysis():
    import pycomex.examples.basic as module

    assert isinstance(module.e, Experiment)

    with ArgumentIsolation():
        experiment = run_example("analysis.py")
        assert experiment.error is None
        assert os.path.exists(experiment.path)


def test_example_inheritance():
    with ArgumentIsolation():
        experiment = run_example('inheritance.py')

        assert experiment.error is None
        assert os.path.exists(experiment.path)


def test_experiment_can_be_imported_from_snapshot():
    with ArgumentIsolation():
        experiment = run_example('quickstart.py')
        assert experiment.error is None
        assert os.path.exists(experiment.path)

    # Now after the experiment has successfully run, we navigate to the copy of the experiment script which
    # was created in the archive folder and try to import that. Importing that file should NOT execute the
    # script again but should still load the data into the experiment instance!
    snapshot_path = os.path.join(experiment.path, 'snapshot.py')
    assert os.path.exists(snapshot_path)

    spec = importlib.util.spec_from_file_location('snapshot', snapshot_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # It should be possible to import the 'e' object from the experiment snapshot. For this example it
    # is the main Experiment object. If this experiment is imported rather than being executed, it
    # should still populate the "data" property from the saved JSON file which is also located in the
    # records folder
    assert isinstance(module.e, Experiment)
    # TODO: check for this in a better way
