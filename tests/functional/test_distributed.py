"""
Tests for distributed (DDP-style) execution of PyComex experiments.

BACKGROUND:
===========

PyTorch's ``DistributedDataParallel`` is typically launched via ``torchrun``, which
starts one independent OS process *per worker*, each executing the experiment module
top-to-bottom. Each process receives the environment variables ``RANK`` (its global
rank, 0..WORLD_SIZE-1) and ``WORLD_SIZE`` (the total number of processes).

Because every one of these processes runs the full experiment, a naive PyComex
experiment would create ``WORLD_SIZE`` archive folders (one per rank), duplicate all
logs and metadata, and fire ``WORLD_SIZE`` notifications -- when the user wants exactly
*one* archive, produced by the primary process (rank 0). The non-primary ranks must
still run the experiment body (they participate in the gradient synchronization) but
must not produce any archival side effects.

The test below reproduces the real launch scenario by forking ``WORLD_SIZE`` processes,
each setting its own ``RANK`` / ``WORLD_SIZE`` (exactly like ``torchrun``), all pointing
at the same base path and namespace. It then asserts that exactly ONE archive folder is
created. Until the DDP fix lands this test is EXPECTED TO FAIL (it will find one folder
per rank), which is precisely what confirms the problem.
"""

import os


def _ddp_experiment_worker(
    base_path: str, namespace: str, rank: int, world_size: int, queue
) -> None:
    """
    Worker executed inside a forked child process. It emulates a single ``torchrun``
    worker: it sets the ``RANK`` / ``WORLD_SIZE`` environment variables for its own
    process and then runs a minimal experiment pointed at the shared archive location.

    The result (the archive path the experiment ended up with, or the exception) is
    reported back through the ``queue``.

    :param base_path: The shared base path for the experiment archive.
    :param namespace: The shared namespace under which the archive is created.
    :param rank: The global rank this worker should assume (0 == primary process).
    :param world_size: The total number of processes in the distributed group.
    :param queue: A multiprocessing queue to report the result back to the parent.

    :returns: None
    """
    # This is exactly what torchrun does for each launched worker process.
    os.environ["RANK"] = str(rank)
    os.environ["WORLD_SIZE"] = str(world_size)

    try:
        from pycomex.functional.experiment import Experiment

        experiment = Experiment(
            base_path=base_path,
            namespace=namespace,
            # A minimal glob is enough; __file__ just has to point at a readable python
            # module for read_module_metadata() / save_code().
            glob={"__file__": __file__, "__doc__": None},
            debug=False,
        )

        @experiment
        def run(e):
            e["result"] = rank
            e.log(f"worker with rank {rank} is running the experiment body")

        experiment.run()
        queue.put((rank, "ok", experiment.path))
    except Exception as exc:
        queue.put((rank, "error", f"{type(exc).__name__}: {exc}"))


class TestDistributedDataParallel:
    """
    Tests that a PyComex experiment launched as multiple distributed workers (as done by
    ``torchrun`` for PyTorch DDP) produces exactly one archive folder, created by the
    primary process (rank 0), while the non-primary ranks produce no archival side
    effects.
    """

    def test_ddp_creates_single_archive_folder(self, tmp_path):
        """
        Launching an experiment as ``WORLD_SIZE`` distributed workers (each with its own
        ``RANK``) must create exactly ONE archive folder -- the one belonging to rank 0.
        """
        import multiprocessing as mp

        world_size = 3
        namespace = "ddp_test"
        base_path = str(tmp_path)

        ctx = mp.get_context("fork")
        queue = ctx.Queue()
        processes = [
            ctx.Process(
                target=_ddp_experiment_worker,
                args=(base_path, namespace, rank, world_size, queue),
            )
            for rank in range(world_size)
        ]

        for process in processes:
            process.start()

        # Drain the queue BEFORE joining to avoid a deadlock on a full pipe.
        results = [queue.get() for _ in range(world_size)]

        for process in processes:
            process.join()

        # Any hard crash in a worker is a failure regardless of the folder count.
        errors = [r for r in results if r[1] == "error"]
        assert not errors, f"Distributed workers crashed: {errors}"

        # Count the archive folders that actually ended up on disk. Only the primary
        # process (rank 0) is supposed to have created one.
        namespace_dir = os.path.join(base_path, namespace)
        created_folders = (
            sorted(os.listdir(namespace_dir)) if os.path.isdir(namespace_dir) else []
        )

        assert len(created_folders) == 1, (
            f"Expected exactly ONE archive folder (created by rank 0) but found "
            f"{len(created_folders)}: {created_folders}. Each distributed worker created "
            f"its own archive instead of only the primary process. results={results}"
        )


