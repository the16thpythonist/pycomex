# Plugin Hook System

## Status

Implemented

## Context

The main motivation for this was the recognition of a significant overlap between "Weights and Biases" and the pycomex experimentation framework. In the end, the pycomex archive is an offline version of WandB with a lot of similar features such as artifact tracking, metadata logging, experiment versioning etc. 

Naturally, since pycomex uses a lot of similar syntax even it should be relatively easy to just also send all of this information to wandb. However, this should not be the default - to force the users to also setup wandb if they do not want to use it would be a bad user experience.

Therefore, the idea of a plugin system was born which allows to add plugins to pycomex as needed.

## Decision

The decision was made to implement a plugin system based on the hook pattern. This means that certain parts of the code will call "hooks" at certain points in the execution which are placeholders for code injection. Plugins can then be programmed by registering custom code to be executed in various of these hook places.

## Implementation

[TBD]

## Consequences

### Advantages

**Flexibility.** From a user perspective a plugin system is always great because everyone can pick and choose their own mix of plugins that they need and that makes the whole experience very flexible.

**Extensibility.** A plugin system makes it very easy to extend the functionality of the core framework without having to modify the core codebase itself. This is especially useful for open-source projects where users may want to add their own custom functionality without having to fork the entire project.

### Disadvantages

**Code Complexity and Opacity.** The main disadvantage of a plugin system is that it adds a lot of complexity to the codebase and makes it harder to understand what is actually happening since custom code can be dynamically injected at various points to modify core functionality. This can make debugging and maintenance more difficult since it is not always clear what code is being executed at any given time.