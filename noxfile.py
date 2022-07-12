import os
import shutil
import subprocess
import webbrowser
import tempfile
from typing import List

import nox


def get_requirements() -> List[str]:
    with tempfile.NamedTemporaryFile("w+") as f:
        subprocess.run(
            f"poetry export "
            f"--no-interaction "
            f"--dev "
            f"--format requirements.txt "
            f"--without-hashes "
            f"--output={f.name}",
            check=True,
            shell=True,
        )
        return f.readlines()


def get_wheel_path() -> str:
    for name in os.listdir("dist"):
        path = os.path.join("dist", name)
        if path.endswith(".whl"):
            return path
    else:
        raise FileNotFoundError("The wheel distributional was not correctly created by poetry!")


@nox.session
def test(session: nox.Session) -> None:
    session.run("poetry", "install")
    session.install("pytest")
    session.run("pytest")


@nox.session
def lint(session: nox.Session) -> None:
    session.install("flake8==4.0.1")
    session.run("flake8", "./pycomex/", "./tests/")


@nox.session
def docs(session: nox.Session) -> None:
    # ~ Installing the doc requirements
    #session.run("poetry", "install")
    session.install(".")
    session.install("-r", "docs/requirements.txt")
    session.run("python", "-m", "pycomex.cli", "--version")

    # ~ Removing previous artifacts
    if os.path.exists("docs/modules.rst"):
        os.remove("docs/modules.rst")

    if os.path.exists("docs/pycomex.rst"):
        os.remove("docs/pycomex.rst")

    if os.path.exists("docs/build"):
        shutil.rmtree("docs/build")

    # ~ Building the docs
    session.run("sphinx-apidoc", "-o", "docs", "pycomex")
    session.run("sphinx-build", "docs", "docs/build/html")


@nox.session
def serve_docs(session: nox.Session) -> None:
    url = "docs/build/html/index.html"
    webbrowser.open(url)


@nox.session
def build(session: nox.Session) -> None:
    # ~ Removing old distribution artifacts if they exist
    if os.path.exists("dist"):
        shutil.rmtree("dist")
        session.log("purged dist folder")

    # ~ Invoking poetry to create a new build
    # TODO: Can we do this using the direct python access to poetry?
    session.run("poetry", "build")

    # ~ Testing the build in the nox venv
    # Here we search the dist folder for the path to the wheel distributional which was just created and
    # then we install it into the nox session venv to see it that works and then we also execute the test
    # suite for that.
    wheel_path = None
    for name in os.listdir("dist"):
        path = os.path.join("dist", name)
        if path.endswith(".whl"):
            wheel_path = path
            break
    else:
        raise FileNotFoundError("The wheel distributional was not correctly created by poetry!")

    session.install(wheel_path)
    session.run("python", "-m", "pip", "freeze")
    session.run("python", "-m", "pip", "show", "pycomex")
    # Testing if the package can be imported
    session.run("python", "-m", "pycomex.cli", "--version")


@nox.session
def changelog(session: nox.Session) -> None:
    with open("pycomex/VERSION") as file:
        version = file.read().replace(" ", "").replace("\n", "")

    with open("HISTORY.rst") as file:
        content = file.read()
        if version not in content:
            raise ValueError("No entry to changelog for current version!")
