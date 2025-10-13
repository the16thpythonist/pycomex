# Functional Decorator Interface

## Status

implemented

## Context

During the inception of the pycomex package, the experimentation framework was working quite a bit differently. The whole idea of the experiment module was based on *context manager* which meant that a script was looking something like this:

```python

from pycomex import Experiment

with Experiment(base_path='results', namespace='exp') as exp:
    # do stuff actual experiment stuff
    exp.log(...)

```

This choice was initially made to allow for a more "clean" syntax, where the user would not have to worry about calling `exp.start()` or something like this. However, this approach turned out to be much more difficult on the implementation side of things because it was for instance very difficult to somehow access the content of that context manager from outside the context manager itself. This made it for instance very hard to implement experiment extension or after-the-fact importing of experiments without having to run the experiment code again.

## Decision

Therefore the decision was made to switch to a functional interface where the user decorates a function with `@Experiment(...)` and then calls that function to run the experiment. This makes it much easier to access the experiment object from outside the function and therefore allows for more flexible usage patterns. Additionally, this method comes with all the advantages of wrapping code within a function which makes it much easier to inspect about the code flow and the scope of variables etc.

So now the typical experiment code looks like this:

```python
from pycomex import Experiment

@Experiment(
    base_path="results",
    namespace="exp",
    glob=globals()
)
def main(exp: Experiment):
    # do stuff actual experiment stuff
    exp.log(...)

exp.run_if_main()
```

This now required slightly more boilerplate code but this is a small price to pay for the increased flexibility and usability of the framework especially when implementing more advanced features.

## Consequences

### Advantages

**Easier backend implementation.** The backend implementation of the experiment framework got significantly easier because the experiment object is now easily accessible from outside the function scope and that there are pre-built inspection mechanisms etc for functions.

### Disadvantages

**Boilerplate/less intuitive.** The core boilerplate for setting up a new experiment module got slightly more complicated and less intuitive which means that users may be more reluctant to adopt it if is perceived as too complicated or that certain crucial parts my be forgotten.