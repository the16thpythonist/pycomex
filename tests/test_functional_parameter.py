import os
import sys
import typing

import pytest

from pycomex.functional.experiment import Experiment
from pycomex.functional.parameter import CopiedPath
from pycomex.testing import ExperimentIsolation


class TestCopiedPath:

    def test_cannot_be_constructed(self):
        """
        It is purely supposed to act as a type annotation and should raise an error if attempted to be instantiated.
        """
        with pytest.raises(TypeError):
            CopiedPath()

    def test_works_as_type_annotation(self):
        assert CopiedPath

        def function() -> CopiedPath:
            return "value"

        assert typing.get_type_hints(function)["return"] is CopiedPath

    def test_basically_works(self):

        with ExperimentIsolation(sys.argv) as iso:

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(*args, **kwargs):
                return

            experiment.run()

            # ~ create a file
            file_path = os.path.join(iso.path, "file.txt")
            with open(file_path, "w") as file:
                file.write("content")

            # This should now create a copy with the suffix '.copy' in the experiment
            # archive folder!
            CopiedPath.on_reproducible(experiment=experiment, value=file_path)
            copy_path = os.path.join(experiment.path, "file.txt.copy")
            assert os.path.exists(copy_path)

            # By default the get method should return the original path, if that exists!
            dest_path = CopiedPath.get(experiment=experiment, value=file_path)
            assert dest_path == file_path

            # If we now remove the original file such that it does not exist anymore and call the "get"
            # method of the CopiedPath class, it should return the path to the copied file and not to the
            # original file.
            os.remove(file_path)
            dest_path = CopiedPath.get(experiment=experiment, value=file_path)
            assert dest_path != file_path
            assert dest_path == copy_path
