"""
This module tests the functionality of the class ``pycomex.experiment.SubExperiment`` which is supposed
to enable the hierarchical inheritance structures of experiment modules.
"""
import os
from pprint import pprint

from pycomex.experiment import AbstractExperiment
from pycomex.experiment import SubExperiment
from pycomex.experiment import ExperimentExchange
from pycomex.experiment import run_experiment
from pycomex.util import Skippable
from pycomex.testing import ExperimentIsolation

from .util import ASSETS_PATH


def test_construction_basically_works():
    """
    If a new instance of "SubExperiment" can be constructed without problems
    """
    experiment_path = os.path.join(ASSETS_PATH, 'test_experiment.py')
    sub_experiment = SubExperiment(
        base_path=os.getcwd(),
        namespace='test',
        experiment_path=experiment_path,
        glob={}
    )

    assert isinstance(sub_experiment, AbstractExperiment)
    assert isinstance(sub_experiment, SubExperiment)


def test_sub_experiment_of_test_experiment_basically_works():
    """
    If the execution of a "SubExperiment" based on a mock experiment module works properly in a simple
    example case.
    """
    experiment_path = os.path.join(ASSETS_PATH, 'mock_experiment.py')
    assert os.path.exists(experiment_path)

    # The mock experiment module which we invoke here as a parent experiment uses the NUM_VALUES parameter
    # to determine how many elements to generate, which is the easiest property to check for later on.
    num_values = 42
    glob_mod = {
        'NUM_VALUES': num_values
    }
    with ExperimentIsolation(glob_mod=glob_mod) as iso:
        # before the context manager, the archive base folder should be empty, since it is a completely
        # fresh temporary folder
        assert len(os.listdir(iso.path)) == 0

        se = SubExperiment(
            experiment_path=experiment_path,
            namespace='test',
            base_path=iso.path,
            glob=iso.glob
        )
        with Skippable(), se:
            pass

        # Also, the sub experiment instance should now contain the same data as the executed parent
        # experiment. which means that values should be in there!
        assert 'values' in se.data
        # after the experiment context, the parent experiment should have gotten executed which we should
        # be obvious by the fact that an archive folder was created.
        assert len(os.listdir(iso.path)) != 0
        # Also, since we override this parameter up top, we should see that this parameter change be
        # reflected in the behavior of the parent experiment!
        assert len(se['values']) == num_values


def test_sub_experiment_hooks_basically_working():
    experiment_path = os.path.join(ASSETS_PATH, 'mock_experiment.py')
    assert os.path.exists(experiment_path)

    with ExperimentIsolation() as iso:

        num_values = 42
        se = SubExperiment(
            experiment_path=experiment_path,
            namespace='test',
            base_path=iso.path,
            glob=iso.glob
        )
        with Skippable(), se:

            # We know that the mock experiment we use as the parent experiment here applies the hook
            # "after_values" which is called after the values are saved to the experiment. We use it
            # to completely overwrite the values.
            @se.hook('after_values')
            def replace_values(e, values):
                e.info(values[:10])
                e['values'] = [0] * num_values

        # Also, the sub experiment instance should now contain the same data as the executed parent
        # experiment. which means that values should be in there!
        assert 'values' in se.data

        # The hook which we have added above should replace this attribute such that this should be the
        # new list which was created in the hook.
        assert len(se['values']) == num_values


def test_mock_sub_experiment_works():
    """
    Executes the test experiment module "mock_sub_experiment.py" which is in itself a sub experiment of
    "mock_experiment.py".
    """
    experiment_path = os.path.join(ASSETS_PATH, 'mock_sub_experiment.py')
    assert os.path.exists(experiment_path)

    with ExperimentIsolation() as iso:
        experiment = run_experiment(experiment_path)

        assert isinstance(experiment, AbstractExperiment)
        assert os.path.exists(experiment.path)
        assert experiment.error is None

        assert experiment.parameters['NUM_VALUES'] == 200
        assert len(experiment['values']) == 200

        with open(experiment.log_path) as file:
            log_content = file.read()
            assert 'SUB IMPLEMENTATION' in log_content
            assert 'DEFAULT IMPLEMENTATION' not in log_content


def test_bug_sub_experiment_snapshot_not_executable_because_base_experiment_missing():
    """
    20.01.2023 - In this bug, a snapshot.py file created by a SubExperiment was not actually executable
    because it was missing the base experiment which was extending on, as that was not copied to the
    archive folder and thus could not be discovered.
    """
    experiment_path = os.path.join(ASSETS_PATH, 'mock_sub_experiment.py')
    assert os.path.exists(experiment_path)

    with ExperimentIsolation() as iso:
        experiment = run_experiment(experiment_path)

        # Here we make sure that the base experiment is actually part of the archive folder as well, which
        # is a prerequisite for the snapshot to be actually executable.
        base_experiment_path = os.path.join(experiment.path, experiment.experiment_name)
        assert os.path.exists(base_experiment_path)

        # Here we try to actually execute the snapshot
        snapshot_experiment = run_experiment(experiment.code_path)
        assert isinstance(snapshot_experiment, AbstractExperiment)
        assert os.path.exists(snapshot_experiment.path)
        assert snapshot_experiment.error is None


def test_stacking_sub_experiments_basically_works():
    """
    In this test we will try to call a SubExperiment of an experiment module, which itself is already a
    SubExperiment. This should work
    """
    experiment_path = os.path.join(ASSETS_PATH, 'mock_sub_experiment.py')
    assert os.path.exists(experiment_path)

    with ExperimentIsolation() as iso:
        se = SubExperiment(
            experiment_path=experiment_path,
            base_path=iso.path,
            glob=iso.glob,
            namespace='test'
        )
        pprint(iso.glob)
        with Skippable(), se:
            pass

        assert os.path.exists(se.path)
        assert se.error is None
        assert len(se.data) != 0
        # We check here if the second-level sub experiment instance still contains the valid values of
        # the original experiment
        assert 'NUM_VALUES' in se.parameters
        assert se.parameters['NUM_VALUES'] == 200
        assert len(se.data['values']) == 200

