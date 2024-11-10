# Reproducible Mode for Experiments

## Status

Implemented - trying it out

## Context

One of the major challanges related to computational experiments in academia right now is *reproducibility*. A lot of scientific 
research is relying on increasingly complex code and computational analysis. When research is ultimately published in the 
form of a paper, computational results are usually aggregated in a series of figures and tables. These results need to be 
reproducible to be useful for other researchers hoping to build on top of this previous work or to verify the validity of the 
results.

The current state of reproducibility in research is to publish a code repository (e.g. on Github) alongside the paper itself.
Unfortunately, this often leads to significant problems when developers incorrectly specify requirements regarding the operating 
system, hardware, software dependencies or exact versioning. Another possible case is that results in a publication were obtained 
with an early version of a software package that has since been updated and may yield different results or exposes a different 
interface.
Ultimately, too much responsibility is left in the hands of the developers themselves, which results in strongly 
varying levels of reproducibility dependent on the skill of the developers. Ideally, there should exist tooling to improve the 
quality of the reproducibility out of the box.

## Decision

To address this issue, the package introduces the ``reproducible`` mode for experiment modules. This mode is disabled by default and 
has to be explicitly enabled by setting the magic parameter ``__REPRODUCIBLE__=True``. This mode determines how the experiment archive 
folder is finalized after the experiment itself has ended. In this mode, all of the exact versions of the package dependencies are 
pinned and exported to the archive folder. In addition, all *editable* dependencies are built into tarballs using ``uv`` and also 
exported to the archive folder.

Later on, such an experiment can be reproduced by running the ``pycomex reproduce [archive_path]`` command. This will create a new 
virtualenv with the exact reconstruction of the original environment and then run the experiment code that has been copied 
into the ``experiment_code.py`` file anyways.

## Consequences

### Advantages

**Simplicity.** In the absence of special requirements, an experiment that was executed in reproducible mode should work out of the box 
with the ``pycomex reproduce`` command. Saving an experiment in reproducible mode is also as easy as setting a single flag to true. 
Therefore, the only real requirement for reproducibility is to structure the project in such a way that the experiment runs and 
creates an archive folder - which one would do anyways when using pycomex.

### Disadvantages

**Storage.** Depending on the size of the project, the tarball-bundling of the editable installs (which includes at the very least the 
project code itself) may incur a large size for the experiment archive folder. Since this is repeated for every experiment to be exported, 
one would have to be careful how to structure the experiments to reduce the storage requirement here. For example, a sweep experiment should 
somehow be bundled into a single experiment instead of individual experiment runs with different parameters.

**Python only.** Without further considerations, this method will only work *well* with projects that rely on python-only dependencies - 
aka packages that can be installed via pip. If the experiment additionally uses some third-party binary such as turbomole for DFT 
calculations, this is currently not covered.

### Potential Problems

**Scripters.** One core assumption of the reproducible experiment mode is that all of the imported functionality is in the form of 
a package - aka no *local*/*relative* imports. The reproducible mode will be able to reconstruct external package dependencies that 
can be installed via pip and also take care of packages installed locally in *editable* mode. However, currently there is no 
automatic way to handle if relative imports have been used - when some module imports another module directly in the same folder 
for example. However, this may very well happen with researchers mostly used to scripting and unaware of best practices.