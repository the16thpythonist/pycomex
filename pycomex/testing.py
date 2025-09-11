import random
import sys
import tempfile
import typing as t
from copy import deepcopy

import matplotlib.pyplot as plt

from pycomex.config import Config


def random_plot() -> plt.Figure:
    fig, ax = plt.subplots(1, 1)
    ax.scatter(
        [random.random() for _ in range(10)],
        [random.random() for _ in range(10)],
    )
    return fig


class MockConfig:
    """
    This class can be used as a stand-in for a ``config.Config`` object. It is used in instances
    where the actual config singleton shouldn't be constructed.
    """

    def __init__(self, data: dict = {}):
        self.data = data


class ConfigIsolation:
    """
    This class is a context manager that can be used to properly isolate the config singleton
    during testing. The problem is that the config class is a global singleton and therefore the
    constructor of the class always returns the same object. For any tests that in some way modify
    that config object, this can lead to side effects in other tests. This context manager can be
    used to isolate the config object for a specific test like this:

    .. code-block:: python

        with self.ConfigIsolation() as config:
            # do something with the config object

        # afterwards the config will be restored to the previous state

    This context manager will save the state of the config object when entering the context, then
    reset the config object to its default state. When exiting the context, the config object will
    be restored to the state it was in when entering the context.
    """

    def __init__(self, reset: bool = True):
        self.config = Config()
        self.reset = reset
        self.config_state: dict = None

    def __enter__(self):
        self.config_state = self.config.export_state()
        self.config.reset_state()

        return self.config

    def __exit__(self, *args):
        self.config_state = self.config.import_state(self.config_state)


class ExperimentIsolation:
    """
    This class implements a context manager, which can be used to test the
    ``pycomex.experiment.Experiment`` class. It provided the following functionality for this purpose:

    - The experiment class requires a folder into which the archive of the experiment and the additional
      artifacts will be saved into. ExperimentIsolation internally maintains a TemporaryDirectory which
      can be used as the parent folder for the experiment archive.
    - The experiment class needs to receive a globals() dictionary. ExperimentIsolation provides the
      possibility to temporarily modify the globals dict within the context only. For that purpose it
      modifies the globals() dict on __enter__ and restores all the original values on __exit__
    - It is also possible to temporarily modify the global sys.argv which experiments also conditionally
      depend on when they are invoked via the command line.

    Example usage:

    .. code-block:: python

        import sys
        from pycomex.functional import Experiment
        from pycomex.testing import ExperimentIsolation

        with ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace='experiment',
                glob=iso.glob,
            )

    :param argv: A list of strings that will be used as the sys.argv for the experiment execution
    :param glob_mod: A dictionary that will be merged into the globals() dict for the experiment execution. This
        can optionally be used to modify the behavior of the experiment during the test by overwriting
        parameter values for example.
    """

    def __init__(self, argv: list[str] = [], glob_mod: dict = {}):
        self.temporary_directory = tempfile.TemporaryDirectory()
        # This field will store the actual string path for the temporary directory once the __enter__
        # method has been called and the directory is created.
        self.path: str | None = None
        self.glob: dict | None = globals()

        self.modified_globals = {
            # This is the main modification which we need to make to actually enable any experiment to run
            # Upon __enter__, Experiments will check the magic __name__ variable and they will only actually
            # execute all the code within the context body if that variable's value is __main__ aka when
            # they detect a direct execution of the module as opposed to a simple import for example.
            # Here we modify it to make the experiment think that it is a direct execution to make it run.
            "__name__": "__main__",
            # As a default we want to disable the system notifications for the testing of the experiments.
            "__NOTIFY__": False,
            **glob_mod,
        }
        self.original_globals = globals().copy()

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

        # 03.01.2023
        # Before, this section did not delete the keys which were not part of the original glob dict, but
        # instead just overwrote the ones that existed anyway. As I found out, this caused a bunch of
        # side effects during testing, but most importantly it was causing major problems for
        # experiment inheritance.
        globals_keys = list(globals().keys())
        for key in globals_keys:
            if key not in ["__experiment__"]:
                if key in self.original_globals:
                    globals()[key] = self.original_globals[key]
                else:
                    del globals()[key]

        # ~ reset the original argv
        sys.argv = self.original_argv


class ArgumentIsolation:

    def __init__(self, argv: list = []):
        self.original_argv = sys.argv
        self.modified_argv = argv

    def __enter__(self):
        sys.argv = self.modified_argv

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.argv = self.original_argv
