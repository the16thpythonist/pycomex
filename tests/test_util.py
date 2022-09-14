import unittest

from inspect import getframeinfo, stack

from pycomex.util import get_version
from pycomex.util import RecordCode
from pycomex.util import Skippable


class TestFunctions(unittest.TestCase):

    def test_get_version(self):
        version = get_version()
        self.assertIsInstance(version, str)
        self.assertNotEqual(0, len(version))


class TestRecordCode(unittest.TestCase):

    # -- EXPLORATION --

    def test_frameinfo(self):

        # These two should show two different frame indices
        frame_info_1 = getframeinfo(stack()[0][0])
        frame_info_2 = getframeinfo(stack()[0][0])
        self.assertNotEqual(frame_info_1.lineno, frame_info_2.lineno)

    def test_removing_first_k_characters_string(self):
        string = '1234only this string should remain'
        expected = 'only this string should remain'
        clipped = string[4:]
        self.assertEqual(expected, clipped)

    # -- UNITTESTS --

    def test_basically_works(self):

        variable = 10
        with RecordCode(stack_index=2) as code:
            self.assertIsInstance(code, RecordCode)
            self.assertIsInstance('hello world', str)

        variable = 12

        self.assertIsInstance(variable, int)
        self.assertIsInstance(code.code_string, str)
        self.assertIn('hello world', code.code_string)
        self.assertNotIn('variable', code.code_string)

    def test_enter_and_exit_callback(self):

        rc = RecordCode(stack_index=2)
        setattr(rc, 'value', 10)

        def enter_cb(record_code, enter_index):
            self.assertEqual(record_code, rc)
            self.assertEqual(10, record_code.value)

        def exit_cb(record_code, exit_index):
            self.assertEqual(record_code, rc)
            self.assertEqual(20, record_code.value)

        rc.enter_callbacks.append(enter_cb)
        rc.exit_callbacks.append(exit_cb)

        with rc:
            rc.value = 20

    def test_skip_flag(self):
        """
        A special flag can be set for the context manager, making it skip the execution of the content.
        """
        value = 10

        with Skippable(), RecordCode(stack_index=2, skip=False):
            value = 20

        with Skippable(), (code := RecordCode(stack_index=2, skip=True)):
            value = 30
            # In the best case this will never be executed
            self.assertTrue(False)

        print(code)

        self.assertTrue(True)
        self.assertEqual(value, 20)
