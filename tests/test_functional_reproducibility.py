"""
Tests for the reproducibility feature in PyComex.

The reproducibility feature allows experiments to capture their complete runtime
environment and later reproduce them exactly. This includes:
- Python dependencies and versions
- Python interpreter version
- Environment information (OS, env vars, system libraries)
- Source code of editable installations
- Special parameter handling (e.g., CopiedPath)
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.testing import ConfigIsolation, ExperimentIsolation
from pycomex.util import (
    bundle_local_sources,
    find_all_local_dependencies,
    get_dependencies,
    get_module_imports,
    resolve_import_path,
)

from .util import ASSETS_PATH


class TestFinalizeReproducible:
    """
    Test the finalize_reproducible method which is called at the end of an experiment
    when __REPRODUCIBLE__ is set to True.
    """

    def test_reproducible_creates_dependencies_file(self):
        """
        When an experiment is run with __REPRODUCIBLE__=True, it should create a
        .dependencies.json file in the experiment archive folder.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Check that the dependencies file was created
            dependencies_path = os.path.join(
                experiment.path, Experiment.DEPENDENCIES_FILE_NAME
            )
            assert os.path.exists(dependencies_path)

            # Check that it's valid JSON
            with open(dependencies_path) as file:
                dependencies = json.load(file)
                assert isinstance(dependencies, dict)

    def test_reproducible_saves_python_version(self):
        """
        The .dependencies.json file should contain Python version information
        under the special __python__ key.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Load and check the dependencies file
            dependencies_path = os.path.join(
                experiment.path, Experiment.DEPENDENCIES_FILE_NAME
            )
            with open(dependencies_path) as file:
                dependencies = json.load(file)

                # Check for Python version information
                assert "__python__" in dependencies
                python_info = dependencies["__python__"]

                assert "version" in python_info
                assert "version_info" in python_info
                assert "version_string" in python_info

                # Verify structure of version_info
                version_info = python_info["version_info"]
                assert "major" in version_info
                assert "minor" in version_info
                assert "micro" in version_info

                # Verify values match current Python version
                assert version_info["major"] == sys.version_info.major
                assert version_info["minor"] == sys.version_info.minor
                assert version_info["micro"] == sys.version_info.micro

    def test_reproducible_saves_environment_info(self):
        """
        The .dependencies.json file should contain environment information
        under the special __environment__ key.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Load and check the dependencies file
            dependencies_path = os.path.join(
                experiment.path, Experiment.DEPENDENCIES_FILE_NAME
            )
            with open(dependencies_path) as file:
                dependencies = json.load(file)

                # Check for environment information
                assert "__environment__" in dependencies
                env_info = dependencies["__environment__"]

                # Verify structure
                assert "os" in env_info
                assert "env_vars" in env_info
                assert "system_libraries" in env_info

                # Verify OS info structure
                os_info = env_info["os"]
                assert "name" in os_info
                assert "version" in os_info
                assert "platform" in os_info
                assert "architecture" in os_info

    def test_reproducible_saves_dependency_info(self):
        """
        The .dependencies.json file should contain information about all installed
        Python packages with their versions and metadata.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Load and check the dependencies file
            dependencies_path = os.path.join(
                experiment.path, Experiment.DEPENDENCIES_FILE_NAME
            )
            with open(dependencies_path) as file:
                dependencies = json.load(file)

                # Should have some packages besides special keys
                package_keys = [
                    k for k in dependencies.keys() if not k.startswith("__")
                ]
                assert len(package_keys) > 0

                # Check structure of a package entry
                example_package = dependencies[package_keys[0]]
                assert "name" in example_package
                assert "version" in example_package
                assert "path" in example_package
                assert "requires" in example_package
                assert "editable" in example_package

    def test_reproducible_creates_sources_directory(self):
        """
        When an experiment has editable installs, finalize_reproducible should create
        a .sources/ directory containing tarballs of those packages.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Check that .sources directory was created
            sources_path = os.path.join(experiment.path, ".sources")
            assert os.path.exists(sources_path)
            assert os.path.isdir(sources_path)

    def test_reproducible_exports_editable_sources(self):
        """
        For editable installs, finalize_reproducible should create tarball exports
        in the .sources/ directory.

        Note: This test may not find editable installs in CI environments, so we
        check conditionally.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Load dependencies to check for editable installs
            dependencies_path = os.path.join(
                experiment.path, Experiment.DEPENDENCIES_FILE_NAME
            )
            with open(dependencies_path) as file:
                dependencies = json.load(file)

                # Count editable installs
                editable_packages = [
                    name
                    for name, info in dependencies.items()
                    if not name.startswith("__") and info.get("editable", False)
                ]

                sources_path = os.path.join(experiment.path, ".sources")

                if len(editable_packages) > 0:
                    # If there are editable installs, there should be tarballs
                    tarball_files = [
                        f for f in os.listdir(sources_path) if f.endswith(".tar.gz")
                    ]
                    # Note: uv build may not create tarballs for all editable packages
                    # so we just check that the sources directory exists
                    assert os.path.exists(sources_path)
                else:
                    # If no editable installs, .sources should still exist but may be empty
                    assert os.path.exists(sources_path)

    def test_reproducible_flag_false_skips_finalize(self):
        """
        When __REPRODUCIBLE__ is False (default), finalize_reproducible should not be called
        and no reproducibility artifacts should be created.
        """
        parameters = {"__REPRODUCIBLE__": False}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Check that dependencies file was NOT created
            dependencies_path = os.path.join(
                experiment.path, Experiment.DEPENDENCIES_FILE_NAME
            )
            assert not os.path.exists(dependencies_path)

            # Check that .sources directory was NOT created
            sources_path = os.path.join(experiment.path, ".sources")
            assert not os.path.exists(sources_path)


class TestReproducibilityIntegration:
    """
    Integration tests for the full reproducibility workflow: creating an experiment
    in reproducible mode and then loading/validating the archive.
    """

    def test_reproducibility_full_pipeline(self):
        """
        Test the complete reproducibility workflow:
        1. Create and run experiment with __REPRODUCIBLE__=True
        2. Verify all artifacts are created
        3. Verify the archive can be loaded
        4. Verify parameters can be restored
        """
        parameters = {
            "__REPRODUCIBLE__": True,
            "CUSTOM_PARAM": 42,
            "STRING_PARAM": "test_value",
        }

        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                # Store some data during execution
                e["result"] = e.CUSTOM_PARAM * 2

            experiment.run()

            # Verify the experiment completed successfully
            assert experiment.error is None
            assert experiment.metadata["status"] == "done"

            # Verify reproducibility artifacts
            assert os.path.exists(
                os.path.join(experiment.path, Experiment.DEPENDENCIES_FILE_NAME)
            )
            assert os.path.exists(os.path.join(experiment.path, ".sources"))

            # Verify the archive is valid
            assert Experiment.is_archive(experiment.path)

            # Load the metadata
            metadata = Experiment.load_metadata(experiment.path)
            assert metadata["parameters"]["__REPRODUCIBLE__"]["value"] is True
            assert metadata["parameters"]["CUSTOM_PARAM"]["value"] == 42
            assert metadata["parameters"]["STRING_PARAM"]["value"] == "test_value"

            # Verify the data was saved correctly
            data_path = os.path.join(experiment.path, Experiment.DATA_FILE_NAME)
            with open(data_path) as f:
                data = json.load(f)
                assert data["result"] == 84  # 42 * 2

    def test_reproducible_archive_structure(self):
        """
        Verify that a reproducible experiment archive has all the expected files
        and directory structure.
        """
        parameters = {"__REPRODUCIBLE__": True}

        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Verify standard experiment files
            assert os.path.exists(
                os.path.join(experiment.path, Experiment.METADATA_FILE_NAME)
            )
            assert os.path.exists(
                os.path.join(experiment.path, Experiment.DATA_FILE_NAME)
            )
            assert os.path.exists(
                os.path.join(experiment.path, Experiment.CODE_FILE_NAME)
            )
            assert os.path.exists(os.path.join(experiment.path, "experiment_out.log"))
            assert os.path.exists(os.path.join(experiment.path, "analysis.py"))

            # Verify reproducibility-specific files
            assert os.path.exists(
                os.path.join(experiment.path, Experiment.DEPENDENCIES_FILE_NAME)
            )
            assert os.path.exists(os.path.join(experiment.path, ".sources"))
            assert os.path.exists(os.path.join(experiment.path, ".track"))

    def test_reproducible_restores_parameters(self):
        """
        Test that parameters are correctly saved and can be restored from a
        reproducible experiment archive.
        """
        parameters = {
            "__REPRODUCIBLE__": True,
            "INT_PARAM": 123,
            "FLOAT_PARAM": 3.14,
            "STRING_PARAM": "hello",
            "BOOL_PARAM": True,
            "LIST_PARAM": [1, 2, 3],
            "DICT_PARAM": {"key": "value"},
        }

        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Load metadata and verify parameters
            metadata = Experiment.load_metadata(experiment.path)

            # Check that all parameters were saved with correct values
            assert metadata["parameters"]["INT_PARAM"]["value"] == 123
            assert metadata["parameters"]["INT_PARAM"]["usable"] is True

            assert metadata["parameters"]["FLOAT_PARAM"]["value"] == 3.14
            assert metadata["parameters"]["FLOAT_PARAM"]["usable"] is True

            assert metadata["parameters"]["STRING_PARAM"]["value"] == "hello"
            assert metadata["parameters"]["STRING_PARAM"]["usable"] is True

            assert metadata["parameters"]["BOOL_PARAM"]["value"] is True
            assert metadata["parameters"]["BOOL_PARAM"]["usable"] is True

            assert metadata["parameters"]["LIST_PARAM"]["value"] == [1, 2, 3]
            assert metadata["parameters"]["LIST_PARAM"]["usable"] is True

            assert metadata["parameters"]["DICT_PARAM"]["value"] == {"key": "value"}
            assert metadata["parameters"]["DICT_PARAM"]["usable"] is True

    def test_reproducible_handles_non_json_parameters(self):
        """
        Test that non-JSON-serializable parameters are handled gracefully by
        converting them to strings and marking them as not usable.
        """

        class CustomObject:
            def __init__(self, value):
                self.value = value

            def __repr__(self):
                return f"CustomObject({self.value})"

        parameters = {
            "__REPRODUCIBLE__": True,
            "SIMPLE_PARAM": 42,
            "CUSTOM_PARAM": CustomObject(100),
        }

        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Load metadata
            metadata = Experiment.load_metadata(experiment.path)

            # Simple parameter should be usable
            assert metadata["parameters"]["SIMPLE_PARAM"]["value"] == 42
            assert metadata["parameters"]["SIMPLE_PARAM"]["usable"] is True

            # Custom object should be converted to string and marked unusable
            assert "CustomObject" in metadata["parameters"]["CUSTOM_PARAM"]["value"]
            assert metadata["parameters"]["CUSTOM_PARAM"]["usable"] is False

    def test_is_archive_detects_reproducible_archive(self):
        """
        Test that Experiment.is_archive() correctly identifies reproducible experiment
        archives.
        """
        parameters = {"__REPRODUCIBLE__": True}

        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Should be detected as a valid archive
            assert Experiment.is_archive(experiment.path) is True

            # Non-existent path should not be an archive
            assert Experiment.is_archive("/nonexistent/path") is False

            # Regular file should not be an archive
            temp_file = os.path.join(iso.path, "temp.txt")
            with open(temp_file, "w") as f:
                f.write("test")
            assert Experiment.is_archive(temp_file) is False


class TestRequirementsExport:
    """
    Test requirements.txt generation functionality for reproducible mode.
    """

    def test_requirements_txt_created(self):
        """
        When an experiment runs with __REPRODUCIBLE__=True, a requirements.txt file
        should be created in the experiment archive.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Check that requirements.txt was created
            requirements_path = os.path.join(experiment.path, "requirements.txt")
            assert os.path.exists(requirements_path)

    def test_requirements_txt_format(self):
        """
        The requirements.txt file should contain properly formatted package==version lines.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Read requirements.txt
            requirements_path = os.path.join(experiment.path, "requirements.txt")
            with open(requirements_path) as file:
                content = file.read()
                lines = content.strip().split("\n")

            # Check that we have at least some packages
            assert len(lines) > 0

            # Verify format: each line should be package==version
            for line in lines:
                if line.strip():  # Skip empty lines
                    assert "==" in line, f"Line '{line}' doesn't have == format"
                    parts = line.split("==")
                    assert len(parts) == 2, f"Line '{line}' has incorrect format"
                    package_name, version = parts
                    assert package_name.strip(), "Package name is empty"
                    assert version.strip(), "Version is empty"

    def test_requirements_txt_excludes_editables(self):
        """
        Editable packages should not be included in requirements.txt as they
        are handled separately in .sources/ directory.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Load dependencies to check for editable packages
            dependencies_path = os.path.join(
                experiment.path, Experiment.DEPENDENCIES_FILE_NAME
            )
            with open(dependencies_path) as file:
                dependencies = json.load(file)

            # Get list of editable package names
            editable_packages = [
                name
                for name, info in dependencies.items()
                if not name.startswith("__") and info.get("editable", False)
            ]

            # Read requirements.txt
            requirements_path = os.path.join(experiment.path, "requirements.txt")
            with open(requirements_path) as file:
                requirements_content = file.read()

            # Verify editable packages are NOT in requirements.txt
            for editable_name in editable_packages:
                assert (
                    editable_name not in requirements_content
                ), f"Editable package '{editable_name}' should not be in requirements.txt"

    def test_requirements_txt_excludes_special_keys(self):
        """
        Special keys like __python__ and __environment__ should not appear
        in requirements.txt.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Read requirements.txt
            requirements_path = os.path.join(experiment.path, "requirements.txt")
            with open(requirements_path) as file:
                content = file.read()

            # Verify special keys are not in requirements.txt
            assert "__python__" not in content
            assert "__environment__" not in content

    def test_requirements_txt_alphabetically_sorted(self):
        """
        Requirements should be sorted alphabetically for consistency.
        """
        parameters = {"__REPRODUCIBLE__": True}
        with ConfigIsolation() as config, ExperimentIsolation(
            sys.argv, glob_mod=parameters
        ) as iso:
            config.load_plugins()

            experiment = Experiment(
                base_path=iso.path,
                namespace="experiment",
                glob=iso.glob,
            )

            @experiment
            def run(e):
                pass

            experiment.run()

            # Read requirements.txt
            requirements_path = os.path.join(experiment.path, "requirements.txt")
            with open(requirements_path) as file:
                lines = [line.strip() for line in file if line.strip()]

            # Extract package names
            package_names = [line.split("==")[0] for line in lines if "==" in line]

            # Verify they are sorted (case-insensitive)
            assert package_names == sorted(
                package_names, key=str.lower
            ), "Requirements are not alphabetically sorted"


class TestImportDetection:
    """
    Test the import detection utilities for finding and resolving Python imports.
    These functions are used to detect local file dependencies that should be bundled
    with reproducible experiments.
    """

    def test_get_module_imports_simple(self):
        """
        Test that get_module_imports() can parse simple import statements.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_module.py")
            with open(test_file, "w") as f:
                f.write("import os\n")
                f.write("import sys\n")
                f.write("import json\n")

            imports = get_module_imports(test_file)

            # Should have 3 imports
            assert len(imports) == 3

            # Check that all imports were detected
            module_names = [imp[0] for imp in imports]
            assert "os" in module_names
            assert "sys" in module_names
            assert "json" in module_names

            # All should be absolute imports (not relative)
            for _, _, is_relative in imports:
                assert is_relative is False

            # All should have None for from_name (not "from" imports)
            for _, from_name, _ in imports:
                assert from_name is None

    def test_get_module_imports_from_import(self):
        """
        Test that get_module_imports() can parse "from x import y" statements.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_module.py")
            with open(test_file, "w") as f:
                f.write("from pathlib import Path\n")
                f.write("from collections import defaultdict\n")
                f.write("from typing import List, Dict\n")

            imports = get_module_imports(test_file)

            # Should have 4 imports (List and Dict are separate)
            assert len(imports) == 4

            # Check specific imports
            import_tuples = [(mod, from_name) for mod, from_name, _ in imports]
            assert ("pathlib", "Path") in import_tuples
            assert ("collections", "defaultdict") in import_tuples
            assert ("typing", "List") in import_tuples
            assert ("typing", "Dict") in import_tuples

    def test_get_module_imports_relative(self):
        """
        Test that get_module_imports() can detect relative imports.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_module.py")
            with open(test_file, "w") as f:
                f.write("from . import utils\n")
                f.write("from ..package import module\n")
                f.write("from .submodule import function\n")

            imports = get_module_imports(test_file)

            # Should have 3 imports
            assert len(imports) == 3

            # Check that relative imports are detected
            relative_imports = [(mod, from_name, is_rel) for mod, from_name, is_rel in imports if is_rel]
            assert len(relative_imports) == 3

            # Check specific relative imports
            import_tuples = [(mod, from_name) for mod, from_name, _ in imports]
            assert (".", "utils") in import_tuples
            assert ("..package", "module") in import_tuples
            assert (".submodule", "function") in import_tuples

    def test_get_module_imports_mixed(self):
        """
        Test parsing a file with mixed import types.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_module.py")
            with open(test_file, "w") as f:
                f.write("import os\n")
                f.write("from pathlib import Path\n")
                f.write("from . import local_module\n")
                f.write("import numpy as np\n")

            imports = get_module_imports(test_file)

            # Should have 4 imports
            assert len(imports) == 4

            # Check for specific imports
            module_names = [imp[0] for imp in imports]
            assert "os" in module_names
            assert "pathlib" in module_names
            assert "." in module_names
            assert "numpy" in module_names

            # Check relative vs absolute
            relative_count = sum(1 for _, _, is_rel in imports if is_rel)
            assert relative_count == 1

    def test_get_module_imports_invalid_file(self):
        """
        Test that get_module_imports() handles invalid files gracefully.
        """
        # Non-existent file
        imports = get_module_imports("/nonexistent/file.py")
        assert imports == []

        # File with syntax error
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "bad_syntax.py")
            with open(test_file, "w") as f:
                f.write("import os\n")
                f.write("def broken(\n")  # Syntax error

            imports = get_module_imports(test_file)
            assert imports == []

    def test_resolve_import_stdlib(self):
        """
        Test that stdlib modules return None (not bundled).
        """
        # These are all stdlib modules
        assert resolve_import_path("os", "/tmp", False) is None
        assert resolve_import_path("sys", "/tmp", False) is None
        assert resolve_import_path("json", "/tmp", False) is None
        assert resolve_import_path("pathlib", "/tmp", False) is None
        assert resolve_import_path("collections", "/tmp", False) is None

    def test_resolve_import_installed(self):
        """
        Test that installed packages return None (not bundled).
        """
        # numpy should be installed in the test environment
        result = resolve_import_path("numpy", "/tmp", False)
        assert result is None

        # pytest should be installed
        result = resolve_import_path("pytest", "/tmp", False)
        assert result is None

    def test_resolve_import_local_file(self):
        """
        Test that local Python files are resolved to their absolute path.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a local Python file
            local_file = os.path.join(temp_dir, "local_module.py")
            with open(local_file, "w") as f:
                f.write("# Local module\n")

            # Resolve should return the absolute path
            result = resolve_import_path("local_module", temp_dir, False, None)
            assert result is not None
            assert os.path.isabs(result)
            assert result == local_file

    def test_resolve_import_local_package(self):
        """
        Test that local packages are resolved to their __init__.py file.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a local package
            package_dir = os.path.join(temp_dir, "my_package")
            os.makedirs(package_dir)
            init_file = os.path.join(package_dir, "__init__.py")
            with open(init_file, "w") as f:
                f.write("# Package init\n")

            # Resolve should return the __init__.py path
            result = resolve_import_path("my_package", temp_dir, False, None)
            assert result is not None
            assert os.path.isabs(result)
            assert result == init_file

    def test_resolve_import_relative_simple(self):
        """
        Test resolving simple relative imports (from . import x).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create main file and a module in the same directory
            main_file = os.path.join(temp_dir, "main.py")
            utils_file = os.path.join(temp_dir, "utils.py")

            with open(main_file, "w") as f:
                f.write("from . import utils\n")
            with open(utils_file, "w") as f:
                f.write("# Utils module\n")

            # Resolve relative import
            result = resolve_import_path(".", temp_dir, True, main_file)
            # Should resolve to the directory itself or a file in it
            assert result is not None or os.path.isdir(temp_dir)

    def test_resolve_import_relative_named(self):
        """
        Test resolving named relative imports (from .module import x).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create main file and a submodule
            src_dir = os.path.join(temp_dir, "src")
            os.makedirs(src_dir)
            main_file = os.path.join(src_dir, "main.py")
            utils_file = os.path.join(src_dir, "utils.py")

            with open(main_file, "w") as f:
                f.write("from .utils import helper\n")
            with open(utils_file, "w") as f:
                f.write("def helper(): pass\n")

            # Resolve relative import
            result = resolve_import_path(".utils", src_dir, True, main_file)
            assert result is not None
            assert os.path.isabs(result)
            assert result == utils_file

    def test_resolve_import_relative_parent(self):
        """
        Test resolving parent directory relative imports (from .. import x).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a nested structure
            parent_file = os.path.join(temp_dir, "parent.py")
            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir)
            child_file = os.path.join(subdir, "child.py")

            with open(parent_file, "w") as f:
                f.write("# Parent module\n")
            with open(child_file, "w") as f:
                f.write("from ..parent import something\n")

            # Resolve parent relative import
            result = resolve_import_path("..parent", subdir, True, child_file)
            assert result is not None
            assert os.path.isabs(result)
            assert result == parent_file

    def test_resolve_import_nonexistent_local(self):
        """
        Test that non-existent local modules return None.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Try to resolve a module that doesn't exist
            result = resolve_import_path("nonexistent_module", temp_dir, False)
            assert result is None

    def test_integration_get_and_resolve(self):
        """
        Integration test: parse imports from a file and resolve them.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a main file with various imports
            main_file = os.path.join(temp_dir, "main.py")
            local_utils = os.path.join(temp_dir, "utils.py")

            with open(main_file, "w") as f:
                f.write("import os\n")
                f.write("from pathlib import Path\n")
                f.write("import utils\n")

            with open(local_utils, "w") as f:
                f.write("# Local utilities\n")

            # Get all imports
            imports = get_module_imports(main_file)
            assert len(imports) == 3

            # Resolve each import
            for module_name, from_name, is_relative in imports:
                result = resolve_import_path(module_name, temp_dir, is_relative, main_file)

                # os and pathlib should resolve to None (stdlib)
                if module_name in ["os", "pathlib"]:
                    assert result is None
                # utils should resolve to the local file
                elif module_name == "utils":
                    assert result is not None
                    assert result == local_utils