class TestDistributedContextDetection:
    """
    Unit tests for the environment-based distributed context detection.
    """

    def test_no_env_is_primary_single_process(self, monkeypatch):
        """Without RANK / WORLD_SIZE the context is a primary, single-process one."""
        from pycomex.functional.distributed import detect_distributed_context

        monkeypatch.delenv("RANK", raising=False)
        monkeypatch.delenv("WORLD_SIZE", raising=False)

        context = detect_distributed_context("auto")
        assert context.rank == 0
        assert context.world_size == 1
        assert context.is_primary is True
        assert context.is_distributed is False

    def test_env_worker_is_detected(self, monkeypatch):
        """RANK / WORLD_SIZE (as set by torchrun) yield the corresponding context."""
        from pycomex.functional.distributed import detect_distributed_context

        monkeypatch.setenv("RANK", "2")
        monkeypatch.setenv("WORLD_SIZE", "4")

        context = detect_distributed_context("auto")
        assert context.rank == 2
        assert context.world_size == 4
        assert context.is_primary is False
        assert context.is_distributed is True

    def test_ddp_false_forces_primary(self, monkeypatch):
        """ddp=False is an escape hatch that ignores the environment."""
        from pycomex.functional.distributed import detect_distributed_context

        monkeypatch.setenv("RANK", "3")
        monkeypatch.setenv("WORLD_SIZE", "8")

        context = detect_distributed_context(False)
        assert context.rank == 0
        assert context.world_size == 1
        assert context.is_primary is True


class TestWorkerBehavior:
    """
    Tests for the in-process behavior of a single non-primary (worker) experiment.
    """

    def test_worker_creates_no_archive_and_persistence_is_noop(self, monkeypatch):
        """
        A worker (rank > 0) must run the experiment body without creating an archive
        folder, without crashing on persistence calls, while keeping in-memory storage
        functional.
        """
        import sys

        from pycomex.functional.experiment import Experiment
        from pycomex.testing import ConfigIsolation, ExperimentIsolation

        monkeypatch.setenv("RANK", "1")
        monkeypatch.setenv("WORLD_SIZE", "2")

        with ConfigIsolation(), ExperimentIsolation(sys.argv) as iso:
            experiment = Experiment(
                base_path=iso.path,
                namespace="worker_ns",
                glob=iso.glob,
                debug=False,
            )

            @experiment
            def run(e):
                # In-memory storage must keep working on a worker...
                e["result"] = 123
                # ...while all archival persistence must be a silent no-op (no crash even
                # though there is no archive folder / self.path is None).
                e.track("metric", 0.5)
                e.commit_raw("artifact.txt", "content")
                with e.open("out.txt", mode="w") as file:
                    file.write("discarded")

            experiment.run()

            # The distributed context is reflected on the experiment object.
            assert experiment.is_primary is False
            assert experiment.rank == 1
            assert experiment.world_size == 2

            # No archive folder was created and self.path stayed None.
            assert experiment.path is None
            namespace_dir = os.path.join(iso.path, "worker_ns")
            assert not os.path.isdir(namespace_dir) or os.listdir(namespace_dir) == []

            # In-memory storage still works.
            assert experiment["result"] == 123
