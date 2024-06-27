#! /usr/bin/env python3
import os
import json
import pathlib
from pprint import pprint
from typing import Dict, Any

# Useful imports for conducting analysis
import numpy as np
import matplotlib.pyplot as plt

# Importing the experiment
from snapshot import *

# List of experiment parameters
# - NUM_WORDS
# - REPETITIONS

PATH = pathlib.Path(__file__).parent.absolute()
DATA_PATH = os.path.join(PATH, 'experiment_data.json')
# Load the all raw data of the experiment
with open(DATA_PATH, mode='r') as json_file:
    DATA: Dict[str, Any] = json.load(json_file)


if __name__ == '__main__':
    print('RAW DATA KEYS:')
    pprint(list(DATA.keys()))

    # The analysis template from the experiment file
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