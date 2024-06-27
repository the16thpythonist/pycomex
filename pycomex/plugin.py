import os
from collections import defaultdict


def hook(hook_name: str, priority: int = 0) -> callable:
    
    def decorator(function: callable):
        
        setattr(function, '__hook__', hook_name)
        setattr(function, '__priority__', priority)
        return function

    return decorator


class StopHook(Exception):
    
    def __init__(self, value, *args, **kwargs):
        self.value = value
        super().__init__(*args, **kwargs)


class Plugin:
    
    def __init__(self, config: object, *args, **kwargs):
        self.config = config
        
    def register(self) -> None:
        
        for attribute_name in dir(self):
            attribute = getattr(self, attribute_name)
            if callable(attribute) and hasattr(attribute, '__hook__'):
                function = attribute
                self.config.pm.register_hook(
                    getattr(attribute, '__hook__'), 
                    function,
                    getattr(attribute, '__priority__')
                )
    
    def unregister(self) -> None:
        pass



class PluginManager:
    
    def __init__(self, config: object):
        self.config = config
        self.hooks: dict[str, list[callable]] = defaultdict(list)
        
    def hook(self, hook_name: str, priority: int = 0):
        
        def decorator(function):
            self.register_hook(hook_name, function, priority)
            return function
        
        return decorator
        
    def register_hook(self,
                      hook_name: str,
                      function: callable,
                      priority: int = 0,
                      ) -> None:
        
        # We attach that attribute to the function to mark it as a hook function. This is useful
        # for the autodiscovery of hooks when iterating over the methods of a class for example.
        if not hasattr(function, '__hook__'):
            setattr(function, '__hook__', hook_name)
        
        if not hasattr(function, '__priority__'):
            setattr(function, '__priority__', priority)
        
        # The only thing that we really need to do in the end is to add the function to list of 
        # callables associated with the given name.
        self.hooks[hook_name].append(function)
        
    def apply_hook(self,
                   hook_name: str,
                   **kwargs,
                   ) -> None:
        
        result = None
        for func in sorted(self.hooks[hook_name], key=lambda x: getattr(x, '__priority__'), reverse=True):
            try:
                result = func(self.config, **kwargs)
            except StopHook as stop:
                result = stop.value
                break
            
        return result
    
    def __len__(self) -> int:
        """
        The length of the plugin manager is defined as the total number of hook callables that are 
        currently registered with some hook name.
        """
        return sum([len(hooks) for hook_name, hooks in self.hooks.items()])