===========================
📖 Additional Documentation
===========================

This file provides some additional documentation on some key aspects of the framework, which were not essential enough
to be discussed in the ``README.rst`` directly.

========
🪝 Hooks
========

This section lists all the hooks which are additionally exposed by the ``Experiment`` class' internal life 
cycle and which users may also utilize to achieve more targeted custom effects.

Such an internal hook my be defined in the same manner as a user-defined one, simply by using it's unique 
string identifier with the ``Experiment.hook`` decorator method like this:

.. code-block:: python

    from pycomex.functional.experiment import Experiment

    experiment = Experiment.extend(
        'some experiment',
        # ...
    )

    @experiment.hook('before_execute')
    def before_execute(e: Experiment):
        e.log('This code is executed right before the experiment itself!')


    experiment.run_if_main()


List of available hooks, together with a list of their supplied arguments

* ``before_run``- (Experiment, ) - Is executed right before the actual function implementation of the experiment
* ``after_run`` - (Experiment, ) - Is executed right after the actual function implementation of the experiment. Note that this 
  hook is only executed if the experiment does not encounter an error during it's runtime.
