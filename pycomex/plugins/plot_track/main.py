"""Plugin for visualising tracked experiment artifacts."""

import os

import imageio
import matplotlib.pyplot as plt
from moviepy.editor import ImageSequenceClip

from pycomex.config import Config
from pycomex.functional.experiment import Experiment
from pycomex.plugin import Plugin, hook


class PlotTrackedElementsPlugin(Plugin):
    """
    This plugin will automatically create visualizations for all the tracked elements of an experiment.

    During an experiment it is possible to use the ``Experiment.track`` method to track certain experiment
    artifacts. This can either be simple numeric properties such as metrics but it can also more complex
    artifacts such as images.

    At the end of the experiment, this plugin will collect all of the tracked elements and create visualizations
    in the main experiment folder. The format of these visualizations depends on the type of the tracked
    artifact:
    - numeric properties will be plotted as a line plot.
    - images will be stitched together into a video which shows the evolution of the tracked image over
      the duration of the experiment.

    TODO: Add optional experiment parameters with which this could be customized (FPS, FIGSIZE)
    """

    def __init__(self, config: Config):
        super().__init__(config)

    @hook("after_experiment_finalize", priority=0)
    def after_experiment_finalize(self, config: Config, experiment: Experiment):
        """
        This hook is executed right after the experiment.finalize method was executed. The finalized method
        will handle the saving of the experiment data and metadata storage at the end of the actual experiment
        runtime (either completed execution or error).

        This method will iterate over all the tracked quantities of the experiment (elements of the metadata "__track__")
        list and will then create visualizations for all of those quantities depending on their type.
        - Numeric quantities will be plotted as a line plot.
        - Image paths will be stitched together into a video.
        """
        # We'll wrap this in a try-except because we dont want to do this

        tracked_keys: list[str] = experiment.metadata["__track__"]

        experiment.logger.info("plotting tracked elements...")
        for key in tracked_keys:

            print(key)
            values = experiment[key]

            # We'll wrap this in a try block because the plotting of the tracked elements is generally
            # a rather low priority step in the experiment lifetime and we don't want a random error in
            # the plotting to crash the whole experiment.
            try:

                # The first and probably most common option here is that we are dealing with just a numeric
                # property that was tracked in that case the following method will simple create a plot
                # for that property over the different tracking steps.
                if isinstance(values[0], (float, int)):
                    self.visualize_numeric_elements(experiment, key, values)

                # Alternatively, we could be dealing with file paths that were tracked
                elif isinstance(values[0], str) and os.path.exists(
                    os.path.join(experiment.path, values[0])
                ):

                    # Specifically if these files are images, the following method will stitch those images together
                    # into a video.
                    if values[0].endswith(".png"):
                        self.visualize_image_elements(experiment, key, values)

            except Exception as exc:
                experiment.logger.debug(
                    f'! plotting tracked elements "{key}" failed with "{exc}". skipping...'
                )

    def sanitize_name(self, name: str) -> str:
        """
        Given the string ``name`` associated with a tracked quantity, this method will sanitize this string so that
        it can be used as part of a filename. This primarly means that all the characters that are not allowed in
        filenames will be replaced by an underscore.

        :param name: string to be sanitized.

        :returns: string sanitized name.
        """
        return (
            name.replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace(".", "_")
        )

    def visualize_numeric_elements(
        self, experiment: Experiment, name: str, values: list[int]
    ) -> str:
        """
        Given the ``experiment`` object, the string ``name`` of the tracked quantitiy and the list of numeric
        ``values`` this method will plot these values into a line plot and save the result into the experiment
        archive folder.
        """
        # ~ plotting the figure
        fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(8, 8))
        steps = list(range(len(values)))
        ax.plot(steps, values, color="orange", label=name)
        ax.scatter(steps[-1], values[-1], color="orange", label=f"{values[-1]:.4f}")
        ax.set_title("Tracked Quantity: " + name)
        ax.set_xlabel("step")
        ax.set_ylabel("value")
        ax.legend()

        # ~ saving the figure
        name_sanitized = self.sanitize_name(name)
        result_path = os.path.join(experiment.path, name_sanitized + ".png")
        fig.savefig(result_path)
        return result_path

    def visualize_image_elements(
        self, experiment: Experiment, name: str, values: list[str]
    ) -> str:
        """
        Given the ``experiment`` object, the string ``name`` of the tracked quantity and the list of image paths
        ``values`` this method will stitch these images together into a video and save the result into the
        experiment archive folder.
        """
        images = [
            imageio.v2.imread(os.path.join(experiment.path, image_path))
            for image_path in values
        ]
        clip = ImageSequenceClip(images, fps=1)

        # ~ saving the video
        name_sanitized = self.sanitize_name(name)
        result_path = os.path.join(experiment.path, name_sanitized + ".mp4")
        clip.write_videofile(result_path, codec="libx264")
        return result_path
