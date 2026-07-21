"""
Distributed (multi-process) execution support for PyComex experiments.

When an experiment is launched with a distributed launcher such as PyTorch's ``torchrun``
(used for ``DistributedDataParallel`` training), the *same* experiment module is executed
once per worker process. Each of these processes receives the environment variables
``RANK`` (its global rank in ``0..WORLD_SIZE-1``) and ``WORLD_SIZE`` (the total number of
processes).

Only the *primary* process (global rank 0) should produce the experiment archive and all
of its side effects (folder creation, logging to file, metadata, notifications, ...). The
remaining *worker* processes still execute the experiment body -- they have to, because
they participate in the gradient synchronization -- but they must not create any archival
artifacts, otherwise every run would produce ``WORLD_SIZE`` duplicate archives.

Design rationale:
    This module is intentionally tiny and dependency-free. In particular it does NOT
    import ``torch``: the distributed context is derived purely from the environment
    variables that the launcher sets, which keeps PyComex agnostic of the training
    framework and avoids a heavy optional dependency.
"""

import functools
import os
from dataclasses import dataclass


@dataclass
class DistributedContext:
    """
    Describes the distributed execution context of a single experiment process.

    A "primary, single-process" context (``rank=0``, ``world_size=1``) is the default for
    ordinary, non-distributed runs and results in the completely unchanged, full
    experiment behavior.

    :param rank: The global rank of the current process. ``0`` for the primary process
        and for ordinary single-process runs.
    :param world_size: The total number of processes participating in the distributed
        group. ``1`` for ordinary single-process runs.
    """

    rank: int
    world_size: int

    @property
    def is_primary(self) -> bool:
        """
        Whether the current process is the primary process (global rank 0).

        The primary process is the single process responsible for creating the experiment
        archive and performing all of its side effects.

        :returns: True if this is the primary process.
        """
        return self.rank == 0

    @property
    def is_distributed(self) -> bool:
        """
        Whether the experiment runs in a distributed context (more than one process).

        :returns: True if ``world_size`` is greater than 1.
        """
        return self.world_size > 1


def detect_distributed_context(mode: bool | str = "auto") -> DistributedContext:
    """
    Detect the distributed execution context from the environment.

    The detection is based on the ``RANK`` and ``WORLD_SIZE`` environment variables which
    are set by PyTorch's ``torchrun`` launcher (and compatible launchers). ``torch`` is
    never imported, so this works regardless of the training framework.

    Example:

    .. code-block:: python

        # Under `torchrun --nproc_per_node=4 experiment.py`, worker 2 sees:
        #   RANK=2, WORLD_SIZE=4
        context = detect_distributed_context()
        context.rank          # 2
        context.world_size    # 4
        context.is_primary    # False

    :param mode: Controls the detection behavior:
        - ``"auto"`` (default) or ``True``: read ``RANK`` / ``WORLD_SIZE`` from the
          environment. When they are unset (the common non-distributed case) this yields a
          primary, single-process context.
        - ``False``: force a primary, single-process context, ignoring the environment.
          This is an escape hatch for the rare case that ``RANK`` / ``WORLD_SIZE`` happen
          to be present in the environment for unrelated reasons.

    :returns: The detected :class:`DistributedContext`.
    """
    if mode is False:
        return DistributedContext(rank=0, world_size=1)

    rank = int(os.environ.get("RANK", 0))
    world_size = int(os.environ.get("WORLD_SIZE", 1))
    return DistributedContext(rank=rank, world_size=world_size)


def primary_only(method):
    """
    Decorator that turns an :class:`Experiment` method into a no-op on non-primary
    (worker) processes.

    This is used to gate all *archival* methods -- those that write to the experiment
    archive folder (``save_*``, ``commit_*``, ``track``, ...). On the primary process
    (global rank 0) the method executes normally; on any worker process it returns
    ``None`` immediately without any side effect.

    Using a declarative decorator (rather than an inline ``if self.is_primary`` guard in
    every method body) keeps the persistence layer readable and makes it obvious at a
    glance which methods are archival.

    The decorated object is expected to expose a boolean ``is_primary`` attribute.

    :param method: The instance method to guard.

    :returns: The wrapped method.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not getattr(self, "is_primary", True):
            return None
        return method(self, *args, **kwargs)

    return wrapper
