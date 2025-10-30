import os
import sys
import typing

import pytest

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.functional.parameter import CopiedPath
from pycomex.testing import ConfigIsolation, ExperimentIsolation


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

    def test_copied_path_with_directory(self):
        """
        Test that CopiedPath correctly copies entire directories in reproducible mode.
        """
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

            # Create a directory with some files
            dir_path = os.path.join(iso.path, "test_dir")
            os.makedirs(dir_path)

            # Create some files in the directory
            with open(os.path.join(dir_path, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(dir_path, "file2.txt"), "w") as f:
                f.write("content2")

            # Create a subdirectory
            sub_dir = os.path.join(dir_path, "subdir")
            os.makedirs(sub_dir)
            with open(os.path.join(sub_dir, "file3.txt"), "w") as f:
                f.write("content3")

            # Copy the directory
            CopiedPath.on_reproducible(experiment=experiment, value=dir_path)
            copy_path = os.path.join(experiment.path, "test_dir.copy")

            # Verify the copy exists and has the same structure
            assert os.path.exists(copy_path)
            assert os.path.isdir(copy_path)
            assert os.path.exists(os.path.join(copy_path, "file1.txt"))
            assert os.path.exists(os.path.join(copy_path, "file2.txt"))
            assert os.path.exists(os.path.join(copy_path, "subdir", "file3.txt"))

            # Verify content
            with open(os.path.join(copy_path, "file1.txt")) as f:
                assert f.read() == "content1"

            # When original exists, get should return original path
            dest_path = CopiedPath.get(experiment=experiment, value=dir_path)
            assert dest_path == dir_path

            # When original doesn't exist, get should return copy path
            import shutil
            shutil.rmtree(dir_path)
            dest_path = CopiedPath.get(experiment=experiment, value=dir_path)
            assert dest_path == copy_path

    def test_copied_path_in_reproducible_experiment(self):
        """
        Test that CopiedPath.on_reproducible() correctly copies files when called directly.
        This documents the expected behavior even though automatic triggering requires
        proper type annotations in the experiment module.
        """
        # Create a test file
        with ExperimentIsolation(sys.argv) as iso:
            test_file = os.path.join(iso.path, "input_file.txt")
            with open(test_file, "w") as f:
                f.write("test data")

            parameters = {
                "__REPRODUCIBLE__": False,  # Set to False to avoid automatic triggering
                "INPUT_PATH": test_file,
            }

            with ConfigIsolation() as config:
                config.load_plugins()

                experiment = Experiment(
                    base_path=iso.path,
                    namespace="experiment",
                    glob=iso.glob,
                )

                # Properly initialize the parameter with metadata
                experiment.parameters["INPUT_PATH"] = test_file
                experiment.metadata["parameters"]["INPUT_PATH"] = {
                    "name": "INPUT_PATH",
                }

                @experiment
                def run(e):
                    # Access the parameter
                    path = e.INPUT_PATH
                    assert os.path.exists(path)

                experiment.run()

                # Verify the experiment completed successfully
                assert experiment.error is None

                # Manually call on_reproducible to test the functionality
                CopiedPath.on_reproducible(experiment=experiment, value=test_file)

                # Verify copy was created
                copy_path = os.path.join(experiment.path, "input_file.txt.copy")
                assert os.path.exists(copy_path)

                # Verify content matches
                with open(copy_path) as f:
                    assert f.read() == "test data"

    def test_copied_path_nonexistent_file(self):
        """
        Test that CopiedPath handles non-existent paths gracefully.
        """
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

            # Try to copy a non-existent file
            nonexistent_path = os.path.join(iso.path, "nonexistent.txt")

            # on_reproducible should handle non-existent paths without error
            CopiedPath.on_reproducible(experiment=experiment, value=nonexistent_path)

            # Copy should not be created
            copy_path = os.path.join(experiment.path, "nonexistent.txt.copy")
            assert not os.path.exists(copy_path)

            # get() should return the copy path when original doesn't exist
            # but copy also doesn't exist, so it returns the copy path anyway
            dest_path = CopiedPath.get(experiment=experiment, value=nonexistent_path)
            assert dest_path == copy_path

    def test_copied_path_preserves_file_content(self):
        """
        Test that CopiedPath preserves the exact content of copied files.
        """
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

            # Create a file with specific content
            file_path = os.path.join(iso.path, "data.txt")
            test_content = "This is test data\nwith multiple lines\nand special chars: !@#$%"
            with open(file_path, "w") as f:
                f.write(test_content)

            # Copy the file
            CopiedPath.on_reproducible(experiment=experiment, value=file_path)
            copy_path = os.path.join(experiment.path, "data.txt.copy")

            # Verify content is identical
            with open(copy_path) as f:
                copied_content = f.read()
            assert copied_content == test_content

    def test_copied_path_with_binary_file(self):
        """
        Test that CopiedPath works with binary files.
        """
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

            # Create a binary file
            file_path = os.path.join(iso.path, "binary.dat")
            test_data = bytes([0, 1, 2, 255, 254, 128, 127])
            with open(file_path, "wb") as f:
                f.write(test_data)

            # Copy the file
            CopiedPath.on_reproducible(experiment=experiment, value=file_path)
            copy_path = os.path.join(experiment.path, "binary.dat.copy")

            # Verify binary content is identical
            with open(copy_path, "rb") as f:
                copied_data = f.read()
            assert copied_data == test_data
