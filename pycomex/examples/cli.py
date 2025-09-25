import os
import pathlib

from pycomex import ExperimentCLI

PATH = pathlib.Path(__file__).parent.absolute()


if __name__ == "__main__":

    cli = ExperimentCLI(
        name="examples",
        experiments_path=PATH,
        experiments_base_path=os.path.join(PATH, "results"),
        version="0.0.0",
    )

    cli()
