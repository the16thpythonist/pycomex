"""
Rich display classes for Optuna plugin CLI output.

This module provides display classes for formatting Optuna study information
in a consistent style with the core PyComex CLI.
"""

from typing import Any
import rich.box
import rich.panel
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table
from rich.text import Text


class RichOptunaStudyList:
    """
    Rich display class for showing a list of Optuna studies.

    This displays a summary table of all studies including trial counts,
    best values, and last modification dates.
    """

    def __init__(self, studies: list[dict[str, Any]]):
        """
        Initialize the display with study data.

        :param studies: List of study information dictionaries from StudyManager.list_studies()
        """
        self.studies = studies

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        """Render the study list table."""

        if not self.studies:
            yield Text("No Optuna studies found in this directory.", style="yellow")
            return

        # Create table with booktabs-style horizontal lines only
        table = Table(
            title="Optuna Studies",
            show_header=True,
            header_style="bold white",
            border_style="bright_black",
            expand=True,
            box=rich.box.HORIZONTALS,
        )

        # Add columns
        table.add_column("Study Name", style="cyan", no_wrap=True)
        table.add_column("Trials", justify="right", style="white")
        table.add_column("Direction", justify="center", style="blue")
        table.add_column("Best Value", justify="right", style="green")
        table.add_column("Best Trial", justify="right", style="magenta")
        table.add_column("Last Modified", justify="right", style="yellow")

        # Add rows
        for study in self.studies:
            best_value_str = (
                f"{study['best_value']:.6f}"
                if study['best_value'] is not None
                else "N/A"
            )
            best_trial_str = (
                f"#{study['best_trial_number']}"
                if study['best_trial_number'] is not None
                else "N/A"
            )
            last_modified_str = study['last_modified'].strftime("%Y-%m-%d %H:%M")

            table.add_row(
                study['name'],
                str(study['n_trials']),
                study['direction'],
                best_value_str,
                best_trial_str,
                last_modified_str
            )

        yield table


class RichOptunaStudySummary:
    """
    Rich display class for showing a summary panel of an Optuna study.

    This displays the study name, direction, trial counts, and best trial information
    in a nicely formatted panel.
    """

    def __init__(self, info: dict[str, Any]):
        """
        Initialize the display with study info.

        :param info: Study information dictionary from StudyManager.get_study_info()
        """
        self.info = info

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        """Render the study summary panel."""

        # Build the summary text
        lines = []
        lines.append(Text(f"Direction: {self.info['direction']}", style="white"))
        lines.append(Text(f"Total Trials: {self.info['n_trials']}", style="white"))
        lines.append(Text())  # Empty line

        if self.info['best_trial'] is not None:
            lines.append(Text(f"Best Trial: #{self.info['best_trial']}", style="bold green"))
            lines.append(Text(f"Best Value: {self.info['best_value']:.6f}", style="bold green"))
            lines.append(Text())  # Empty line
            lines.append(Text("Best Parameters:", style="bold white"))

            for param, value in self.info['best_params'].items():
                if isinstance(value, float):
                    lines.append(Text(f"  {param}: {value:.6f}", style="cyan"))
                else:
                    lines.append(Text(f"  {param}: {value}", style="cyan"))
        else:
            lines.append(Text("No trials completed yet.", style="yellow"))

        # Create a group of all lines
        from rich.console import Group
        content = Group(*lines)

        # Wrap in a panel with study name in title
        panel = rich.panel.Panel(
            content,
            title=f"[bold cyan]Study: {self.info['name']}[/bold cyan]",
            title_align="left",
            border_style="bright_black",
            box=rich.box.ROUNDED,
            padding=(1, 2),
        )

        yield panel


class RichOptunaStudyInfo:
    """
    Rich display class for showing detailed information about a specific Optuna study.

    This displays study summary information and a detailed table of all trials
    with their parameters and objective values. The best trial is highlighted.
    """

    def __init__(self, info: dict[str, Any]):
        """
        Initialize the display with study info.

        :param info: Study information dictionary from StudyManager.get_study_info()
        """
        self.info = info

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        """Render the study information."""

        # Add blank line before panel
        yield ""

        # Use the summary display class
        yield RichOptunaStudySummary(self.info)
        yield ""

        # Trials table
        if not self.info['trials']:
            yield Text("No trials found in this study.", style="yellow")
            return

        yield Text("All Trials:", style="bold")
        yield ""

        # Create trials table with booktabs style
        table = Table(
            show_header=True,
            header_style="bold white",
            border_style="bright_black",
            expand=True,
            box=rich.box.HORIZONTALS,
        )

        # Add fixed columns (all white by default, styling will be applied per-row)
        table.add_column("Trial", justify="right", style="white", no_wrap=True)
        table.add_column("State", justify="center", style="white", no_wrap=True)
        table.add_column("Value", justify="right", style="white")
        table.add_column("Duration (s)", justify="right", style="white")

        # Get all parameter names and add them as columns
        all_params = set()
        for trial in self.info['trials']:
            all_params.update(trial['params'].keys())

        for param in sorted(all_params):
            table.add_column(param, justify="right", style="white")

        # Add rows (highlight best trial)
        for trial in self.info['trials']:
            is_best = trial['number'] == self.info['best_trial']

            # Determine style for this row
            row_style = "bold green" if is_best else None

            # Format trial number with # prefix
            trial_num = f"#{trial['number']}"

            # Format value
            value_str = (
                f"{trial['value']:.6f}"
                if trial['value'] is not None
                else "N/A"
            )

            # Format duration
            duration_str = (
                f"{trial['duration']:.2f}"
                if trial['duration'] is not None
                else "N/A"
            )

            # Build row data
            row = [
                trial_num,
                trial['state'],
                value_str,
                duration_str
            ]

            # Add parameter values
            for param in sorted(all_params):
                param_value = trial['params'].get(param, "N/A")
                if isinstance(param_value, float):
                    row.append(f"{param_value:.6f}")
                else:
                    row.append(str(param_value))

            table.add_row(*row, style=row_style)

        yield table
