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


NUM_WORDS = 1000
REPETITIONS = 10

with Skippable(), (e := Experiment(base_path=tempfile.gettempdir(),
                                   namespace="example/analysis", glob=globals())):

    response = urllib.request.urlopen("https://www.mit.edu/~ecprice/wordlist.10000")
    WORDS = response.read().decode("utf-8").splitlines()

    # With the "apply_hook" method it is possible to define special points
    # during the main experiment runtime, where custom code of child experiments
    # (which inherit from - and extend upon - this experiment) can be
    # injected / executed. This will be further explained in later examples.
    # Using the "default" argument defines a filter hook, where custom code
    # of child experiments is able to modify the value of the WORDS variable
    WORDS = e.apply_hook('filter_words', words=WORDS, default=WORDS)

    for i in range(e.parameters["REPETITIONS"]):
        sampled_words = random.sample(WORDS, k=NUM_WORDS)
        text = "\n".join(textwrap.wrap(" ".join(sampled_words), 80))
        e.commit_raw(f"{i:02d}_random.txt", text)

        text_length = len(text)
        e[f"metrics/length/{i}"] = text_length
        e.info(f"saved text file with {text_length} characters")

    # This is a simple action hook, where custom code can be executed to
    # potentially add more functionality to the end of the experiment.
    e.apply_hook('after_experiment')


# ~ post-experiment analysis
# Suppose we want to conduct some sort of analysis on the results of the completed
# experiment. in this case we want to find the texts with the min and max number
# of characters. We also want to find out the average value for the
# character count. We then store this information as additional character count.

# All of the code defined within this "Experiment.analyis" context manager will be
# copied to the "analyis.py" template inside the archive folder of this experiment
# and that code will work as it is...
# NOTE: ... As long as the analysis code defined here only accesses global variables
#       or data that has been previously committed to the experiment instance via
#       the indexing operation (e.g data['values'])
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
