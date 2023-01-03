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
import tempfile
import random
import textwrap
import urllib.request

from pycomex.experiment import Experiment
from pycomex.util import Skippable

# (1) All variables defined in uppercase are automatically detected as experiment
#     variables and can be overwritten when externally executing the experiment
#     using "run_experiment" for example
NUM_WORDS = 1000
REPETITIONS = 10
SHORT_DESCRIPTION = 'An example experiment, which shows all the basic features of the library'

with Skippable(), (e := Experiment(base_path=tempfile.gettempdir(),
                                   namespace="example/basic", glob=globals())):

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

        # (4) The "info" message should be used as an alternative to "print".
        #     These messages will be relayed to a Logger instance, which will
        #     print them to stdout, but also save them to a log file which is
        #     also stored as an experiment artifact.
        e.info(f"saved text file with {text_length} characters")

# The metadata is saved to an actual json file upon the content manager __exit__'s
if os.path.exists(e.path):
    print(f"\n FILES IN EXPERIMENT FOLDER: {e.path}")
    for path in sorted(os.listdir(e.path)):
        print(os.path.basename(path))
