import importlib.util
import inspect
import os
import subprocess
from typing import Tuple

import pytest

from pycomex.functional.experiment import (
    Experiment,
    find_experiment_in_module,
    run_experiment,
)
from pycomex.testing import ArgumentIsolation
from pycomex.util import PATH, dynamic_import

from .util import ASSETS_PATH


def run_example(file_name: str) -> Experiment:
    path = os.path.join(PATH, "examples", file_name)
    return run_experiment(path)


def test_example_experiment_inspect():

    experiment_path = os.path.join(ASSETS_PATH, "mock_functional_experiment.py")
    module = dynamic_import(experiment_path)

    doc_string = module.__doc__
    assert doc_string != ""

    experiment = find_experiment_in_module(module)
    description = experiment.metadata["description"]
    assert description != ""

    parameter_dict = experiment.metadata["parameters"]
    assert isinstance(parameter_dict, dict)
    assert len(parameter_dict) != 0
    assert "PARAMETER" in parameter_dict
    assert "type" in parameter_dict["PARAMETER"]
    assert "description" in parameter_dict["PARAMETER"]


@pytest.mark.slow
def test_example_basic():

    experiment = run_example("02_basic.py")

    assert experiment.error is None
    assert os.path.exists(experiment.path)


@pytest.mark.slow
def test_example_analysis():

    experiment = run_example("03_analysing.py")

    assert experiment.error is None
    assert os.path.exists(experiment.path)


@pytest.mark.slow
def test_example_inheritance():

    experiment = run_example("04_inheritance.py")

    assert experiment.error is None
    assert os.path.exists(experiment.path)


@pytest.mark.slow
def test_example_testing_mode():

    experiment = run_example("05_testing_mode.py")

    assert experiment.error is None
    assert os.path.exists(experiment.path)
