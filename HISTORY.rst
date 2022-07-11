=======
History
=======

0.1.0 (2022-07-09)
------------------

* First release on PyPI.

0.1.1 (2022-07-11)
------------------

* Added the "poetry_bumpversion" plugin https://github.com/monim67/poetry-bumpversion to update the version
  strings in all the relevant files
* Using "black" for code formatting
* Using "flake9" for linting

0.2.0 (2022-07-11)
------------------

* Every experiment file now has a command line interface realized with ``argparse``
    * It is possible to pass in either a .JSON or a .PY file which are able to modify the default
      experiment parameters defined in the experiment file
    * It is possible to retrieve the destination path when invoking an experiment file over the command line
* A copy of the actual experiment file is copied as a snapshot to the experiment record folder
* It is possible to define additional jinja templates which are rendered as additional files into the
  experiment record folder
    * One default template which is rendered this way is "analysis.py" module, which provides a boilerplate
      starting point for further analysis on the experiment results.
