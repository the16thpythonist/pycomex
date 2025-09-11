import os
import shutil
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pycomex.functional.experiment import Experiment


class ActionableParameterType:
    """
    This is the abstract base class for a special *actionable* kind of type annotation. This kind of
    type annotation is specifically to be used in the context of the parameters of an Experiment module (
    the upper case parameters that are defined in the module's global scope). The idea is that such special
    actionable parameter types can overwrite the default behavior of how the Experiment runtime handles
    these parameter values.

    The main mechanism of this behavior modification is by providing custom implementations of the
    "get" and "set" methods. These will be called whenever the value of a parameter is retrieved from the
    Experiment through the __getattr__ method or modified through the __setattr__ method.
    """

    def __new__(cls, *args, **kwargs):
        raise TypeError(
            f"{cls.__name__} cannot be instantiated; it is intended for "
            f"type annotations only."
        )

    @classmethod
    def get(cls, experiment: "Experiment", value: Any) -> Any:  # noqa
        """
        This method is called by the ``experiment`` runtime, whenever a parameter that is annotated by this
        actionable type is being accessed through the __getattr__ function. Instead of using the ``value`` of the
        parameter directly, the value that is returned by this method will be used.

        By default this will just return the given ``value``.

        This method can be overwritten in subclasses to provide custom behavior.
        """
        return value

    @classmethod
    def set(
        cls,
        experiment: "Experiment",  # noqa
        value: Any,
    ) -> Any:
        """
        This method is called by the ``experiment`` runtime, whenever a parameter that is annotated by this
        actionable type is being modified through the __setattr__ function. Instead of using the ``value`` of the
        parameter directly, the value that is returned by this method will be used.

        By default this will just return the given ``value``.

        This method can be overwritten in subclasses to provide custom behavior.
        """
        return value

    @classmethod
    def on_reproducible(cls, experiment: "Experiment", value: Any) -> Any:  # noqa,
        """
        This method is called at the end of the "finalize_reproducible" method of the ``experiment`` runtime. This
        code is executed after the experiment is finished and the experiment archive folder is being created - but
        only if the experiment was explicitly run in the "reproducible" mode.

        This method provides the opportunity to perform any kind of action that is necessary to store the experiment
        parameter in a reproducible format.
        """
        return value


class CopiedPath(ActionableParameterType):
    """
    This is a special type annotation for file system paths (of either files or folders) that is mainly relevant
    in conjunction with the "reproducible" mode.

    This type can be used to annotate a filesystem path parameter in an experiment module, whose destination
    file/folder should be copied into the experiment archive folder when the experiment is run in the reproducible
    mode. When the experiment is then reproduced in another location, the copied file/folder will be used as a
    fallback instead of using the actual parameter value if that original location does not exist.
    """

    @classmethod
    def on_reproducible(cls, experiment: "Experiment", value: Any) -> Any:  # noqa

        if os.path.exists(value):
            name = os.path.basename(value)
            path = os.path.join(experiment.path, f"{name}.copy")
            if os.path.isfile(value):
                shutil.copyfile(value, path)
            else:
                shutil.copytree(value, path)

        return value

    @classmethod
    def get(cls, experiment: "Experiment", value: Any) -> Any:  # noqa

        if not os.path.exists(value):
            name = os.path.basename(value)
            path = os.path.join(experiment.path, f"{name}.copy")
            return path

        else:
            return value
