import importlib.util
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

from pycomex.util import EXAMPLES_PATH
from pycomex.util import Skippable
from pycomex.experiment import run_example
from pycomex.experiment import Experiment
from pycomex.experiment import ArchivedExperiment
from pycomex.experiment import ExperimentArgParser
from pycomex.experiment import run_experiment
from pycomex.experiment import ExperimentRegistry
from pycomex.experiment import NamespaceFolder

from .util import TEMPLATE_ENV, write_template


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

    # -- EXPLORATION --

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

    # -- UNITTESTS --

    def test_folder_creation_basically_works(self):
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
                pass

            # After the construction, the folder path should already exist
            self.assertIsInstance(e.path, str)
            self.assertTrue(os.path.exists(e.path))
            self.assertTrue(os.path.isdir(e.path))

    def test_folder_creation_nested_namespace_works(self):
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="main/sub/test",
                                               glob=globals())):
                pass

            # After the construction, the folder path should already exist
            self.assertIsInstance(e.path, str)
            self.assertTrue(os.path.exists(e.path))
            self.assertTrue(os.path.isdir(e.path))

    def test_logger_basically_works(self):
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
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
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
                e.work = 5
                for i in range(e.work - 1):
                    time.sleep(0.1)
                    e.update()

                    self.assertNotEqual(0, e.work_tracker.remaining_time)

    def test_not_executing_code_when_not_main(self):
        # Here we purposefully change the value of the __name__ field to NOT be __main__. This should
        # prevent any of the code within the context manager from actually being executed!
        with Skippable(), ExperimentIsolation(glob_mod={'__name__': 'test'}) as iso:
            flag = True
            with Experiment(base_path=iso.path, namespace="test", glob=globals()):
                flag = False

            # Thus the flag should still be True
            self.assertTrue(flag)

    def test_data_manipulation_basically_works(self):
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):

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
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
                # This is actually a global variable at the top of the file and thus should have been
                # automatically detected by the procedure
                self.assertIn("VARIABLE", e.parameters)
                self.assertEqual(10, e.parameters["VARIABLE"])
                # This variable does not exists and should therefore also not be part of the parameters
                self.assertNotIn('SOMETHING_WRONG', e.parameters)

            self.assertEqual(None, e.error)

    def test_discover_description_works(self):
        with ExperimentIsolation(glob_mod={'__doc__': 'some description'}) as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
                self.assertIn("description", e.data)
                self.assertEqual("some description", e["description"])

            self.assertEqual(None, e.error)

    def test_load_parameters_json_works(self):

        with ExperimentIsolation() as iso:
            self.assertEqual(10, VARIABLE)
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
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
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
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

    def test_start_and_end_time_pretty_properties(self):
        """
        Whether the :meth:``pycomex.Experiment.start_time_pretty`` and
        :meth:``pycomex.Experiment.end_time_pretty`` properties for pretty datetime formatting work.
        """
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):

                self.assertIsInstance(e.start_time_pretty, str)
                self.assertNotEqual(0, len(e.start_time_pretty))

                # But during the execution of the experiment we expect "end_time_pretty" to fail because
                # it does not exist yet
                with self.assertRaises(AttributeError):
                    print(e.end_time_pretty)

            # But after the experiment is done, this should work
            self.assertIsInstance(e.end_time_pretty, str)
            self.assertNotEqual(0, len(e.end_time_pretty))

    def test_update_monitoring(self):
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):

                # At the beginning the monitoring dict should be empty
                self.assertEqual(0, len(e.data['monitoring']))

                # After the update process it should not be
                data = e.update_monitoring()
                self.assertIsInstance(data, dict)
                self.assertNotEqual(0, len(data))
                self.assertEqual(1, len(e.data['monitoring']))
                first_ts = data['ts']

                # Now if we do it again, another one should be added
                e.update_monitoring()
                self.assertEqual(2, len(e.data['monitoring']))
                # It should be possible to get the most recent entry like this
                most_recent = list(e.data['monitoring'].values())[-1]
                self.assertTrue(most_recent['ts'] > first_ts)

    def test_logging_experiment_status(self):
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
                e.status(log=True)

            # Now the printed status should appear in the log file
            log_path = os.path.join(e.path, 'experiment_log.txt')
            with open(log_path) as file:
                content = file.read()
                self.assertIn('EXPERIMENT STATUS', content)

            # Also the experiment should have more than 0 monitoring entries
            self.assertNotEqual(0, len(e.data['monitoring']))

    # -- BUG TESTS --

    def test_bug_experiment_meta_file_does_not_have_monitoring_info_if_not_explicitly_called(self):
        """
        **21.08.2022** This bug causes an error when trying to access the "monitoring" field of the
        experiment metadata json file if the experiment did not explicitly call "status" or
        "update_monitoring" in the code at least once
        """
        with ExperimentIsolation() as iso:
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
                pass

            meta_path = os.path.join(e.path, 'experiment_meta.json')
            with open(meta_path) as file:
                data = json.loads(file.read())
                # This fails with the bug
                self.assertIn('monitoring', data)
                self.assertIsInstance(data['monitoring'], dict)
                self.assertNotEqual(0, len(data['monitoring']))

    def test_bug_experiment_analysis_from_experiment_file_is_not_copied(self):
        """
        **12.09.2022** This bug occurred when moving from Python 3.8 to 3.10. I have no idea why though. It
        appears for every experiment file which has a "with experiment.analysis" block. It does get executed
        but then it is not able to copy it to "analysis.py" supposedly because "detect_indent" fails.
        """
        path, p = run_example("analysis.py")
        self.assertEqual(0, p.returncode)

        analysis_path = os.path.join(path, 'analysis.py')
        self.assertTrue(os.path.exists(analysis_path))
        with open(analysis_path) as file:
            content = file.read()
            self.assertIn('e.commit_json', content)

    def test_experiment_analysis_gets_executed_when_experiment_is_imported(self):
        """
        **14.09.2022** By fixing the previous bug, I introduced a new one: The way how the experiment
        analysis functionality is written now, it gets executed in the main experiment file, when the
        experiment is just being imported by another file.
        """
        # First we execute this and get the modification date of one of the ANALYSIS artifacts. Then we try
        # to merely import the SNAPSHOT file of that experiment and then we can compare the modification
        # times of the analsyis artifacts, which should not have changed
        path, p = run_example("analysis.py")
        self.assertEqual(0, p.returncode)

        artifact_path = os.path.join(path, 'analysis_results.json')
        mod = os.path.getmtime(artifact_path)

        snapshot_path = os.path.join(path, 'snapshot.py')
        spec = importlib.util.spec_from_file_location('snapshot', snapshot_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        mod_new = os.path.getmtime(artifact_path)
        self.assertEqual(mod, mod_new)


class TestRunExperiment(unittest.TestCase):
    """
    Tests for the function :meth:`pycomex.experiment.run_experiment`
    """

    def test_basically_works(self):
        # We will use one of the simple examples here to check if it works
        experiment_path = os.path.join(EXAMPLES_PATH, 'quickstart.py')
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
            with Skippable(), (e := Experiment(base_path=iso.path, namespace="test", glob=globals())):
                pass

            self.assertEqual(None, e.error)
            # The file should exist
            analysis_path = os.path.join(e.path, 'analysis.py')
            self.assertTrue(os.path.exists(analysis_path))
            # And it should not be empty
            with open(analysis_path) as file:
                content = file.read()
                self.assertTrue(len(content) > 10)

    def test_default_analysis_file_is_executable_without_error(self):
        template = TEMPLATE_ENV.get_template('test_experiment_analysis.py.j2')
        code_string = template.render(analysis_code=['pass'])
        with tempfile.TemporaryDirectory() as path:
            code_path = os.path.join(path, 'main.py')
            with open(code_path, mode='w') as file:
                file.write(code_string)

            archive_path, proc = run_experiment(code_path)
            self.assertEqual(0, proc.returncode)

    def test_custom_code_is_added_to_analysis_file(self):
        template = TEMPLATE_ENV.get_template('test_experiment_analysis.py.j2')
        code_string = template.render(analysis_code=[
            'new_value = 200',
            'print(new_value)',
            'final_value = new_value ** 0.5'
        ])
        print(code_string)
        with tempfile.TemporaryDirectory() as path:
            code_path = os.path.join(path, 'main.py')
            with open(code_path, mode='w') as file:
                file.write(code_string)

            archive_path, proc = run_experiment(code_path)
            self.assertEqual(0, proc.returncode)

            # The custom code should be inside the generated analysis file
            analysis_path = os.path.join(archive_path, 'analysis.py')
            with open(analysis_path) as file:
                content = file.read()
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
            'from pycomex.util import Skippable\n'
            'PATH = pathlib.Path(__file__).parent.absolute()\n'
            'with Skippable(),'
            '(e := Experiment(base_path=PATH, namespace="test_bug", glob=globals())):\n'
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


class TestArchivedExperiment(unittest.TestCase):
    """
    Testing :class:`pycomex.experiment.ArchivedExperiment`, which can be used to load an already finished
    experiment to access the persistent data records of that experiment.
    """

    def test_basically_works(self):
        code_string = (
            'import os\n'
            'import pathlib\n'
            'from pycomex.experiment import Experiment\n'
            'from pycomex.util import Skippable\n'
            'PATH = pathlib.Path(__file__).parent.absolute()\n'
            'DEBUG = True\n'
            'with Skippable(), (e := Experiment(base_path=PATH, namespace="test_bug", glob=globals())):\n'
            '   e["value"] = 10\n'
            '   e["foo"] = "bar"\n'
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

            with ArchivedExperiment(archive_path) as e:
                # this context manager should actually return the very Experiment object instance from which
                # was dynamically imported from that experiment's snapshot module
                self.assertIsInstance(e, Experiment)
                # Trough this loaded object it should be possible to access the persisted values which were
                # added to the experiment object during the execution of the experiment
                self.assertEqual(10, e['value'])
                self.assertEqual('bar', e['foo'])
                # Also it should be possible to access the experiment parameters
                self.assertTrue(e.parameters['DEBUG'])


class TestExperimentRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        To test :class:`pycomex.experiment.ExperimentRegistry` we actually need a registry in the first
        place. That is a folder which contains multiple different archived experiments. Setting up such a
        folder structure would be too much effort for every single unittest individually, which is why
        we simply set it up once for the entire class and all of the unittests can work on this structure
        then
        """
        cls.temp_directory = TemporaryDirectory()
        cls.path = cls.temp_directory.__enter__()

        # This template is very basic Experiment python code file, where we can put in a custom namespace.
        # We will need that here since we want multiple different experiments in our experiment registry.
        template = TEMPLATE_ENV.get_template('test_experiment_registry.py.j2')

        experiment_1_path = os.path.join(cls.path, 'experiment1.py')
        write_template(experiment_1_path, template, {'namespace': 'experiment1'})
        archive_path, proc = run_experiment(experiment_1_path)

        # Experiment 2 we will run multiple times so that there are multiple archives
        experiment_2_path = os.path.join(cls.path, 'experiment2.py')
        write_template(experiment_2_path, template, {'namespace': 'experiment2'})
        run_experiment(experiment_2_path)
        run_experiment(experiment_2_path)

        # Experiment 3 will have a nested namespace
        experiment_3_path = os.path.join(cls.path, 'experiment3.py')
        write_template(experiment_3_path, template, {'namespace': 'nested/experiment3'})
        run_experiment(experiment_3_path)

        # Afterwards we need to get rid of all the original experiment files since we only want to have the
        # archives in this main folder
        os.remove(experiment_1_path)
        os.remove(experiment_2_path)
        os.remove(experiment_3_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_directory.__exit__(None, None, None)

    def test_temp_directory_exists(self):
        self.assertTrue(os.path.exists(self.path))
        self.assertTrue(os.path.isdir(self.path))

        # Now we also want to check if there are in fact only the archive folders in this main folder
        # now, like we set up in setUpClass
        contents = os.listdir(self.path)
        self.assertNotEqual(0, len(contents))
        self.assertTrue(all([os.path.isdir(os.path.join(self.path, name)) for name in contents]))

    # -- EXPLORATION --

    def test_set_differences(self):
        s1 = {1, 2, 3}
        s2 = {1, 2, 4}
        self.assertEqual({3}, s1.difference(s2))
        self.assertEqual({4}, s2.difference(s1))

    # -- UNITTESTS --

    def test_basically_works(self):
        reg = ExperimentRegistry(self.path)
        reg.load()

        # Looking into "setUpClass" we created 3 separate namespaces which should be discovered by the
        # registry
        self.assertEqual(3, len(reg.namespaces))

        self.assertTrue('experiment1' in reg)
        self.assertTrue('experiment2' in reg)
        self.assertTrue('nested/experiment3' in reg)

        # Testing the getting the namespace folders here
        ex1_namespace = reg.namespaces['experiment1']
        self.assertIsInstance(ex1_namespace, NamespaceFolder)

    def test_namespace_folder_loading_experiments_properly(self):
        reg = ExperimentRegistry(self.path)
        reg.load()

        # First experiment should only have a single archived run, while experiment 2 namespace should have
        # two archived runs

        ex1_namespace = reg.namespaces['experiment1']
        self.assertEqual(1, len(ex1_namespace))
        self.assertTrue(0 in ex1_namespace)
        self.assertFalse(1 in ex1_namespace)

        ex2_namespace = reg.namespaces['experiment2']
        self.assertEqual(2, len(ex2_namespace))
        self.assertTrue(0 in ex2_namespace)
        self.assertTrue(1 in ex2_namespace)

        # Accessing one of the experiments should return the ArchivedExperiment object instance directly
        archived_experiment = ex2_namespace[1]
        with archived_experiment as e:
            self.assertEqual(10, e['value'])

    def test_namespace_folder_accessing_meta_data(self):
        reg = ExperimentRegistry(self.path)
        reg.load()

        ex1_namespace = reg.namespaces['experiment1']
        self.assertTrue(0 in ex1_namespace)
        self.assertTrue(0 in ex1_namespace.meta)
        meta = ex1_namespace.meta[0]
        self.assertIsInstance(meta, dict)
        self.assertFalse(meta['running'])
