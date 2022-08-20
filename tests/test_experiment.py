import os
import io
import sys
import time
import json
import tempfile
import unittest
import contextlib
import subprocess
from tempfile import TemporaryDirectory
from typing import Optional, List

from pycomex.experiment import Experiment
from pycomex.experiment import ExperimentArgParser
from pycomex.experiment import run_experiment
from pycomex.util import PATH

VARIABLE = 10


class ExperimentIsolation:

    def __init__(self, argv: List[str] = [], glob_mod: dict = {}):
        self.temporary_directory = TemporaryDirectory()
        self.path: Optional[str] = None
        self.glob: Optional[dict] = globals()

        self.modified_globals = {
            '__name__': '__main__',
            **glob_mod
        }
        self.original_globals = {
            **{k: globals()[k] for k in self.modified_globals.keys()},
            **{k: v for k, v in globals().items() if k.isupper()}
        }

        self.modified_argv = argv
        self.original_argv = sys.argv

    def __enter__(self):
        # ~ create temporary folder
        self.path = self.temporary_directory.__enter__()

        # ~ modify globals dictionary
        for key, value in self.modified_globals.items():
            globals()[key] = value

        # ~ modify command line arguments
        sys.argv = self.modified_argv

        return self

    def __exit__(self, *args):
        # ~ clean up temp folder
        self.temporary_directory.__exit__(*args)

        # ~ reset the globals to the original values
        for key, value in self.original_globals.items():
            globals()[key] = value

        # ~ reset the original argv
        sys.argv = self.original_argv


class TestExperimentIsolation(unittest.TestCase):

    def test_basically_works(self):
        # This is the original value defined above
        self.assertEqual(VARIABLE, 10)
        # argv should not be empty for pytest invocation
        self.assertNotEqual(0, len(sys.argv))

        with ExperimentIsolation(glob_mod={'VARIABLE': 20}) as iso:
            # We modify the globals here
            self.assertNotEqual(VARIABLE, 10)
            self.assertEqual(VARIABLE, 20)
            self.assertEqual(__name__, '__main__')

            # We also modified argv to be completely empty now
            self.assertEqual(0, len(sys.argv))

            # The temp folder has to exist
            self.assertTrue(os.path.exists(iso.path))
            self.assertTrue(os.path.isdir(iso.path))

        # Afterwards it should all have been reset to the original values though!
        self.assertEqual(VARIABLE, 10)
        self.assertNotEqual(0, len(sys.argv))


class TestExperimentArgParser(unittest.TestCase):

    def test_construction_basically_works(self):
        p = ExperimentArgParser(name="test/experiment", path="/tmp/test/experiment/000",
                                description="hello world!")
        self.assertIsInstance(p, ExperimentArgParser)

    def test_parsing_basically_works(self):
        p = ExperimentArgParser(name="test/experiment", path="/tmp/test/experiment/000",
                                description="hello world!")
        # Testing with empty arguments
        args = p.parse_args([])
        self.assertIn("description", args)
        self.assertEqual(None, args.description)

    def test_printing_help_works(self):
        """
        The "--help" option is a special case which will print the help string of the command and then
        actually terminate the execution without even touching the main experiment code
        """
        name = "test/experiment"
        p = ExperimentArgParser(name=name, path="/tmp/test/experiment/000", description="hello world!")
        with self.assertRaises(SystemExit):
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                # https://stackoverflow.com/questions/30510282/reopening-a-closed-stringio-object-in-python-3
                buf.close = lambda: None  # noqa
                p.parse_args(["--help"])

        self.assertIn(name, buf.getvalue())

    def test_printing_description_works(self):
        """
        "--description" works much like help. It is only supposed to print the experiment description string
        and then terminate the execution without actually executing the main experiment code.
        """
        description = "hello world!"
        p = ExperimentArgParser(name="test/experiment", path="/tmp/test/experiment/000",
                                description=description)
        with self.assertRaises(SystemExit):
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                # https://stackoverflow.com/questions/30510282/reopening-a-closed-stringio-object-in-python-3
                buf.close = lambda: None  # noqa
                p.parse_args(["--description"])

        self.assertIn(description, buf.getvalue())

    def test_out_path_works(self):
        p = ExperimentArgParser(name="test/experiment", path="/tmp/test/experiment/000",
                                description="hello world!")

        # If the "--out" option is not given, the field should still exist, but the value should be None
        args = p.parse_args([])
        self.assertIn('output_path', args)
        self.assertEqual(None, args.output_path)

        # If it is given the correct value has to be in the returned args
        out_path = 'tmp/.experiment_path'
        args = p.parse_args(['--out', out_path])
        self.assertEqual(out_path, args.output_path)

    def test_param_path_works(self):
        p = ExperimentArgParser(name="test/experiment", path="/tmp/test/experiment/000",
                                description="hello world!")

        # If the "--params" option is not given, the field should still exist, but the value should be None
        args = p.parse_args([])
        self.assertIn('parameters_path', args)
        self.assertEqual(None, args.parameters_path)

        # If the parameter is present but the file does not exist, that should cause an error
        param_path = '/tmp/experiment_parameters'
        with self.assertRaises(SystemExit):
            p.parse_args(['--parameters', param_path])

        # If the path exists everything should be fine
        with tempfile.TemporaryDirectory() as path:
            param_path = os.path.join(path, 'experiment_parameters.json')
            with open(param_path, mode='w') as json_file:
                json.dump({'hello': 'world'}, json_file)

            args = p.parse_args(['--parameters', param_path])
            self.assertIsInstance(args.parameters_path, str)
            self.assertEqual(param_path, args.parameters_path)


