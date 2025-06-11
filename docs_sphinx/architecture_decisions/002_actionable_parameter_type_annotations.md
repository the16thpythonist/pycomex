# Actionable Parameter Type Annotations

## Status

Implemented

## Context

The primary motivation for this choice came as a side effect of the "reproducible" experiment mode. In this mode, the dependencies of
an experiment module are packaged into the experiment archive folder alongside the experiment artifacts. Later on, an experiment that 
has been exported in this reproducible mode should then be able to simply be repeated using the ``pycomex reproduce [archive_path]``
command.

One problem that occurs with this method is that experiments often have file path parameters that point to certain external files or 
folders that are needed for the experiment. For some of these cases it is justified to expect that whoever does the replication also 
obtains these files and supplies a corresponding parameter overwrite for their local filesystem structure. However, for other file 
assets one might not want to do this, but rather package files as part of the archive in case of a reproduction. This can mainly 
be the case for smaller CSV files, config files etc. However, in the current form of the package, these paths would break and the 
reproducer would have to supply all of these files.

## Decision

The main motivation was to find an elegant solution for the aforementioned problem. From the outside this problem can now be addressed 
by simply changing the type annotation of the corresponding path experiment parameters:

```python
from pycomex.functional.parameter import CopiedPath

CSV_PATH: CopiedPath = "/home/jonas/local/path/to/file.csv"
```

When using this type annotation and running an experiment in reproducible mode, the file/folder in question will be copied into the 
experiment archive folder. When the experiment is executed and the exact path cannot be found on the local system, it will use the 
version that is in the archive folder.

Practically this is implemented by having ``CopiedPath`` be a subclass of the ``ActionableParameterType`` interface which implements 
special methods such as "get" and "set" which overwrite the behavior whenever parameters are accessed within the Experiment object.

## Consequences

### Advantages

**Simplicity.** Achieving the copying behavior in the reproducible scenario is as easy as changing the type annotation and all of the 
desired functionality is done in the background without the user itself having to worry about it.

**Extendability.** Beside, the use case of the reproducible mode, the ActionableParameterType interface provides a very generic 
way to implemenet other magic parameter behavior in the future.


### Disadvantages

**Complex Implicit Behavior.** Sometimes, implicit behavior can also be hard to grasp and it can be hard to debug interactions when one 
isn't aware of implicit behavior like this. On the development side this also introduced another layer of complexity/division when 
accessing the experiment parameters.