"""
This module tests the functionality of the class ``pycomex.experiment.AbstractExperiment``, which is the
abstract base class implementation of an experiment, which implements a lot of the basic logic which applies
to every kind of specific experiment implementation.
"""
import os

from pycomex.experiment import AbstractExperiment
from pycomex.testing import ExperimentIsolation
from pycomex.util import Skippable


def test_construction_basically_works():
    with ExperimentIsolation() as iso:
        e = AbstractExperiment(base_path=iso.path, namespace='test', glob=iso.glob)
        assert isinstance(e, AbstractExperiment)


def test_set_get_item_basically_works():
    with ExperimentIsolation() as iso:
        # ~ basic test with simple values
        e = AbstractExperiment(base_path=iso.path, namespace='test', glob=iso.glob)
        e['data1'] = 'value'
        assert e.data['data1'] == 'value'

        e['data2/nested'] = 'value'
        assert isinstance(e.data['data2'], dict)
        assert e.data['data2']['nested'] == 'value'
        assert e['data2/nested'] == 'value'


def test_update_internal_state_with_dict_basically_works():
    """
    The "update" method is supposed to accept a dict argument which defines how the internal state of
    an existing experiment instance is supposed to be updated.
    """
    with ExperimentIsolation() as iso:
        # ~ very basic test with blank experiment
        e = AbstractExperiment(base_path=iso.path, namespace='test', glob=iso.glob)
        # When it was just created, mostly all the internal properties should be empty or None which we
        # will make sure here
        assert e.data == {}
        assert e.base_path == iso.path
        assert e.glob['__name__'] == '__main__'  # This will always be true w ExperimentIsolation

        # After the update, the internal fields should have the properties which were passed into the update
        # function.
        e.update({
            'base_path': os.getcwd(),
            'namespace': 'updated',
            'data': {'key': 'value'},
            'glob': {'__name__': 'updated'},
        })
        assert e.base_path == os.getcwd()
        assert e.namespace == 'updated'
        assert e.data != {}
        assert e.data['key'] == 'value'
        assert e.glob['__name__'] == 'updated'
        assert len(e.glob) != 1  # to make sure that glob is updated and not replaced...


def test_to_update_dict_basically_works():
    """
    "to_update_dict" is a method which is supposed to convert an existing experiment instance into a
    dictionary, which contains the most important information about the experiment and which is supposed
    to be usable as the argument to the "update" method of another experiment instance.
    """
    with ExperimentIsolation() as iso:
        # ~ very basic test with blank experiment
        e = AbstractExperiment(base_path=iso.path, namespace='test', glob=iso.glob)
        other = e.to_update_dict()
        assert isinstance(other, dict)
        assert len(other) != 0

        key_type_map = {
            'data': dict, 'meta': dict, 'parameters': dict, 'namespace': str, 'base_path': str, 'glob': dict,
        }
        for key, typ in key_type_map.items():
            assert key in other
            assert isinstance(other[key], typ)


def test_update_internal_state_using_other_experiment_instance():
    """
    The "update" method primarily supposed to work with dictionaries that define new values for the internal
    experiment state, but it should also be possible to pass a different experiment instance which will
    cause the first instance to update the internal parameters with the values from the second instance.
    """
    with ExperimentIsolation() as iso:
        e = AbstractExperiment(base_path=iso.path, namespace='test', glob=iso.glob)
        assert e.data == {}
        assert e.base_path == iso.path
        assert e.glob['__name__'] == '__main__'  # This will always be true w ExperimentIsolation

        e_other = AbstractExperiment(base_path=os.getcwd(), namespace='other', glob=iso.glob)
        e_other['key'] = 'value'
        assert e_other.data == {'key': 'value'}
        assert e_other.base_path == os.getcwd()
        assert e_other.namespace == 'other'

        # Now we perform update and see if it worked with a few sporadic checks
        e.update(e_other)
        assert 'key' in e.data
        assert e.data['key'] == 'value'
        assert e.namespace == 'other'


def test_hook_system_basically_works():
    """
    The hook system consists of the two methods "hook" and "apply_hook". A callback function can be
    registered to an experiment using the "hook" decorator prior to the execution of the main experiment
    context. Inside the context the various callback functions registered to a unique hook name can be
    executed using "apply_hook"
    """
    with ExperimentIsolation() as iso:
        # ~ simple case: single hook without return
        se = AbstractExperiment(base_path=iso.path, namespace='test', glob=iso.glob)

        @se.hook('my_hook')
        def func(e):
            e['key'] = 'value'

        with Skippable(), se:
            se.apply_hook('my_hook')

        # Since we have registered the hook prior, the code inside it should have been executed upon calling
        # "apply_hook", which means that the value should exist in the experiment instance now
        assert se['key'] == 'value'
