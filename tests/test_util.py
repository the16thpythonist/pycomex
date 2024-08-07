import os
import unittest
import typing as t

from inspect import getframeinfo, stack

from pycomex.util import get_version
from pycomex.util import get_comments_from_module
from pycomex.util import parse_parameter_info
from pycomex.util import type_string
from pycomex.util import trigger_notification

from .util import ASSETS_PATH


def test_type_string():
    string = type_string(t.Dict[str, int])
    print(string)
    assert string == 'Dict[str, int]'
    
    string = type_string(t.List[t.Dict[bool, t.Tuple[int, int]]])
    print(string)
    assert string == 'List[Dict[bool, Tuple[int, int]]]'


def test_parse_parameter_info_basically_works():
    """
    the "parse_parameter_info" is supposed to parse a specific format of additional parameter information 
    from a string and return all the information as a dictionary.
    """
    string = (
        'Some random comment\n'
        ':param PARAMETER:\n'
        '       the first line.\n'
        '       the second line.\n'
        'Some random string\n'
    )
    result = parse_parameter_info(string)
    assert isinstance(result, dict)
    assert 'PARAMETER' in result


def test_get_comments_from_module_basically_works():
    """
    The "get_comments_from_module" function should return a list with all the string comment lines 
    for the absolute path of a given python module
    """
    module_path = os.path.join(ASSETS_PATH, 'mock_functional_experiment.py')
    comments = get_comments_from_module(module_path)
    assert isinstance(comments, list)
    assert len(comments) != 0
    
    # Testing a single example comment from the list which we know is part of that module.
    assert '# testing comment - do not remove' in comments


def test_get_version():
    version_string = get_version()
    assert version_string != ''


def test_trigger_notification_basically_works():
    """
    The "trigger_notification" function should display a system notification with the given message
    """
    trigger_notification('Hello World, from unittesting!')
    assert True
