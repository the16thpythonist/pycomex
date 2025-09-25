"""
This example demonstrates the caching functionality of PyComex experiments.

The caching system allows expensive computations to be stored and reused across 
experiment runs. This is particularly useful for computationally intensive operations
that don't need to be repeated every time an experiment is executed.

The cache is scoped to prevent conflicts between different experiments and can be
configured with specific names and scopes for fine-grained control.
"""

import time

import numpy as np

from pycomex import Experiment, file_namespace, folder_path

# Create the experiment with standard configuration using utility functions
# - folder_path(__file__): Gets the parent directory of this script as base path
# - file_namespace(__file__): Creates namespace "results/10_caching" from filename
experiment = Experiment(
    base_path=folder_path(__file__),
    namespace=file_namespace(__file__),
    glob=globals(),
)


@experiment
def experiment(e: Experiment):

    e.log(f"starting experiment with namespace {e.namespace}")

    # (1) The @e.cache.cached decorator enables caching for expensive computations
    #     - name: unique identifier for this cached function
    #     - scope: tuple defining cache scope - prevents conflicts between experiments
    #     On first run, the function executes and result is stored in cache.
    #     Subsequent runs load the cached result instead of recomputing.
    @e.cache.cached(name="heavy_computation", scope=("10_caching",))
    def heavy_computation():
        # Use fixed random seed for reproducible results
        rng = np.random.default_rng(42)
        A = rng.standard_normal((100, 100))

        # Heavy-ish computation: repeated matrix multiplications
        # This simulates an expensive operation that benefits from caching
        B = A.copy()
        for _ in range(30):
            B = B @ A.T  # Matrix multiplication with transpose

        # (2) Perform various linear algebra computations on the matrices
        #     These operations are computationally expensive and perfect for caching
        eigvals = np.linalg.eigvalsh(B)  # Eigenvalues (Hermitian/symmetric)
        u, s, vh = np.linalg.svd(A, full_matrices=False)  # Singular Value Decomposition

        # Stable determinant computation to avoid numerical overflow
        sign, logdet = np.linalg.slogdet(B)

        # (3) Return a compact summary instead of large matrices
        #     This keeps the cache size manageable while preserving key results
        return {
            "matrix_shape": A.shape,
            "trace_B": float(np.trace(B)),
            "eigvals_top5": eigvals[::-1][:5].tolist(),  # Top 5 eigenvalues
            "singular_values_top5": s[:5].tolist(),  # Top 5 singular values
            "logdet_B": float(logdet),
            "sign_B": int(sign),
        }

    # (4) Time the execution to demonstrate caching performance benefits
    #     First run will be slow (computation happens), subsequent runs fast (cached)
    time_start = time.time()
    result = heavy_computation()
    time_end = time.time()

    # (5) Log the execution time - compare first run vs cached runs
    e.log(f"Computation time: {time_end - time_start:.5f} seconds")

    # (6) Store the computation results in experiment data for analysis
    e["results/computation"] = result
    e.log(
        f'Matrix computation completed. Shape: {result["matrix_shape"]}, Trace: {result["trace_B"]:.6f}'
    )


# (7) Execute the experiment only when this script is run directly
#     This allows the module to be imported without triggering execution
#     Run this example multiple times to see the caching effect:
#     - First run: slow (computation executes)
#     - Subsequent runs: fast (cached result loaded)
experiment.run_if_main()