class TestExperiment(unittest.TestCase):
    """
    Mainly tests for the class :class:`pycomex.experiment.Experiment`
    """

    # -- misc tests

    def test_how_does_string_split_behave(self):
        string = "hello/world"
        self.assertListEqual(["hello", "world"], string.split("/"))

        string = "hello"
        self.assertListEqual(["hello"], string.split("/"))

    def test_dynamic_code_execution(self):
        variable = 10
        exec('variable = 20', globals(), locals())
        # Very interesting! exec() actually does not work the way I initially assumed. In this case I thought
        # the dynamic code would change the value of the previously defined local variable but it does not!
        self.assertNotEqual(20, variable)

    def test_dynamic_code_eval(self):
        d = eval('{"hello": "world"}')
        self.assertIsInstance(d, dict)
        self.assertEqual('world', d['hello'])

    def test_multiline_complex_code_eval(self):
        # Well, this also does not work! Either you cannot make import statements in an eval string or there
        # cannot be eval strings, either way i cant use that either!
        with self.assertRaises(SyntaxError):
            eval('import random\n'
                 'random.randint(0, 100)\n')

    def test_exec_workaround(self):
        # https://stackoverflow.com/questions/1463306/how-to-get-local-variables-updated-when-using-the-exec-call
        variable = None
        local_dict = {}
        exec('import random \n'
             'variable = random.randint(0, 10)',
             globals(), local_dict)

        # The actual variable in our scope does not change!
        self.assertEqual(None, variable)
        # But the variable values from the other scope get saved to the second dict we pass it!
        # This is actually even better for my use case :)
        self.assertIn('variable', local_dict)
        self.assertIsInstance(local_dict['variable'], int)

    # -- class related tests

    def test_folder_creation_basically_works(self):
        with ExperimentIsolation() as iso:
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()

            # After the construction, the folder path should already exist
            self.assertIsInstance(e.path, str)
            self.assertTrue(os.path.exists(e.path))
            self.assertTrue(os.path.isdir(e.path))

    def test_folder_creation_nested_namespace_works(self):
        with ExperimentIsolation() as iso:
            with Experiment(base_path=iso.path, namespace="main/sub/test", glob=globals()) as e:
                e.prepare()

            # After the construction, the folder path should already exist
            self.assertIsInstance(e.path, str)
            self.assertTrue(os.path.exists(e.path))
            self.assertTrue(os.path.isdir(e.path))

    def test_logger_basically_works(self):
        with ExperimentIsolation() as iso:
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                log_message = "hello world!"
                e.info(log_message)

            # First we try again if the folder exists
            self.assertTrue(os.path.exists(e.path))

            # Now we should be able to find the previously logged message within the log file
            self.assertTrue(os.path.exists(e.log_path))
            with open(e.log_path, mode="r") as file:
                content = file.read()
                self.assertIn(log_message, content)

    def test_progress_tracking_basically_works(self):
        with ExperimentIsolation() as iso:
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                e.work = 5
                for i in range(e.work - 1):
                    time.sleep(0.1)
                    e.update()

                    self.assertNotEqual(0, e.work_tracker.remaining_time)

    def test_not_executing_code_when_not_main(self):
        # Here we purposefully change the value of the __name__ field to NOT be __main__. This should
        # prevent any of the code within the context manager from actually being executed!
        with ExperimentIsolation(glob_mod={'__name__': 'test'}) as iso:
            flag = True
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                flag = False

            # Thus the flag should still be True
            self.assertTrue(flag)

    def test_data_manipulation_basically_works(self):
        with ExperimentIsolation() as iso:
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()

                # Using dict style indexing to access the internal data dict should work:
                self.assertIsInstance(e["start_time"], float)

                # The setting operation should also work with a simple key
                e["new_value"] = 10
                self.assertEqual(10, e["new_value"])

                # More importantly, complex query-like keys for nested structures should also work. Even
                # if the nested structures do not yet exists, they should be automatically created
                e["metrics/exp/loss"] = 10
                self.assertEqual(10, e["metrics"]["exp"]["loss"])

                # This is how list logging would work:
                e["metrics/acc"] = []
                e["metrics/acc"].append(10)
                e["metrics/acc"].append(20)
                self.assertListEqual([10, 20], e["metrics/acc"])

            # Now we also check if the data file exists and if it also contains these values
            self.assertTrue(os.path.exists(e.data_path))
            with open(e.data_path, mode="r") as json_file:
                d = json.load(json_file)
                self.assertEqual(10, d["metrics"]["exp"]["loss"])

            self.assertEqual(None, e.error)

    def test_discover_parameters_basically_works(self):
        with ExperimentIsolation() as iso:
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                # This is actually a global variable at the top of the file and thus should have been
                # automatically detected by the procedure
                self.assertIn("VARIABLE", e.parameters)
                self.assertEqual(10, e.parameters["VARIABLE"])
                # This variable does not exists and should therefore also not be part of the parameters
                self.assertNotIn('SOMETHING_WRONG', e.parameters)

            self.assertEqual(None, e.error)

    def test_discover_description_works(self):
        with ExperimentIsolation(glob_mod={'__doc__': 'some description'}) as iso:
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                self.assertIn("description", e.data)
                self.assertEqual("some description", e["description"])

            self.assertEqual(None, e.error)

    def test_load_parameters_json_works(self):

        with ExperimentIsolation() as iso:
            self.assertEqual(10, VARIABLE)
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                # At this point the variable should still be the same
                self.assertEqual(10, VARIABLE)
                # This function indirectly modifies the globals() dict and thus should also modify the
                # value of the variable.
                # The lower case value also in the parameter update should not be reflected in the
                # parameters since that key was not in there to begin with
                e.load_parameters_json(json.dumps({'VARIABLE': 20, 'variable': 10}))

                self.assertEqual(20, VARIABLE)
                self.assertNotIn('variable', e.parameters)

            self.assertEqual(None, e.error)

        self.assertEqual(10, VARIABLE)

    def test_load_parameters_py_works(self):

        with ExperimentIsolation() as iso:
            self.assertEqual(10, VARIABLE)
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                # At this point the variable should still be the same
                self.assertEqual(10, VARIABLE)
                # This function indirectly modifies the globals() dict and thus should also modify the
                # value of the variable.
                # The lower case value also in the parameter update should not be reflected in the
                # parameters since that key was not in there to begin with
                code_string = (
                    'import random\n\n'
                    'VARIABLE = [10 for i in range(5)]\n'
                    'variable = 10'
                )
                e.load_parameters_py(code_string)

                self.assertIsInstance(VARIABLE, list)
                self.assertNotIn('variable', e.parameters)

            self.assertEqual(None, e.error)


