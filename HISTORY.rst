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

0.2.0 (2022-07-12)
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

0.2.1 (2022-07-12)
------------------

* Now it is possible to commit matplotlib Figures directly to the experiment with ``Experiment.commit_fig``
* File artifact paths are now automatically tracked as metadata
* Added a default template ``annotations.rst`` to be rendered for each experiment which provides a
  boilerplate starting point for additional thoughts to be added

0.3.0 (2022-07-17)
------------------

* Added ``Experiment.commit_json`` to directly store dict data as json file artifacts for the experiment
  records
* Improved the ``analysis.py`` templating for experiments
    * Using the context manager ``Experiment.analysis`` within the experiment file can be used to not only
      directly execute the analysis right after the experiment is completed but also all the code within
      that context managers content block is copied into the analysis template of that run and it will
      work as it is
    * This is due to the fact, that ``Experiment`` now automatically realizes if it is being imported
      from a ``snapshot.py`` within an existing record folder. In that case it populates internal fields
      such as ``Experiment.data`` by loading the persistent file artifact.
* Added ``examples/analysis.py`` which documents / explains the previously mentioned process
