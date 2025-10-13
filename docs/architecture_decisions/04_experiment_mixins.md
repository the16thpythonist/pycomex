# Plugin Hook System

## Status

Planning

## Context

Currently, the pycomex package already allows for experiment inheritance were one experiment can extend another experiment and for example inject custom code into the execution of the base experiment using hooks. However, sometimes it is also necessary that a certain hook is implemented for two sub experiments. But perhaps they include the same hook. Currently, this would require to duplicate the code for the hook implementation for the two sub experiments.

## Decision

To address this problem, it would make sense to implement a mixin system where there could be an experiment mixin module which implements the generic override of that hook without being executable by itself. Then the two sub experiments could both extend the base experiment and also include the mixin module to get the hook implementation and reuse the code.

This should be implemented in a ``ExperimentMixin`` class and in general defining a mixin module should be very similar to defining a regular experiment module. The only difference is that the mixin module cannot be executed by itself and does not define its own experiment namespace or base path. Instead, it is always used in conjunction with a regular experiment module.

```python
# experiment_mixin.py
from pycomex import ExperimentMixin

experiment = ExperimentMixin()

experiment.hook(...)
def hook_implementation(...):
    ...
```

Then it should be possible not only to extend a base experiment but also to include one or more mixin modules.

```python
# sub_experiment.py
from pycomex import Experiment

experiment = Experiment.extend(
    'base_experiment.py',
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)
experiment.include('experiment_mixin.py')

#...
```

The same should also work for experiment yaml files like this:

```yaml
# sub_experiment.yml
extend: base_experiment.py
include: experiment_mixin.py
parameters:
    ...
```