class TestRunExperiment(unittest.TestCase):
    """
    Tests for the function :meth:`pycomex.experiment.run_experiment`
    """

    def test_basically_works(self):
        # We will use one of the simple examples here to check if it works
        experiment_path = os.path.join(PATH, 'examples', 'quickstart.py')
        path, proc = run_experiment(experiment_path)
        self.assertIsInstance(path, str)
        self.assertEqual(0, proc.returncode)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.isdir(path))

        # One of the default artifacts is also supposed to be a "analysis.py" file, which contains
        # boilerplate code necessary to analyze the results of the experiment.
        analysis_path = os.path.join(path, 'analysis.py')
        self.assertTrue(os.path.exists(analysis_path))
        # It should also be possible to execute this python script as is without any errors
        command = f'{sys.executable} {analysis_path}'
        proc = subprocess.run(command, shell=True)
        self.assertEqual(0, proc.returncode)


class TestExperimentAnalysis(unittest.TestCase):
    """
    Tests related to the `analysis.py` file created by the execution of experiments
    """

    def test_analysis_file_is_created_by_default(self):
        """
        The `analysis.py` is default artifact for every experiment and should be created for every experiment
        """
        with ExperimentIsolation() as iso:
            self.assertEqual(10, VARIABLE)
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()

            self.assertEqual(None, e.error)
            # The file should exist
            analysis_path = os.path.join(e.path, 'analysis.py')
            self.assertTrue(os.path.exists(analysis_path))
            # And it should not be empty
            with open(analysis_path) as file:
                content = file.read()
                self.assertTrue(len(content) > 10)

    def test_default_analysis_file_is_executable_without_error(self):
        with ExperimentIsolation() as iso:
            self.assertEqual(10, VARIABLE)
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()

            analysis_path = os.path.join(e.path, 'analysis.py')
            command = f'{sys.executable} {analysis_path}'
            proc = subprocess.run(command, shell=True)
            self.assertEqual(0, proc.returncode)

    def test_custom_code_is_added_to_analysis_file(self):
        with ExperimentIsolation() as iso:
            self.assertEqual(10, VARIABLE)
            with Experiment(base_path=iso.path, namespace="test", glob=globals()) as e:
                e.prepare()
                e['value'] = 100

                with e.analysis:
                    # All of this code should be copied to the analysis file
                    new_value = 200
                    print(new_value)
                    final_value = new_value ** 0.5
                    print(final_value)

            # The custom code should be inside the generated analysis file
            analysis_path = os.path.join(e.path, 'analysis.py')
            with open(analysis_path) as file:
                content = file.read()
                print(content)
                self.assertIn('new_value', content)
                self.assertIn('final_value', content)

            # THe analysis file should still work.
            # In fact, we know that that file should print "200" to stdout, which we will also check
            command = f'{sys.executable} {analysis_path}'
            proc = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
            self.assertEqual(0, proc.returncode)
            self.assertIn('200\n', proc.stdout.decode())

    def test_bug_it_is_not_possible_to_invoke_the_logger_in_analysis_file(self):
        """
        **20.08.2022** This bug causes an exception when trying to execute an `analysis.py` script which
        for example contains a line `e.info("...")`. The logger cannot be invoked for the analysis version
        of an experiment...
        """
        # We need to do a bit of a workaround here. The thing is we can fundamentally only invoke *any*
        # function of the experiment object "e" from the analysis file, if the original experiment is it's
        # own file, or rather if the experiment object/context is defined at the top level. This is
        # obviously not given for such a unittest module. Thus we create some sample python code string here
        # write that into a file, invoke that file as an experiment and then it should work
        code_string = (
            'import os\n'
            'import pathlib\n'
            'from pycomex.experiment import Experiment\n'
            'PATH = pathlib.Path(__file__).parent.absolute()\n'
            'with Experiment(base_path=PATH, namespace="test_bug", glob=globals()) as e:\n'
            '   e.prepare()\n'
            '   e["value"] = 10\n'
            '   with e.analysis:\n'
            '       e.info("starting analysis")\n'
            '       e.info("experiment value: " + str(e["value"]))\n'
        )
        with tempfile.TemporaryDirectory() as path:
            code_path = os.path.join(path, 'main.py')
            with open(code_path, mode='w') as file:
                file.write(code_string)

            archive_path, proc = run_experiment(code_path)
            self.assertEqual(0, proc.returncode)

            analysis_path = os.path.join(archive_path, 'analysis.py')
            command = f'{sys.executable} {analysis_path}'
            proc = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
            # With the bug, this fails
            self.assertEqual(0, proc.returncode)
            self.assertIn('experiment value: 10', proc.stdout.decode())
