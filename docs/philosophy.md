# Philosophy

## Introduction

PyComex was born from the recognition that computational experiments, while fundamental to scientific computing and data science, are often conducted in an ad-hoc manner that leads to reproducibility issues, lost results, and inefficient workflows. The framework embodies a philosophy of **structured experimentation** where every computational experiment is treated as a first-class citizen with its own identity, metadata, and lifecycle.

At its core, PyComex believes that experiments should be **self-documenting**, **reproducible**, and **easily analyzable**. Rather than scattering experiment scripts across directories with inconsistent naming and organization, PyComex provides a systematic approach that captures not just the code, but the complete experimental context including parameters, outputs, intermediate results, and analysis artifacts.

## Solving Common Experimental Challenges

### Asset Management

One of the most pervasive problems in computational experimentation is the chaos of asset management. Researchers and data scientists often find themselves with directories full of scattered files: input data here, output plots there, model checkpoints somewhere else, and configuration files everywhere. This fragmentation makes it nearly impossible to understand what belongs to which experiment, leading to lost work and irreproducible results.

PyComex solves this through **automatic experiment archiving**. Every experiment execution creates a self-contained directory structure with a timestamp and namespace, ensuring that all assets—input files, generated outputs, plots, logs, and metadata—are co-located and properly organized. The framework automatically captures the experiment's state, including the exact code version, parameter values, and execution environment, creating a complete experimental record that can be revisited months or years later.

This systematic organization means that finding the results from "that experiment I ran last Tuesday" becomes trivial rather than a archaeological expedition through your file system.

### Experiment Deviations and Evolution

Real experimental work rarely follows a linear path. You start with one set of parameters, realize you need to test a variation, want to override a single value for a quick test, or need to inject custom behavior through hooks. Traditional approaches often lead to copying and modifying entire scripts, creating a branching nightmare of slightly different versions that become impossible to track.

PyComex embraces this reality through **inheritance and hook systems**. The framework allows experiments to inherit from base configurations while overriding specific parameters, creating clear lineages of experimental evolution. Hook systems enable you to inject custom behavior—like specialized logging, notifications, or data preprocessing—without modifying the core experiment logic.

This approach means you can maintain a clean experimental history while supporting the natural branching and variation that real research requires. Every experiment knows its lineage and deviations, making it easy to understand how results evolved over time.

### Quantity Tracking and Data Persistence

Computational experiments generate vast amounts of intermediate data: metrics during training, intermediate results, diagnostic information, and final outputs. Managing this information typically involves manual bookkeeping with inconsistent formats, making it difficult to compare results across experiments or perform meta-analyses.

PyComex provides structured **quantity tracking** through the `.track()` method that makes storing evolving parameters and artifacts effortless. The framework automatically compiles tracked data over time, creating comprehensive records of how values change throughout an experiment's execution. This goes far beyond simple logging—PyComex automatically generates visualizations of your tracked data, creating plots for numerical values and videos from sequences of tracked images.

The system intelligently handles different data types, automatically creating the most appropriate visualization: line plots for scalar metrics over time, animated videos for image sequences, and structured compilations for complex artifacts. This automatic compilation and visualization means that understanding your experiment's behavior becomes immediate and intuitive, without requiring manual post-processing or custom visualization code.

### Post-Experiment Analysis and Reloadability

Perhaps the most overlooked aspect of experimental workflows is what happens after an experiment completes. Traditional approaches often leave you with raw output files that require custom parsing and loading code, making it difficult to perform retrospective analysis or build on previous results.

PyComex addresses this through **experiment reloadability**. Every archived experiment can be loaded back into memory with full access to its original parameters, tracked data, and generated artifacts. The framework provides a consistent API for exploring experimental results, whether you're analyzing a single experiment or comparing across dozens of experimental runs.

This capability transforms post-experiment analysis from a tedious manual process into a streamlined investigation. You can easily load experiments, compare their results, generate visualizations, and perform meta-analyses using the same tools and interfaces, regardless of when the experiments were originally run.

The framework also automatically generates analysis boilerplate code for each experiment, providing a starting point for deeper investigation and ensuring that the analysis workflow is as systematic as the experimental execution itself.