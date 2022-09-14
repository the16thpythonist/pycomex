#! /usr/bin/env python3
"""
This experiment will repeatedly create a text made of randomly sampled words.
The words are assembled into a text file, which is supposed to be saved as an
artifact of the computational experiment. Additionally, information such as the
total text length / run time of the calculations are to be saved as experiment
metadata.

This is the same experiment content, which is also featured in the "basic.py"
example.
"""
import tempfile
import random
import textwrap
import urllib.request

from pycomex.experiment import Experiment
from pycomex.util import Skippable

response = urllib.request.urlopen("https://www.mit.edu/~ecprice/wordlist.10000")

WORDS = response.read().decode("utf-8").splitlines()
NUM_WORDS = 1000
REPETITIONS = 10

with Skippable(), (e := Experiment(base_path=tempfile.gettempdir(),
                                   namespace="example/analysis", glob=globals())):
    e.work = REPETITIONS

    for i in range(e.parameters["REPETITIONS"]):
        sampled_words = random.sample(WORDS, k=NUM_WORDS)
        text = "\n".join(textwrap.wrap(" ".join(sampled_words), 80))
        e.commit_raw(f"{i:02d}_random.txt", text)

        text_length = len(text)
        e[f"metrics/length/{i}"] = text_length
        e.info(f"saved text file with {text_length} characters")

        e.update()

    # ~ post-experiment analysis
    # Suppose we want to conduct some sort of analysis on the results of the completed
    # experiment. in this case we want to find the texts with the min and max number
    # of characters. We also want to find out the average value for the
    # character count. We then store this information as additional character count.

print(e)
# ALl of the code defined within this "Experiment.analyis" context manager will be
# copied to the analyis.py template of the record folder of this experiment run and
# it will work as it is.
# NOTE: As long as the analysis code is only using experiment data or experiment
#       variables
with Skippable(), e.analysis:
    # (1) Note how the experiment path will be dynamically determined to be a *new*
    #     folder when actually executing the experiment, but it will refer to the
    #     already existing experiment record folder when imported from
    #     "snapshot.py"
    print(e.path)
    e.info('Starting analysis of experiment results')

    index_min, count_min = min(e['metrics/length'].items(),
                               key=lambda item: item[1])
    index_max, count_max = max(e['metrics/length'].items(),
                               key=lambda item: item[1])
    count_mean = sum(e['metrics/length'].values()) / len(e['metrics/length'])

    analysis_results = {
        'index_min': index_min,
        'count_min': count_min,
        'index_max': index_max,
        'count_max': count_max,
        'count_mean': count_mean
    }
    # (2) Committing new files to the already existing experiment record folder will
    #     also work as usual, whether executed here directly or later in "analysis.py"
    e.commit_json('analysis_results.json', analysis_results)
