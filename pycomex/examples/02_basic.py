"""
This experiment will repeatedly create a text made of randomly sampled words.

The words are assembled into a text file, which is supposed to be saved as an
artifact of the computational experiment. Additionally, information such as the
total text length / run time of the calculations are to be saved as experiment
metadata.

This module-level doc string will automatically be saved as the description
for this experiment
"""

import os
import random
import tempfile
import textwrap
import urllib.request

from pycomex import Experiment, file_namespace, folder_path

# (1) All variables defined in uppercase are automatically detected as experiment
#     variables and can be overwritten when externally executing the experiment
#     using "run_experiment" for example

# :param NUM_WORDS:
#       The number of words to be generated each time
NUM_WORDS: int = 1000
# :param REPETITIONS:
#       The number of times to repeat the generation process
REPETITIONS: int = 10

__REPRODUCIBLE__: bool = True


# There are some utility functions which simplify the setup of the experiment decorator.
# - folder_path(path: str): This function will return the absolute parent folder path for any given path.
#   In most cases this can be used to supply the base_path relative to the current file
# - file_namespace(path: str): This function will return a namespace string which is structured in the
#   following way: "results/{{ name of file }}"
@Experiment(
    base_path=folder_path(__file__), namespace=file_namespace(__file__), glob=globals()
)
def experiment(e: Experiment):

    e.log("starting experiment...")
    e.log_parameters()

    e.log("downloading word list...")
    response = urllib.request.urlopen("https://www.mit.edu/~ecprice/wordlist.10000")
    WORDS = response.read().decode("utf-8").splitlines()
    # (1) The uppercase "experiment parameters" are stored in the "parameters"
    #     field of the experiment instance. Alternatively the variables can
    #     also just be used directly.
    for i in range(e.parameters["REPETITIONS"]):
        sampled_words = random.sample(WORDS, k=NUM_WORDS)
        text = "\n".join(textwrap.wrap(" ".join(sampled_words), 80))

        # (2) The first option to commit file artifacts to the experiment records
        #     is to use the "open" method directly to get a file manager context
        file_name = f"{i:02d}_random.txt"
        with e.open(file_name, mode="w") as file:
            file.write(text)

        #     Alternatively there are convenience functions that accept various
        #     data types and handle the file creation automatically.
        #     e.commit_fig(file_name, fig) for pyplot figures for example
        e.commit_raw(file_name, text)

        # (3) Simple metadata (strings, numbers) such as various metrics can be
        #     stored to the internal experiment registry by simply indexing the
        #     experiment object. The slash '/' characters automatically define a
        #     nested structure.
        #     If a specific nested structure does not yet exist on assignment,
        #     it is automatically created first
        text_length = len(text)
        e[f"metrics/length/{i}"] = text_length
        # >> e.data['metric']['length']['0'] = text_length

        # (4) The "log" message should be used as an alternative to "print".
        #     These messages will be relayed to a Logger instance, which will
        #     print them to stdout, but also save them to a log file which is
        #     also stored as an experiment artifact.
        e.log(f"saved text file with {text_length} characters")


experiment.run_if_main()
