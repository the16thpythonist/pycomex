import tempfile
import sys
import typing as t


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
    """
    def __init__(self, argv: t.List[str] = [], glob_mod: dict = {}):
        self.temporary_directory = tempfile.TemporaryDirectory()
        # This field will store the actual string path for the temporary directory once the __enter__
        # method has been called and the directory is created.
        self.path: t.Optional[str] = None
        self.glob: t.Optional[dict] = globals()

        self.modified_globals = {
            # This is the main modification which we need to make to actually enable any experiment to run
            # Upon __enter__, Experiments will check the magic __name__ variable and they will only actually
            # execute all the code within the context body if that variable's value is __main__ aka when
            # they detect a direct execution of the module as opposed to a simple import for example.
            # Here we modify it to make the experiment think that it is a direct execution to make it run.
            '__name__': '__main__',
            **glob_mod
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
