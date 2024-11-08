import os
import unittest
import typing as t
import sys

from inspect import getframeinfo, stack

from pycomex.util import get_version
from pycomex.util import get_comments_from_module
from pycomex.util import parse_parameter_info
from pycomex.util import type_string
from pycomex.util import trigger_notification
from pycomex.util import SetArguments
from pycomex.util import get_dependencies

from .util import ASSETS_PATH
from .util import ARTIFACTS_PATH


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
    
    
class TestSetArguments:
    """
    A suite of tests for the SetArguments context manager which is provides a temporary emulation 
    of a sys.argv list.
    """
    
    def test_sys_argv_structure(self):
        print(sys.argv)
        assert isinstance(sys.argv, list)

    def test_basically_works(self):
        """
        The class should act as a context manager that is able to change the sys.argv list only as 
        long as the context is active and reset it to the previous state afterwards.
        """
        original = sys.argv.copy()
        
        with SetArguments(['python', 'run.py', '--help']):
            # only in the context manager should the args become exactly that
            assert sys.argv == ['python', 'run.py', '--help']
            
        # outside it should not be that but instead should be its original value
        assert sys.argv != ['python', 'run.py', '--help']
        assert len(sys.argv) != 0
        assert sys.argv == original
        
    def test_works_with_exception(self):
        """
        It is important that the sys.argv list is reset to its original state even if an exception
        is raised within the context manager.
        """
        original = sys.argv.copy()
        
        try:
            with SetArguments(['python', 'run.py', '--help']):
                # only in the context manager should the args become exactly that
                assert sys.argv == ['python', 'run.py', '--help']
                
                # raise an exception
                raise ValueError('Some random exception')
        except ValueError:
            pass
        finally:
            assert sys.argv != ['python', 'run.py', '--help']
            assert sys.argv == original
            
            
def test_get_dependencies():
    """
    The "get_dependencies" function should return a dictionary with all the dependencies of the current 
    python runtime.
    """
    deps = get_dependencies()
    print(deps)
    
    assert isinstance(deps, dict)
    assert len(deps) != 0
    
    example_info = next(iter(deps.values()))
    assert isinstance(example_info, dict)
    assert 'version' in example_info
    assert 'name' in example_info
    assert 'path' in example_info