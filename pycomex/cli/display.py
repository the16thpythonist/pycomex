"""
Rich display classes for CLI output.
"""

import datetime
import os

import rich
import rich.align
import rich.box
import rich.console
import rich.markdown
import rich.panel
from rich.columns import Columns
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement
from rich.padding import Padding
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from pycomex.functional.experiment import Experiment
from pycomex.utils import TEMPLATE_PATH


class RichLogo:
    """
    A rich display which will show the PyComex logo in ASCII art when printed.
    """

    STYLE = Style(bold=True, color="white")

    def __rich_console__(self, console, options):
        text_path = os.path.join(TEMPLATE_PATH, "logo_text.txt")
        with open(text_path) as file:
            text_string: str = file.read()
            text = Text(text_string, style=self.STYLE)

        image_path = os.path.join(TEMPLATE_PATH, "logo_image.txt")
        with open(image_path) as file:
            image_string: str = file.read()
            # Replace \e with actual escape character and create Text from ANSI
            ansi_string = image_string.replace('\\e', '\033')
            image = Text.from_ansi(ansi_string)

        side_by_side = Columns([image, text], equal=True, padding=(0, 3))
        yield Padding(side_by_side, (1, 3, 0, 3))


class RichHelp:
    """
    Rich display class for showing PyComex help information.
    """

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        yield "[white bold]PyComex[/white bold] - A Python framework for computational experiments"
        yield ""
        yield (
            "PyComex is a microframework for the creation, execution and organization of computational experiments "
            "in python. This command line interface offers tools to easily create new experiment modules "
            "from boilerplate templates, inspect and interact with the archive of completed experiments and to "
            "execute experiments directly."
        )
        yield ""
        # ~ Experiment templating
        yield "📌 [magenta bold]Create Experiments[/magenta bold]"
        yield ""
        yield (
            "to create new experiments based on the boilerplate templates, use the [cyan]template[/cyan] command group. "
            "to create a new experiment module, use the [cyan]template experiment[/cyan] command."
        )
        yield Padding(
            Syntax(
                ("pycomex template experiment --name=my_experiment"),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield (
            "To create a new sub experiment derived from an existing experiment, use the [cyan]template extend[/cyan] command."
        )
        yield Padding(
            Syntax(
                (
                    "pycomex template extend --from=my_experiment.py --name=my_sub_experiment"
                ),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield ("Use [cyan]pycomex template --help[/cyan] for more information")
        yield ""

        # ~ Experiment execution
        yield "📌 [magenta bold]Run Experiments[/magenta bold]"
        yield ""
        yield (
            "To start a new run of an experiment module, you can either execute the python module directly - using "
            "[cyan]python my_experiment.py[/cyan] - or you can use the [cyan]run[/cyan] command. "
        )
        yield Padding(
            Syntax(
                ("pycomex run my_experiment --PARAM1=5000 --PARAM2=20"),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield ("Use [cyan]pycomex run --help[/cyan] for more information")
        yield ""

        # ~ Experiment Archives
        yield "📌 [magenta bold]Experiment Archives[/magenta bold]"
        yield ""
        yield (
            "All experiments that are executed will automatically be archived in a structured way. "
            "The [cyan]archive[/cyan] command group can be used to interact with the archive of completed experiments. "
            "The [cyan]archive overview[/cyan] command can be used to print generic information about the selected archive "
            "folder, for instance."
        )
        yield Padding(
            Syntax(
                ("pycomex archive overview"),
                lexer="bash",
                theme="monokai",
                line_numbers=False,
            ),
            (1, 3),
        )
        yield ("Use [cyan]pycomex archive --help[/cyan] for more information")


class RichExperimentParameterInfo:
    """
    Rich display class for showing experiment parameter information.
    """

    def __init__(self, experiment: Experiment):
        self.experiment = experiment

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        width = options.size.width

        num_parameters = len(self.experiment.metadata["parameters"])
        for index, (parameter, data) in enumerate(
            self.experiment.metadata["parameters"].items()
        ):
            title = f"[cyan]{parameter}[/cyan]"
            if "type" in data:
                title = title + f' - {data["type"]}'

            yield title

            if "description" in data and len(data["description"]) > 3:
                yield data["description"]

            if index + 1 < num_parameters:
                yield ""


class RichExperimentHookInfo:
    """
    Rich display class for showing experiment hook information.
    """

    def __init__(self, experiment: Experiment):
        self.experiment = experiment

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = options.size.width

        num_parameters = len(self.experiment.metadata["hooks"])
        for index, (hook, data) in enumerate(self.experiment.metadata["hooks"].items()):
            title = f"[magenta]{hook}[/magenta]"
            if "type" in data:
                title = title + f' - {data["type"]}'

            yield title

            if "description" in data and len(data["description"]) > 3:
                yield data["description"]

            if index + 1 < num_parameters:
                yield ""


class RichExperimentInfo:
    """
    Rich display class for showing detailed experiment information.
    """

    def __init__(self, path: str, experiment: Experiment):
        self.path = path
        self.experiment = experiment

        self.name = os.path.basename(self.path).split(".")[0]

    # ~ Implementing renderable
    # The following are magic methods which allow this object to produce the actual rich console
    # output.

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        width = options.size.width

        # ~ The header
        yield rich.panel.Panel(
            rich.align.Align(self.name, align="center"),
            box=rich.box.HEAVY,
            style="markdown.h1.border",
        )
        yield rich.panel.Panel(
            rich.markdown.Markdown(self.experiment.metadata["description"]),
            title="description",
            title_align="left",
            border_style="bright_black",
        )
        yield rich.panel.Panel(
            RichExperimentParameterInfo(self.experiment),
            title="parmeters",
            title_align="left",
            border_style="bright_black",
        )
        yield rich.panel.Panel(
            RichExperimentHookInfo(self.experiment),
            title="hooks",
            title_align="left",
            border_style="bright_black",
        )

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        return Measurement(len(self.name) + 20, options.max_width)


class RichExperimentList:
    """
    Rich display class for showing a list of experiments.
    """

    def __init__(self, experiments: list[Experiment]):
        self.experiments = experiments

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        width = options.size.width

        num_experiments = len(self.experiments)
        for index, experiment in enumerate(self.experiments):
            name = experiment.metadata["name"]
            title = f"[yellow]{name}[/yellow]"
            yield title

            description = experiment.metadata["short_description"]
            yield description

            # parameters = experiment.metadata['parameters']
            # yield f'[bright_black]n.o. params: {len(parameters)}[/bright_black]'

            if index + 1 < num_experiments:
                yield ""


class RichExperimentTailInfo:
    """
    Rich display class for showing tail information of recent experiments.
    """

    def __init__(self, experiment_path: str, metadata: dict):
        self.experiment_path = experiment_path
        self.metadata = metadata

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Extract experiment name from path (last two folders)
        path_parts = self.experiment_path.rstrip("/").split("/")
        experiment_id = (
            "/".join(path_parts[-2:]) if len(path_parts) >= 2 else path_parts[-1]
        )

        # Experiment name and status
        name = self.metadata.get("name", "Unknown")
        status = self.metadata.get("status", "unknown")

        # Status with emojis and colors
        has_error = self.metadata.get("has_error", False)
        if status == "done" and not has_error:
            status_display = "✅ completed"
            status_color = "green"
        elif status == "running":
            status_display = "⏳ running"
            status_color = "yellow"
        elif status == "failed" or has_error:
            error_type = self.metadata.get("error_type")
            if error_type:
                status_display = f"❌ failed ({error_type})"
            else:
                status_display = "❌ failed"
            status_color = "red"
        else:
            status_display = f"❌ {status}"
            status_color = "red"

        yield f"[cyan]{name}[/cyan] [{status_color}]{status_display}[/{status_color}] [bright_black]({experiment_id})[/bright_black]"

        # Timing information
        start_time = self.metadata.get("start_time")
        if start_time:
            dt = datetime.datetime.fromtimestamp(start_time)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            yield f"  Started: {formatted_time}"

        # End time if experiment is done
        if status == "done" and start_time:
            duration = self.metadata.get("duration", 0)
            if duration > 0:
                end_time = start_time + duration
                end_dt = datetime.datetime.fromtimestamp(end_time)
                formatted_end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                yield f"  Ended:   {formatted_end_time}"

        # Duration if available
        duration = self.metadata.get("duration", 0)
        if duration > 0:
            duration_str = f"{duration:.2f}s"
            yield f"  Duration: {duration_str}"

        # Short description
        short_desc = self.metadata.get("short_description", "")
        if short_desc:
            # Truncate if too long
            if len(short_desc) > 80:
                short_desc = short_desc[:77] + "..."
            yield f"  [bright_black]{short_desc}[/bright_black]"


class RichExperimentListInfo:
    """
    Rich display class for showing experiment list information.
    """

    def __init__(self, experiment_path: str, metadata: dict):
        self.experiment_path = experiment_path
        self.metadata = metadata

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        # Determine status with emojis and colors
        status = self.metadata.get("status", "unknown")
        has_error = self.metadata.get("has_error", False)

        if status == "done" and not has_error:
            status_emoji = "✅"
        elif status == "running":
            status_emoji = "⏳"
        elif status == "failed" or has_error:
            status_emoji = "❌"
        else:
            status_emoji = "❌"

        # Get duration for display
        duration = self.metadata.get("duration", 0)
        duration_str = ""
        if duration > 0:
            duration_str = f" [bright_black]({duration:.2f}s)[/bright_black]"

        # Create the single line output
        yield f"{status_emoji} {self.experiment_path}{duration_str}"


class RichArchiveInfo:
    """
    Rich display class for showing archive statistics.
    """

    def __init__(self, archive_stats: dict):
        self.stats = archive_stats

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Overview statistics
        total_experiments = self.stats["total_experiments"]
        successful_experiments = self.stats["successful_experiments"]
        failed_experiments = self.stats["failed_experiments"]
        success_rate = (successful_experiments / total_experiments * 100) if total_experiments > 0 else 0

        overview_content = f"""[bold]Total Experiments:[/bold] {total_experiments}
[green]✅ Successful:[/green] {successful_experiments} ([green]{success_rate:.1f}%[/green])
[red]❌ Failed:[/red] {failed_experiments} ([red]{100 - success_rate:.1f}%[/red])"""

        # Add disk space if available
        if self.stats["total_size_gb"] is not None:
            overview_content += f"\n[cyan]💾 Estimated Disk Space:[/cyan] {self.stats['total_size_gb']:.2f} GB"

        yield rich.panel.Panel(
            overview_content,
            title="📊 Overview",
            title_align="left",
            border_style="bright_blue",
        )

        # Timing statistics
        timing_content = ""
        if self.stats["first_experiment_time"]:
            first_dt = datetime.datetime.fromtimestamp(self.stats["first_experiment_time"])
            timing_content += f"[bold]First Experiment:[/bold] {first_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"

        if self.stats["last_experiment_time"]:
            last_dt = datetime.datetime.fromtimestamp(self.stats["last_experiment_time"])
            timing_content += f"[bold]Last Experiment:[/bold] {last_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"

        if self.stats["avg_duration"] is not None:
            timing_content += f"[bold]Average Duration:[/bold] {self.stats['avg_duration']:.2f}s\n"

        if self.stats["max_duration"] is not None:
            timing_content += f"[bold]Max Duration:[/bold] {self.stats['max_duration']:.2f}s\n"

        if self.stats["total_duration"] is not None:
            total_hours = self.stats['total_duration'] / 3600
            timing_content += f"[bold]Total Time:[/bold] {self.stats['total_duration']:.2f}s ({total_hours:.2f} hours)"

        if timing_content:
            yield rich.panel.Panel(
                timing_content.rstrip(),
                title="⏱️  Timing Statistics",
                title_align="left",
                border_style="bright_yellow",
            )

        # Content statistics
        content_content = ""

        # Parameter statistics with range
        if self.stats["avg_parameters"] is not None:
            min_params = self.stats["min_parameters"]
            max_params = self.stats["max_parameters"]
            avg_params = self.stats["avg_parameters"]
            total_params = self.stats["total_parameters"]

            if min_params == max_params:
                # All experiments have the same number of parameters
                content_content += f"[bold]Parameters per Experiment:[/bold] {min_params} (total: {total_params})\n"
            else:
                content_content += f"[bold]Parameters per Experiment:[/bold] {min_params}-{max_params} (avg: {avg_params:.1f}, total: {total_params})\n"

        # Asset statistics with range
        if self.stats["avg_assets"] is not None:
            min_assets = self.stats["min_assets"]
            max_assets = self.stats["max_assets"]
            avg_assets = self.stats["avg_assets"]
            total_assets = self.stats["total_assets"]

            if min_assets == max_assets:
                # All experiments have the same number of assets
                content_content += f"[bold]Assets per Experiment:[/bold] {min_assets} (total: {total_assets})"
            else:
                content_content += f"[bold]Assets per Experiment:[/bold] {min_assets}-{max_assets} (avg: {avg_assets:.1f}, total: {total_assets})"

        if content_content:
            yield rich.panel.Panel(
                content_content.rstrip(),
                title="📁 Content Statistics",
                title_align="left",
                border_style="bright_green",
            )

        # Error statistics - displayed last
        if self.stats["error_types"] and failed_experiments > 0:
            error_content = ""
            for error_type, count in sorted(self.stats["error_types"].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / failed_experiments * 100) if failed_experiments > 0 else 0
                error_content += f"[bold]{error_type}:[/bold] {count} ([red]{percentage:.1f}%[/red] of failures)\n"

            if error_content:
                yield rich.panel.Panel(
                    error_content.rstrip(),
                    title="🚫 Error Types",
                    title_align="left",
                    border_style="bright_red",
                )


class RichEnvironmentComparison:
    """
    Rich display class for comparing original and current environment information
    when reproducing experiments.
    """

    def __init__(self, original_env: dict, current_env: dict):
        """
        Initialize the environment comparison display.

        :param original_env: Environment info from the original experiment
        :param current_env: Environment info from the current system
        """
        self.original_env = original_env
        self.current_env = current_env

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """
        Render the environment comparison as rich panels.
        """
        # Extract OS information
        orig_os = self.original_env.get("os", {})
        curr_os = self.current_env.get("os", {})

        # Extract system libraries
        orig_libs = self.original_env.get("system_libraries", {})
        curr_libs = self.current_env.get("system_libraries", {})

        # Extract environment variables
        orig_vars = self.original_env.get("env_vars", {})
        curr_vars = self.current_env.get("env_vars", {})

        # Build original environment content
        orig_content_lines = []
        orig_content_lines.append(f"[bold]OS:[/bold] {orig_os.get('name', 'Unknown')} {orig_os.get('version', '')}")
        orig_content_lines.append(f"[bold]Architecture:[/bold] {orig_os.get('architecture', 'Unknown')}")

        if "cuda" in orig_libs:
            orig_content_lines.append(f"[bold]CUDA:[/bold] {orig_libs['cuda']}")

        # Show important env vars
        for key in ["CUDA_HOME", "CUDA_PATH", "LD_LIBRARY_PATH"]:
            if key in orig_vars:
                # Truncate long paths for display
                value = orig_vars[key]
                if len(value) > 50:
                    value = value[:47] + "..."
                orig_content_lines.append(f"[bold]{key}:[/bold] {value}")

        orig_content = "\n".join(orig_content_lines)

        # Build current environment content
        curr_content_lines = []
        curr_content_lines.append(f"[bold]OS:[/bold] {curr_os.get('name', 'Unknown')} {curr_os.get('version', '')}")
        curr_content_lines.append(f"[bold]Architecture:[/bold] {curr_os.get('architecture', 'Unknown')}")

        if "cuda" in curr_libs:
            curr_content_lines.append(f"[bold]CUDA:[/bold] {curr_libs['cuda']}")

        # Show important env vars
        for key in ["CUDA_HOME", "CUDA_PATH", "LD_LIBRARY_PATH"]:
            if key in curr_vars:
                # Truncate long paths for display
                value = curr_vars[key]
                if len(value) > 50:
                    value = value[:47] + "..."
                curr_content_lines.append(f"[bold]{key}:[/bold] {value}")

        curr_content = "\n".join(curr_content_lines)

        # Display original environment (white border)
        yield rich.panel.Panel(
            orig_content,
            title="🔬 Original Environment",
            title_align="left",
            border_style="white",
            padding=(1, 2),
        )

        # Display current environment (blue border)
        yield rich.panel.Panel(
            curr_content,
            title="💻 Current Environment",
            title_align="left",
            border_style="blue",
            padding=(1, 2),
        )

        # Detect and display differences (red border)
        differences = []

        # Check OS differences
        if orig_os.get('name') != curr_os.get('name'):
            differences.append(f"• OS: {orig_os.get('name')} → {curr_os.get('name')}")
        elif orig_os.get('version') != curr_os.get('version'):
            differences.append(f"• OS Version: {orig_os.get('version')} → {curr_os.get('version')}")

        if orig_os.get('architecture') != curr_os.get('architecture'):
            differences.append(f"• Architecture: {orig_os.get('architecture')} → {curr_os.get('architecture')}")

        # Check CUDA differences
        if orig_libs.get('cuda') != curr_libs.get('cuda'):
            orig_cuda = orig_libs.get('cuda', 'Not installed')
            curr_cuda = curr_libs.get('cuda', 'Not installed')
            differences.append(f"• CUDA: {orig_cuda} → {curr_cuda}")

        # Check environment variable differences
        for key in ["CUDA_HOME", "CUDA_PATH", "LD_LIBRARY_PATH"]:
            orig_val = orig_vars.get(key)
            curr_val = curr_vars.get(key)
            if orig_val != curr_val:
                # Truncate for display
                orig_display = orig_val[:40] + "..." if orig_val and len(orig_val) > 40 else orig_val or "Not set"
                curr_display = curr_val[:40] + "..." if curr_val and len(curr_val) > 40 else curr_val or "Not set"
                differences.append(f"• {key}:")
                differences.append(f"  {orig_display}")
                differences.append(f"  → {curr_display}")

        # Only show differences panel if there are differences
        if differences:
            diff_content = "\n".join(differences)
            yield rich.panel.Panel(
                diff_content,
                title="⚠️  Differences Detected",
                title_align="left",
                border_style="red",
                padding=(1, 2),
            )
        else:
            # Show success message if environments match
            yield rich.panel.Panel(
                "✅ Environments match!",
                title="Environment Comparison",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
