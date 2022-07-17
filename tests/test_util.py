import unittest

from pycomex.util import get_version
from pycomex.util import RecordCode


class TestFunctions(unittest.TestCase):

    def test_get_version(self):
        version = get_version()
        self.assertIsInstance(version, str)
        self.assertNotEqual(0, len(version))


class TestRecordCode(unittest.TestCase):

    def test_basically_works(self):

        variable = 10
        with RecordCode(stack_index=2, clip_indent=True) as code:
            self.assertIsInstance(code, RecordCode)
            self.assertIsInstance('hello world', str)

        variable = 12

        self.assertIsInstance(variable, int)
        self.assertIsInstance(code.code_string, str)
        self.assertIn('hello world', code.code_string)
        self.assertNotIn('variable', code.code_string)
