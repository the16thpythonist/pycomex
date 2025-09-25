import os
import shutil
import webbrowser
from pathlib import Path
from typing import List

import nox

nox.options.default_venv_backend = "uv"




# Supported Python versions for testing
PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12"]


@nox.session(python=PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    """Run the test suite across multiple Python versions."""
    session.install(".[test]")
    session.run("pytest", "tests/", "-v")


# @nox.session(python="3.10")
# def test_coverage(session: nox.Session) -> None:
#     """Run tests with coverage reporting."""
#     session.install(".[test]")
#     session.run("pytest", "tests/", "--cov=pycomex", "--cov-report=term-missing", "--cov-report=html")


@nox.session(python="3.10")
def lint(session: nox.Session) -> None:
    """Run linting with ruff and black."""
    session.install(".[dev]")
    session.run("ruff", "check", "pycomex/", "tests/")


@nox.session(python="3.10")
def format(session: nox.Session) -> None:
    """Format code with black and ruff."""
    session.install(".[dev]")
    session.run("ruff", "check", "--fix", "pycomex/", "tests/")


@nox.session(python=PYTHON_VERSIONS)
def install_test(session: nox.Session) -> None:
    """Test package installation across Python versions."""
    session.install(".")
    session.run("python", "-c", "import pycomex; print(f'Successfully imported pycomex {pycomex.__version__}')")
    session.run("pycomex", "--version")


# @nox.session(python="3.10")
# def docs(session: nox.Session) -> None:
#     """Build documentation."""
#     session.install(".")
#     if os.path.exists("docs/requirements.txt"):
#         session.install("-r", "docs/requirements.txt")
    
#     # Clean previous artifacts
#     if os.path.exists("docs/modules.rst"):
#         os.remove("docs/modules.rst")
#     if os.path.exists("docs/pycomex.rst"):
#         os.remove("docs/pycomex.rst")
#     if os.path.exists("docs/build"):
#         shutil.rmtree("docs/build")
    
#     # Build docs
#     session.run("sphinx-apidoc", "-o", "docs", "pycomex")
#     session.run("sphinx-build", "docs", "docs/build/html")


@nox.session(python="3.10")
def build(session: nox.Session) -> None:
    """Build package and test the wheel using uv."""
    dist_dir = Path("dist")
    
    # Clean old distributions
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
        session.log("Purged dist folder")
    
    # Build package with uv
    session.run("uv", "build", "--python=3.10")
    
    # Test the built wheel
    wheel_files = list(dist_dir.glob("*.whl"))
    if not wheel_files:
        raise FileNotFoundError("No wheel file found in dist/")
    
    wheel_path = wheel_files[0]
    session.log(f"Found wheel: {wheel_path}")
    
    # Test installation and functionality
    session.install(str(wheel_path))
    session.run("python", "-c", "import pycomex; print(f'Installed pycomex {pycomex.__version__}')")
    session.run("pycomex", "--version")


@nox.session(python="3.10")
def changelog(session: nox.Session) -> None:
    """Verify changelog entry exists for current version."""
    _ = session  # Unused but required by nox
    with open("pycomex/VERSION") as file:
        version = file.read().strip()
    
    with open("HISTORY.rst") as file:
        content = file.read()
        if version not in content:
            raise ValueError(f"No changelog entry found for version {version}")


@nox.session(python="3.10")
def clean(session: nox.Session) -> None:
    """Clean build artifacts and cache files."""
    dirs_to_clean: List[Path] = [
        Path("dist"),
        Path("build"),
        Path(".pytest_cache"),
        Path("htmlcov"),
        Path("docs/build"),
    ]
    
    for dir_path in dirs_to_clean:
        if dir_path.exists():
            if dir_path.is_dir():
                shutil.rmtree(dir_path)
            else:
                dir_path.unlink()
            session.log(f"Removed {dir_path}")
    
    # Clean __pycache__ directories recursively
    current_path = Path(".")
    for pycache_dir in current_path.rglob("__pycache__"):
        shutil.rmtree(pycache_dir)
        session.log(f"Removed {pycache_dir}")
