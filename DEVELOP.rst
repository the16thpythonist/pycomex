================
Development Help
================

Adding a remote github repository
---------------------------------

Since github removed password authentication it is best to just set up permanent access with the
personal access token like this:

.. code-block:: console

    git remote add origin https:://[username]:[access token]@github.com/[username]/[repo].git

Releasing new version
---------------------

This is a summary of the steps required to release a new version

.. code-block:: console

    poetry lock
    poetry version [ major | minor | patch ]
    poetry build
    poetry publish --username='...' --password='...'
    git commit -a -m "..."
    git push origin master


Bumping Version for a new Release
================================= 

To release a new version of the package, the version string has to be updated throughout all the different 
places where this version string is used in the text. In this project, this is handled automatically 
using the [bump-my-version](https://github.com/callowayproject/bump-my-version) tool, which can be 
installed like this:

.. code-block:: bash

    uv tool install bump-my-version

One of the following commands can then be used to bump the version either for a patch, minor or major release: 

.. code-block:: bash

    bump-my-version bump -v patch
    bump-my-version bump -v minor
    bump-my-version bump -v major

The configuration of which files are being updated and how the version is parsed etc. can be found in a 
tool section of the ``pyproject.toml``


Building a new Package Version
==============================

Before a new version of the package can be published on PyPi for example, the code has to be built first. This 
can be done with uv's ``build`` command like this:

.. code-block:: bash

    uv build --python=3.10

If it doesn't already exist, this command will create a new ``dist`` folder where the built tarball and wheel of 
the current version (as defined in the pyproject.toml file) are saved.


Publishing a new Version to PyPi
================================

[twine](https://twine.readthedocs.io/en/stable/) is a python library that is specifically intended for publishing python 
packages to the package indices such as PyPi. Twine can be installed like this:

.. code-block:: bash

    uv tool install twine

After this the ``twine`` command is available:

.. code-block:: bash

    twine --help

**Checking the distribution. ** Twine assumes that the built distribution files (tarball and wheel) already exist in the 
project's ``dist`` folder (see "Building a New Package Version"). The ``twine check`` command can be used to check 
these distribution files for correctness before actually uploading them. This command will for example check the 
syntax of the README file to make sure it can be properly rendered on the PyPi website.

.. code-block:: bash

    twine check dist/*
    
**Uploading to PyPi. ** Finally, the ``twine upload`` command can be used to actually upload the distribution files 
to the package index.

    twine upload --username='__token__' --password='[your password]' dist/*


Development Environment with Nox
=================================

This project uses `Nox <https://nox.thea.codes/en/stable/>`_ as a task runner for development workflows. 
Nox creates isolated virtual environments for each task and supports running tests across multiple Python 
versions automatically.

Installation
------------

Nox can be installed globally using uv:

.. code-block:: bash

    uv tool install nox

Or with pip:

.. code-block:: bash

    pip install nox

Available Sessions
------------------

The project's ``noxfile.py`` defines several sessions for common development tasks:

**Testing Sessions**

- ``test`` - Run the test suite across all supported Python versions (3.10, 3.11, 3.12)
- ``test_coverage`` - Run tests with coverage reporting (Python 3.10 only)
- ``install_test`` - Test package installation across all Python versions

**Code Quality Sessions**

- ``lint`` - Run code quality checks with ruff and black
- ``format`` - Auto-format code with black and apply ruff fixes

**Build and Documentation Sessions**

- ``build`` - Build the package and test the wheel installation
- ``docs`` - Build documentation with Sphinx
- ``serve_docs`` - Open built documentation in browser

**Utility Sessions**

- ``clean`` - Clean build artifacts and cache files
- ``changelog`` - Verify changelog entry exists for current version

Running Nox Sessions
--------------------

**Run all test sessions:**

.. code-block:: bash

    nox

**Run tests on all Python versions:**

.. code-block:: bash

    nox -s test

**Run tests on a specific Python version:**

.. code-block:: bash

    nox -s test-3.11

**Run tests with coverage:**

.. code-block:: bash

    nox -s test_coverage

**Check code quality:**

.. code-block:: bash

    nox -s lint

**Format code:**

.. code-block:: bash

    nox -s format

**Build package:**

.. code-block:: bash

    nox -s build

**Clean up artifacts:**

.. code-block:: bash

    nox -s clean

**Build documentation:**

.. code-block:: bash

    nox -s docs


Development Workflow
--------------------

A typical development workflow using nox might look like:

1. **Make changes** to the code
2. **Format code**: ``nox -s format``
3. **Run linting**: ``nox -s lint``
4. **Run tests**: ``nox -s test``
5. **Check coverage**: ``nox -s test_coverage``
6. **Build package**: ``nox -s build``

For continuous integration, you can run all sessions:

.. code-block:: bash

    nox

This will execute the default sessions (typically ``test`` and ``lint``).


Documentation
=============

The project documentation is done with "Material for Mkdocs" and hosted on Github Pages.

Starting Development Server
---------------------------

To start the development server for the documentation, the following command can be used:

.. code-block:: bash

    cd docs
    mkdocs serve

This will start a local server that can be accessed at `http://127.0.0.1:8000/`. Any changes made to the documentation 
files will be automatically updated in the browser.