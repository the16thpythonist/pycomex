# Experiment Mixins

## Status

Implemented

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

## Implementation

The mixin system was implemented through the `ExperimentMixin` class in `pycomex/functional/mixin.py`, which inherits from `ExperimentBase` alongside the `Experiment` class. Mixins use `replace=False` as the default for hook registration, ensuring hooks append rather than replace existing ones. When included via `experiment.include()`, mixin hooks are merged into the experiment's hook map while preserving execution order (base → mixin → experiment). Mixin parameters act as fallback defaults that are only used if not defined in the experiment itself. The system also supports YAML configuration files through the `include` field in experiment config files, allowing both single mixins (`include: mixin.py`) and multiple mixins (`include: [mixin1.py, mixin2.py]`).

## Consequences

### Advantages

**Code Reusability.** Mixins eliminate code duplication by allowing common hook implementations to be defined once and reused across multiple experiments. This is particularly valuable for standardized behaviors like logging, validation, or notifications that need to be consistent across different research projects.

**Composability.** Multiple mixins can be combined in a single experiment, enabling modular composition of functionality. Experiments can selectively include only the mixins they need, avoiding the "God object" anti-pattern where everything is bundled together.

**Consistency.** Mixins promote consistent behavior across experiments by centralizing common functionality. When a change is needed to shared behavior, it only needs to be updated in the mixin rather than in every experiment that uses it.

### Disadvantages

**Additional Abstraction Layer.** Mixins add another level of abstraction to the experiment system, which can make it harder for new users to understand where functionality comes from. Code that executes in an experiment may originate from the base experiment, one or more mixins, or the experiment itself.

**Hook Execution Complexity.** The execution order of hooks becomes more complex with mixins, following the pattern: base experiment → mixin 1 → mixin 2 → current experiment. While this order is deterministic, it can be non-obvious to users and may require careful documentation and debugging when hooks interact in unexpected ways.