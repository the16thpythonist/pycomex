import os
import unittest

from inspect import getframeinfo, stack

from pycomex.util import get_version
from pycomex.util import get_comments_from_module
from pycomex.util import parse_parameter_info

from .util import ASSETS_PATH


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