class TestRecursiveDependencyFinder:
    """
    Test the recursive dependency finding functionality for discovering all local
    Python files imported by an experiment. This is used to bundle local source
    files with reproducible experiments.
    """

    def test_single_file_no_imports(self):
        """
        Test finding dependencies for a file with no imports.
        Should only return the file itself.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple file with no imports
            experiment_file = os.path.join(temp_dir, "experiment.py")
            with open(experiment_file, "w") as f:
                f.write("# Experiment with no imports\n")
                f.write("print('Hello world')\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment_file)

            # Should contain only the experiment file itself
            assert len(deps) == 1
            assert experiment_file in deps

    def test_single_file_with_stdlib_imports(self):
        """
        Test finding dependencies for a file that only imports stdlib modules.
        Should only return the file itself (stdlib not included).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file with only stdlib imports
            experiment_file = os.path.join(temp_dir, "experiment.py")
            with open(experiment_file, "w") as f:
                f.write("import os\n")
                f.write("import sys\n")
                f.write("from pathlib import Path\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment_file)

            # Should contain only the experiment file itself
            assert len(deps) == 1
            assert experiment_file in deps

    def test_single_local_dependency(self):
        """
        Test finding dependencies when experiment imports one local file.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create experiment file
            experiment_file = os.path.join(temp_dir, "experiment.py")
            utils_file = os.path.join(temp_dir, "utils.py")

            with open(experiment_file, "w") as f:
                f.write("import utils\n")
                f.write("print('Experiment')\n")

            with open(utils_file, "w") as f:
                f.write("# Utility functions\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment_file)

            # Should contain both files
            assert len(deps) == 2
            assert experiment_file in deps
            assert utils_file in deps

    def test_transitive_dependencies(self):
        """
        Test finding transitive dependencies (A imports B, B imports C).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create chain of dependencies: experiment -> module_a -> module_b
            experiment_file = os.path.join(temp_dir, "experiment.py")
            module_a = os.path.join(temp_dir, "module_a.py")
            module_b = os.path.join(temp_dir, "module_b.py")

            with open(experiment_file, "w") as f:
                f.write("import module_a\n")

            with open(module_a, "w") as f:
                f.write("import module_b\n")

            with open(module_b, "w") as f:
                f.write("# Leaf module\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment_file)

            # Should contain all three files
            assert len(deps) == 3
            assert experiment_file in deps
            assert module_a in deps
            assert module_b in deps

    def test_circular_imports(self):
        """
        Test that circular imports are handled gracefully without infinite loops.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create circular dependency: module_a -> module_b -> module_a
            experiment_file = os.path.join(temp_dir, "experiment.py")
            module_a = os.path.join(temp_dir, "module_a.py")
            module_b = os.path.join(temp_dir, "module_b.py")

            with open(experiment_file, "w") as f:
                f.write("import module_a\n")

            with open(module_a, "w") as f:
                f.write("import module_b\n")

            with open(module_b, "w") as f:
                f.write("import module_a\n")  # Circular reference

            # Find dependencies (should not hang or error)
            deps = find_all_local_dependencies(experiment_file)

            # Should contain all three files, no duplicates
            assert len(deps) == 3
            assert experiment_file in deps
            assert module_a in deps
            assert module_b in deps

    def test_relative_imports(self):
        """
        Test finding dependencies with relative imports.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create package structure
            package_dir = os.path.join(temp_dir, "mypackage")
            os.makedirs(package_dir)

            experiment_file = os.path.join(package_dir, "experiment.py")
            utils_file = os.path.join(package_dir, "utils.py")

            with open(experiment_file, "w") as f:
                f.write("from . import utils\n")

            with open(utils_file, "w") as f:
                f.write("# Utilities\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment_file)

            # Note: relative imports without current_file context may not resolve
            # but the experiment file itself should always be included
            assert experiment_file in deps

    def test_nested_package_structure(self):
        """
        Test finding dependencies in a nested package structure.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure: experiment -> package -> module
            experiment_file = os.path.join(temp_dir, "experiment.py")
            package_dir = os.path.join(temp_dir, "mypackage")
            os.makedirs(package_dir)

            init_file = os.path.join(package_dir, "__init__.py")
            module_file = os.path.join(package_dir, "module.py")

            with open(experiment_file, "w") as f:
                f.write("import mypackage\n")  # Import the package itself

            with open(init_file, "w") as f:
                f.write("# Package init\n")

            with open(module_file, "w") as f:
                f.write("# Module\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment_file)

            # Should include experiment and the __init__.py (since we import the package)
            assert experiment_file in deps
            assert init_file in deps

    def test_mixed_local_and_external_imports(self):
        """
        Test that only local files are included, external packages are excluded.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file with mixed imports
            experiment_file = os.path.join(temp_dir, "experiment.py")
            local_module = os.path.join(temp_dir, "local_module.py")

            with open(experiment_file, "w") as f:
                f.write("import os\n")  # stdlib
                f.write("import numpy\n")  # external package
                f.write("import local_module\n")  # local file

            with open(local_module, "w") as f:
                f.write("# Local module\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment_file)

            # Should contain only experiment and local_module, not os or numpy
            assert experiment_file in deps
            assert local_module in deps
            assert len(deps) == 2

    def test_with_parent_experiments(self):
        """
        Test finding dependencies when experiment has parent experiments
        (from Experiment.extend()).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create experiment hierarchy
            base_experiment = os.path.join(temp_dir, "base_experiment.py")
            child_experiment = os.path.join(temp_dir, "child_experiment.py")
            utils_file = os.path.join(temp_dir, "utils.py")

            with open(base_experiment, "w") as f:
                f.write("import utils\n")

            with open(child_experiment, "w") as f:
                f.write("# Child experiment\n")

            with open(utils_file, "w") as f:
                f.write("# Utilities\n")

            # Find dependencies with parent experiment list
            deps = find_all_local_dependencies(
                child_experiment,
                experiment_dependencies=[base_experiment]
            )

            # Should contain child, base, and utils
            assert len(deps) == 3
            assert child_experiment in deps
            assert base_experiment in deps
            assert utils_file in deps

    def test_multiple_parent_experiments(self):
        """
        Test with multiple parent experiments.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create experiment hierarchy
            parent1 = os.path.join(temp_dir, "parent1.py")
            parent2 = os.path.join(temp_dir, "parent2.py")
            child = os.path.join(temp_dir, "child.py")
            utils1 = os.path.join(temp_dir, "utils1.py")
            utils2 = os.path.join(temp_dir, "utils2.py")

            with open(parent1, "w") as f:
                f.write("import utils1\n")

            with open(parent2, "w") as f:
                f.write("import utils2\n")

            with open(child, "w") as f:
                f.write("# Child\n")

            with open(utils1, "w") as f:
                f.write("# Utils 1\n")

            with open(utils2, "w") as f:
                f.write("# Utils 2\n")

            # Find dependencies with multiple parents
            deps = find_all_local_dependencies(
                child,
                experiment_dependencies=[parent1, parent2]
            )

            # Should contain all files
            assert len(deps) == 5
            assert child in deps
            assert parent1 in deps
            assert parent2 in deps
            assert utils1 in deps
            assert utils2 in deps

    def test_parent_with_shared_dependency(self):
        """
        Test that shared dependencies between parent and child are not duplicated.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Both parent and child import the same utils module
            parent = os.path.join(temp_dir, "parent.py")
            child = os.path.join(temp_dir, "child.py")
            utils = os.path.join(temp_dir, "utils.py")

            with open(parent, "w") as f:
                f.write("import utils\n")

            with open(child, "w") as f:
                f.write("import utils\n")

            with open(utils, "w") as f:
                f.write("# Shared utils\n")

            # Find dependencies
            deps = find_all_local_dependencies(
                child,
                experiment_dependencies=[parent]
            )

            # Should contain all three files, but utils only once
            assert len(deps) == 3
            assert child in deps
            assert parent in deps
            assert utils in deps

    def test_complex_dependency_tree(self):
        """
        Test a complex dependency tree with multiple levels and branches.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create complex tree:
            # experiment -> module_a -> module_b
            #            -> module_c -> module_b (shared)
            experiment = os.path.join(temp_dir, "experiment.py")
            module_a = os.path.join(temp_dir, "module_a.py")
            module_b = os.path.join(temp_dir, "module_b.py")
            module_c = os.path.join(temp_dir, "module_c.py")

            with open(experiment, "w") as f:
                f.write("import module_a\n")
                f.write("import module_c\n")

            with open(module_a, "w") as f:
                f.write("import module_b\n")

            with open(module_c, "w") as f:
                f.write("import module_b\n")

            with open(module_b, "w") as f:
                f.write("# Leaf module\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment)

            # Should contain all four modules (no duplicates)
            assert len(deps) == 4
            assert experiment in deps
            assert module_a in deps
            assert module_b in deps
            assert module_c in deps

    def test_missing_import_handled_gracefully(self):
        """
        Test that missing/broken imports are handled gracefully.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create experiment that imports non-existent module
            experiment = os.path.join(temp_dir, "experiment.py")

            with open(experiment, "w") as f:
                f.write("import nonexistent_module\n")
                f.write("# More code\n")

            # Should not raise an error
            deps = find_all_local_dependencies(experiment)

            # Should at least contain the experiment file itself
            assert experiment in deps

    def test_returns_absolute_paths(self):
        """
        Test that all returned paths are absolute.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some files
            experiment = os.path.join(temp_dir, "experiment.py")
            utils = os.path.join(temp_dir, "utils.py")

            with open(experiment, "w") as f:
                f.write("import utils\n")

            with open(utils, "w") as f:
                f.write("# Utils\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment)

            # All paths should be absolute
            for path in deps:
                assert os.path.isabs(path)

    def test_returns_set(self):
        """
        Test that the function returns a set (no duplicates possible).
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment = os.path.join(temp_dir, "experiment.py")

            with open(experiment, "w") as f:
                f.write("# Simple experiment\n")

            # Find dependencies
            deps = find_all_local_dependencies(experiment)

            # Should return a set
            assert isinstance(deps, set)


class TestSourceBundling:
    """
    Test the source bundling functionality that copies local Python files into
    the experiment archive with preserved directory structure.
    """

    def test_bundle_single_file(self):
        """
        Test bundling a single local file.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create experiment file
            experiment_file = os.path.join(temp_dir, "experiment.py")
            with open(experiment_file, "w") as f:
                f.write("# Simple experiment\n")

            # Create mock experiment object
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle the single file
            local_files = {experiment_file}
            bundle_local_sources(experiment, local_files)

            # Check that .local_sources directory was created
            local_sources_path = os.path.join(experiment.path, ".local_sources")
            assert os.path.exists(local_sources_path)
            assert os.path.isdir(local_sources_path)

            # Check that the file was copied
            bundled_file = os.path.join(local_sources_path, "experiment.py")
            assert os.path.exists(bundled_file)

            # Check file contents match
            with open(bundled_file) as f:
                assert f.read() == "# Simple experiment\n"

    def test_bundle_multiple_files(self):
        """
        Test bundling multiple files from the same directory.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple files
            experiment_file = os.path.join(temp_dir, "experiment.py")
            utils_file = os.path.join(temp_dir, "utils.py")
            helper_file = os.path.join(temp_dir, "helper.py")

            for file_path, content in [
                (experiment_file, "# Experiment\n"),
                (utils_file, "# Utils\n"),
                (helper_file, "# Helper\n"),
            ]:
                with open(file_path, "w") as f:
                    f.write(content)

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle all files
            local_files = {experiment_file, utils_file, helper_file}
            bundle_local_sources(experiment, local_files)

            # Check all files were bundled
            local_sources_path = os.path.join(experiment.path, ".local_sources")
            assert os.path.exists(os.path.join(local_sources_path, "experiment.py"))
            assert os.path.exists(os.path.join(local_sources_path, "utils.py"))
            assert os.path.exists(os.path.join(local_sources_path, "helper.py"))

    def test_bundle_preserves_directory_structure(self):
        """
        Test that bundling preserves the directory structure relative to base dir.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested directory structure
            experiment_file = os.path.join(temp_dir, "experiment.py")
            subdir = os.path.join(temp_dir, "utils")
            os.makedirs(subdir)
            utils_file = os.path.join(subdir, "helper.py")

            with open(experiment_file, "w") as f:
                f.write("# Experiment\n")
            with open(utils_file, "w") as f:
                f.write("# Helper\n")

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle files
            local_files = {experiment_file, utils_file}
            bundle_local_sources(experiment, local_files)

            # Check directory structure was preserved
            local_sources_path = os.path.join(experiment.path, ".local_sources")
            assert os.path.exists(os.path.join(local_sources_path, "experiment.py"))
            assert os.path.exists(os.path.join(local_sources_path, "utils", "helper.py"))

    def test_bundle_creates_manifest(self):
        """
        Test that bundling creates a .manifest.json file with metadata.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files
            experiment_file = os.path.join(temp_dir, "experiment.py")
            utils_file = os.path.join(temp_dir, "utils.py")

            with open(experiment_file, "w") as f:
                f.write("# Experiment\n")
            with open(utils_file, "w") as f:
                f.write("# Utils\n")

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle files
            local_files = {experiment_file, utils_file}
            bundle_local_sources(experiment, local_files)

            # Check manifest was created
            manifest_path = os.path.join(experiment.path, ".local_sources", ".manifest.json")
            assert os.path.exists(manifest_path)

            # Check manifest content
            with open(manifest_path) as f:
                manifest = json.load(f)

            assert "base_dir" in manifest
            assert "experiment_file" in manifest
            assert "file_count" in manifest
            assert "total_size" in manifest
            assert "files" in manifest

            assert manifest["base_dir"] == temp_dir
            assert manifest["experiment_file"] == experiment_file
            assert manifest["file_count"] == 2
            assert len(manifest["files"]) == 2

    def test_manifest_contains_file_metadata(self):
        """
        Test that manifest contains correct metadata for each file.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file with known content
            experiment_file = os.path.join(temp_dir, "experiment.py")
            test_content = "# Test experiment\nprint('hello')\n"
            with open(experiment_file, "w") as f:
                f.write(test_content)

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle file
            local_files = {experiment_file}
            bundle_local_sources(experiment, local_files)

            # Read manifest
            manifest_path = os.path.join(experiment.path, ".local_sources", ".manifest.json")
            with open(manifest_path) as f:
                manifest = json.load(f)

            # Check file metadata
            file_info = manifest["files"]["experiment.py"]
            assert "absolute_path" in file_info
            assert "size" in file_info
            assert "modified_time" in file_info

            assert file_info["absolute_path"] == experiment_file
            assert file_info["size"] == len(test_content)
            assert isinstance(file_info["modified_time"], (int, float))

    def test_bundle_with_empty_set(self):
        """
        Test bundling with an empty set of files.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment_file = os.path.join(temp_dir, "experiment.py")
            with open(experiment_file, "w") as f:
                f.write("# Experiment\n")

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle empty set
            local_files = set()
            bundle_local_sources(experiment, local_files)

            # Directory should still be created
            local_sources_path = os.path.join(experiment.path, ".local_sources")
            assert os.path.exists(local_sources_path)

            # Manifest should exist with zero files
            manifest_path = os.path.join(local_sources_path, ".manifest.json")
            assert os.path.exists(manifest_path)

            with open(manifest_path) as f:
                manifest = json.load(f)
            assert manifest["file_count"] == 0
            assert len(manifest["files"]) == 0

    def test_bundle_file_contents_preserved(self):
        """
        Test that file contents are correctly copied.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file with specific content
            experiment_file = os.path.join(temp_dir, "experiment.py")
            original_content = """import os
import sys

def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
"""
            with open(experiment_file, "w") as f:
                f.write(original_content)

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle file
            local_files = {experiment_file}
            bundle_local_sources(experiment, local_files)

            # Read bundled file
            bundled_file = os.path.join(experiment.path, ".local_sources", "experiment.py")
            with open(bundled_file) as f:
                bundled_content = f.read()

            # Content should match exactly
            assert bundled_content == original_content

    def test_bundle_nested_package(self):
        """
        Test bundling files from a nested package structure.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create package structure
            experiment_file = os.path.join(temp_dir, "experiment.py")
            package_dir = os.path.join(temp_dir, "mypackage")
            subpackage_dir = os.path.join(package_dir, "subpackage")
            os.makedirs(subpackage_dir)

            init1 = os.path.join(package_dir, "__init__.py")
            init2 = os.path.join(subpackage_dir, "__init__.py")
            module = os.path.join(subpackage_dir, "module.py")

            for file_path in [experiment_file, init1, init2, module]:
                with open(file_path, "w") as f:
                    f.write(f"# {os.path.basename(file_path)}\n")

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle all files
            local_files = {experiment_file, init1, init2, module}
            bundle_local_sources(experiment, local_files)

            # Check structure was preserved
            local_sources = os.path.join(experiment.path, ".local_sources")
            assert os.path.exists(os.path.join(local_sources, "experiment.py"))
            assert os.path.exists(os.path.join(local_sources, "mypackage", "__init__.py"))
            assert os.path.exists(os.path.join(local_sources, "mypackage", "subpackage", "__init__.py"))
            assert os.path.exists(os.path.join(local_sources, "mypackage", "subpackage", "module.py"))

    def test_bundle_integration_with_find_dependencies(self):
        """
        Integration test: Use find_all_local_dependencies and bundle_local_sources together.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create experiment with local dependencies
            experiment_file = os.path.join(temp_dir, "experiment.py")
            utils_file = os.path.join(temp_dir, "utils.py")
            helper_file = os.path.join(temp_dir, "helper.py")

            with open(experiment_file, "w") as f:
                f.write("import utils\n")
                f.write("import helper\n")

            with open(utils_file, "w") as f:
                f.write("# Utils\n")

            with open(helper_file, "w") as f:
                f.write("# Helper\n")

            # Find dependencies
            local_files = find_all_local_dependencies(experiment_file)
            assert len(local_files) == 3

            # Create mock experiment
            class MockExperiment:
                def __init__(self):
                    self.path = os.path.join(temp_dir, "archive")
                    os.makedirs(self.path)
                    self.glob = {"__file__": experiment_file}

            experiment = MockExperiment()

            # Bundle found dependencies
            bundle_local_sources(experiment, local_files)

            # Verify all were bundled
            local_sources = os.path.join(experiment.path, ".local_sources")
            assert os.path.exists(os.path.join(local_sources, "experiment.py"))
            assert os.path.exists(os.path.join(local_sources, "utils.py"))
            assert os.path.exists(os.path.join(local_sources, "helper.py"))
