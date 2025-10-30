"""Generate HTML reports with visualizations for Optuna studies."""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Any
import warnings

try:
    import optuna
    from optuna.visualization.matplotlib import (
        plot_optimization_history,
        plot_param_importances,
        plot_parallel_coordinate,
        plot_slice,
        plot_contour,
        plot_edf,
        plot_timeline,
    )
    OPTUNA_AVAILABLE = True
    print(f"DEBUG: Optuna import SUCCESS in report.py")
except ImportError as e:
    OPTUNA_AVAILABLE = False
    optuna = None
    print(f"DEBUG: Optuna import FAILED in report.py: {e}")

try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None

from pycomex.plugins.optuna.main import StudyManager


class OptunaReportGenerator:
    """
    Generate HTML reports with visualizations for Optuna studies.

    This class creates comprehensive HTML reports for Optuna hyperparameter optimization
    studies, including various visualization plots to help understand the optimization
    process and results.

    The report includes:
    - Study summary with metadata
    - Optimization history plot
    - Parameter importance analysis
    - Parallel coordinate visualization
    - Slice plots for individual parameters
    - Contour plots for parameter interactions
    - Empirical distribution function
    - Trial timeline

    Example:

    .. code-block:: python

        from pycomex.plugins.optuna import StudyManager, OptunaReportGenerator

        study_manager = StudyManager("/path/to/experiments")
        report_gen = OptunaReportGenerator(study_manager)

        # Generate report in current directory
        report_path = report_gen.generate_report("my_study")
        print(f"Report generated at: {report_path}")

    :param study_manager: StudyManager instance for loading studies
    """

    def __init__(self, study_manager: StudyManager):
        """
        Initialize the report generator.

        :param study_manager: StudyManager instance for accessing Optuna studies
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna is required for report generation. Install with: pip install pycomex[full]")

        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("Matplotlib is required for report generation.")

        self.study_manager = study_manager

    def _apply_modern_style(self):
        """
        Apply modern, clean matplotlib styling for better visual aesthetics.

        This configures matplotlib with:
        - Larger, more readable fonts
        - Clean white backgrounds
        - Subtle grid lines
        - Colorblind-safe color palettes
        - Professional appearance
        """
        # Set global matplotlib parameters for modern aesthetics
        plt.rcParams.update({
            # Figure and axes
            'figure.facecolor': 'white',
            'axes.facecolor': 'white',
            'axes.edgecolor': '#CCCCCC',
            'axes.linewidth': 1.0,
            'axes.grid': True,
            'axes.axisbelow': True,

            # Grid styling - subtle and non-distracting
            'grid.color': '#E0E0E0',
            'grid.linestyle': '--',
            'grid.linewidth': 0.8,
            'grid.alpha': 0.7,

            # Fonts - larger and more readable with Roboto Condensed
            'font.family': 'sans-serif',
            'font.sans-serif': ['Roboto Condensed', 'DejaVu Sans', 'Arial', 'Helvetica'],
            'font.size': 11,
            'axes.labelsize': 13,
            'axes.titlesize': 15,
            'axes.titleweight': 'bold',
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.titlesize': 16,

            # Spines - remove top and right for cleaner look
            'axes.spines.top': False,
            'axes.spines.right': False,

            # Colors - use colorblind-safe defaults
            'axes.prop_cycle': plt.cycler('color', [
                '#0173B2',  # Blue
                '#DE8F05',  # Orange
                '#029E73',  # Green
                '#CC78BC',  # Purple
                '#CA9161',  # Brown
                '#949494',  # Gray
                '#ECE133',  # Yellow
                '#56B4E9',  # Light blue
            ]),

            # Line and marker styling
            'lines.linewidth': 2.0,
            'lines.markersize': 6,

            # Saving
            'savefig.facecolor': 'white',
            'savefig.edgecolor': 'none',
            'savefig.bbox': 'tight',
        })

    def generate_report(
        self,
        study_name: str,
        output_dir: Optional[str] = None
    ) -> Path:
        """
        Generate a comprehensive HTML report for an Optuna study.

        Creates a folder containing an HTML report and visualization plots as PNG images.
        The folder structure is:

        .. code-block:: text

            {study_name}_report/
            ├── index.html          # Main report page
            └── plots/              # Visualization PNG files
                ├── optimization_history.png
                ├── param_importances.png
                ├── parallel_coordinate.png
                ├── slice.png
                ├── contour_*.png
                ├── edf.png
                └── timeline.png

        :param study_name: Name of the Optuna study to generate report for
        :param output_dir: Optional custom output directory path. If None, uses '{study_name}_report'

        :return: Path to the generated report directory

        :raises ValueError: If the study doesn't exist or has no trials
        """
        # Load study
        storage_url = self.study_manager._get_storage_url(study_name)
        try:
            study = optuna.load_study(
                study_name=study_name,
                storage=storage_url
            )
        except KeyError:
            raise ValueError(f"Study '{study_name}' not found")

        if len(study.trials) == 0:
            raise ValueError(f"Study '{study_name}' has no trials to report")

        # Apply modern matplotlib styling for better visual aesthetics
        self._apply_modern_style()

        # Get study info
        study_info = self.study_manager.get_study_info(study_name)

        # Create output directory
        if output_dir is None:
            output_dir = f"{study_name}_report"

        report_path = Path(output_dir)
        plots_path = report_path / "plots"
        plots_path.mkdir(parents=True, exist_ok=True)

        # Generate all visualizations
        plot_files = {}

        # 1. Optimization History
        try:
            plot_path = self._generate_optimization_history(study, plots_path)
            if plot_path:
                plot_files['optimization_history'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate optimization history plot: {e}")

        # 2. Parameter Importances
        try:
            plot_path = self._generate_param_importances(study, plots_path)
            if plot_path:
                plot_files['param_importances'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate parameter importances plot: {e}")

        # 3. Parallel Coordinate
        try:
            plot_path = self._generate_parallel_coordinate(study, plots_path)
            if plot_path:
                plot_files['parallel_coordinate'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate parallel coordinate plot: {e}")

        # 4. Slice Plot
        try:
            plot_path = self._generate_slice_plot(study, plots_path)
            if plot_path:
                plot_files['slice'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate slice plot: {e}")

        # 5. Contour Plots
        try:
            contour_paths = self._generate_contour_plots(study, plots_path)
            if contour_paths:
                plot_files['contour'] = contour_paths
        except Exception as e:
            warnings.warn(f"Failed to generate contour plots: {e}")

        # 6. EDF Plot
        try:
            plot_path = self._generate_edf(study, plots_path)
            if plot_path:
                plot_files['edf'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate EDF plot: {e}")

        # 7. Timeline
        try:
            plot_path = self._generate_timeline(study, plots_path)
            if plot_path:
                plot_files['timeline'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate timeline plot: {e}")

        # 8. Parameter Correlation Heatmap
        try:
            plot_path = self._generate_param_correlation(study, plots_path)
            if plot_path:
                plot_files['param_correlation'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate parameter correlation plot: {e}")

        # 9. Parameter Distribution Histograms
        try:
            plot_path = self._generate_param_distributions(study, plots_path)
            if plot_path:
                plot_files['param_distributions'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate parameter distributions plot: {e}")

        # 10. Trial State Distribution
        try:
            plot_path = self._generate_trial_states(study, plots_path)
            if plot_path:
                plot_files['trial_states'] = plot_path
        except Exception as e:
            warnings.warn(f"Failed to generate trial states plot: {e}")

        # Generate HTML report
        html_path = self._create_html_report(study_info, plot_files, report_path)

        return report_path

    def _generate_optimization_history(self, study, plots_path: Path) -> Optional[Path]:
        """Generate optimization history plot."""
        result = plot_optimization_history(study)
        plot_path = plots_path / "optimization_history.png"
        # Handle both Figure and Axes objects
        if hasattr(result, 'get_figure'):
            fig = result.get_figure()
        else:
            fig = result
        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _generate_param_importances(self, study, plots_path: Path) -> Optional[Path]:
        """Generate parameter importances plot."""
        if len(study.trials) < 2:
            return None  # Need at least 2 trials for importance

        try:
            result = plot_param_importances(study)
            plot_path = plots_path / "param_importances.png"
            # Handle both Figure and Axes objects
            if hasattr(result, 'get_figure'):
                fig = result.get_figure()
            else:
                fig = result
            fig.savefig(plot_path, dpi=200, bbox_inches='tight')
            plt.close(fig)
            return plot_path
        except ImportError:
            # scikit-learn not available
            return None

    def _generate_parallel_coordinate(self, study, plots_path: Path) -> Optional[Path]:
        """Generate parallel coordinate plot with alpha transparency to reduce clutter."""
        result = plot_parallel_coordinate(study)
        plot_path = plots_path / "parallel_coordinate.png"
        # Handle both Figure and Axes objects
        if hasattr(result, 'get_figure'):
            fig = result.get_figure()
        else:
            fig = result

        # Add alpha transparency to all lines to reduce visual clutter
        for ax in fig.get_axes():
            for line in ax.get_lines():
                line.set_alpha(0.3)

        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _generate_slice_plot(self, study, plots_path: Path) -> Optional[Path]:
        """Generate slice plot showing individual parameter effects."""
        result = plot_slice(study)
        plot_path = plots_path / "slice.png"
        # Handle Figure, Axes, or array of Axes objects
        if hasattr(result, 'get_figure'):
            # Single Axes object
            fig = result.get_figure()
        elif hasattr(result, 'savefig'):
            # Already a Figure
            fig = result
        elif hasattr(result, 'flat'):
            # Array of Axes - get figure from first axes
            fig = result.flat[0].get_figure()
        else:
            # Fallback: use current figure
            fig = plt.gcf()
        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _generate_contour_plots(self, study, plots_path: Path) -> List[Path]:
        """Generate contour plots for top parameter pairs."""
        contour_paths = []

        # Get all parameter names
        params = list(study.best_params.keys())

        if len(params) < 2:
            return contour_paths

        # Generate contour for top 2-3 parameter pairs
        # For simplicity, just do the first 2 pairs
        max_pairs = min(2, len(params) // 2)

        for i in range(max_pairs):
            param_pair = params[i*2:i*2+2]
            if len(param_pair) == 2:
                try:
                    result = plot_contour(study, params=param_pair)
                    plot_path = plots_path / f"contour_{'_'.join(param_pair)}.png"
                    # Handle both Figure and Axes objects
                    if hasattr(result, 'get_figure'):
                        fig = result.get_figure()
                    else:
                        fig = result
                    fig.savefig(plot_path, dpi=200, bbox_inches='tight')
                    plt.close(fig)
                    contour_paths.append(plot_path)
                except Exception:
                    pass  # Skip if contour can't be generated for this pair

        return contour_paths

    def _generate_edf(self, study, plots_path: Path) -> Optional[Path]:
        """Generate empirical distribution function plot."""
        result = plot_edf(study)
        plot_path = plots_path / "edf.png"
        # Handle both Figure and Axes objects
        if hasattr(result, 'get_figure'):
            fig = result.get_figure()
        else:
            fig = result
        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _generate_timeline(self, study, plots_path: Path) -> Optional[Path]:
        """Generate trial timeline plot."""
        result = plot_timeline(study)
        plot_path = plots_path / "timeline.png"
        # Handle both Figure and Axes objects
        if hasattr(result, 'get_figure'):
            fig = result.get_figure()
        else:
            fig = result
        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _generate_param_correlation(self, study: Any, plots_path: Path) -> Optional[Path]:
        """
        Generate parameter correlation heatmap.

        Shows correlations between parameters and between parameters and objective value.

        :param study: Optuna study object
        :param plots_path: Directory to save the plot
        :return: Path to the saved plot, or None if generation failed
        """
        import numpy as np

        # Get completed trials only
        completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]

        if len(completed_trials) < 2:
            return None

        # Extract parameter names (only numeric parameters)
        param_names = []
        param_data = []

        for trial in completed_trials:
            if not param_names:
                # First trial - identify numeric parameters
                for param_name, param_value in trial.params.items():
                    if isinstance(param_value, (int, float)):
                        param_names.append(param_name)

            # Extract values for this trial
            row = [trial.params.get(name, np.nan) for name in param_names]
            param_data.append(row)

        if not param_names:
            return None

        # Add objective values
        objectives = [trial.value for trial in completed_trials]

        # Create data matrix: parameters + objective
        data = np.array(param_data)
        objectives_array = np.array(objectives).reshape(-1, 1)
        full_data = np.hstack([data, objectives_array])

        # Calculate correlation matrix
        correlation_matrix = np.corrcoef(full_data.T)

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))

        # Plot heatmap with colorblind-friendly colormap
        im = ax.imshow(correlation_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')

        # Add colorbar with better formatting
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Correlation Coefficient', rotation=270, labelpad=25, fontsize=12)
        cbar.ax.tick_params(labelsize=10)

        # Set ticks and labels
        labels = param_names + ['Objective']
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=11)
        ax.set_yticklabels(labels, fontsize=11)

        # Add correlation values to cells with better visibility
        for i in range(len(labels)):
            for j in range(len(labels)):
                corr_val = correlation_matrix[i, j]
                # Choose text color based on background intensity
                text_color = 'white' if abs(corr_val) > 0.5 else 'black'
                text = ax.text(j, i, f'{corr_val:.2f}',
                             ha="center", va="center", color=text_color,
                             fontsize=9, fontweight='bold')

        ax.set_title('Parameter Correlation Heatmap', pad=15)
        plt.tight_layout()

        # Save plot
        plot_path = plots_path / "param_correlation.png"
        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _generate_param_distributions(self, study: Any, plots_path: Path) -> Optional[Path]:
        """
        Generate parameter distribution histograms.

        Shows how the sampler explored each parameter's space.

        :param study: Optuna study object
        :param plots_path: Directory to save the plot
        :return: Path to the saved plot, or None if generation failed
        """
        import numpy as np

        # Get completed trials only
        completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]

        if len(completed_trials) < 2:
            return None

        # Collect parameter names and values
        param_data = {}
        for trial in completed_trials:
            for param_name, param_value in trial.params.items():
                if param_name not in param_data:
                    param_data[param_name] = []
                param_data[param_name].append(param_value)

        if not param_data:
            return None

        # Determine grid size
        n_params = len(param_data)
        n_cols = min(3, n_params)
        n_rows = (n_params + n_cols - 1) // n_cols

        # Create figure with subplots
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
        if n_params == 1:
            axes = np.array([axes])
        axes = axes.flatten() if n_params > 1 else axes

        # Plot histogram for each parameter
        for idx, (param_name, values) in enumerate(param_data.items()):
            ax = axes[idx]

            # Check if parameter is categorical
            if isinstance(values[0], str):
                # Categorical parameter - use bar chart
                unique_values, counts = np.unique(values, return_counts=True)
                bars = ax.bar(range(len(unique_values)), counts, color='#0173B2',
                             alpha=0.8, edgecolor='#333333', linewidth=1.2)
                ax.set_xticks(range(len(unique_values)))
                ax.set_xticklabels(unique_values, rotation=45, ha='right')
                ax.set_ylabel('Count', fontweight='bold')
            else:
                # Numeric parameter - use histogram with better styling
                n, bins, patches = ax.hist(values, bins=20, color='#0173B2',
                                          alpha=0.75, edgecolor='#333333', linewidth=1.0)
                ax.set_ylabel('Frequency', fontweight='bold')

            ax.set_title(param_name, fontweight='bold', pad=10)
            ax.set_xlabel('Value', fontweight='bold')

        # Hide unused subplots
        for idx in range(n_params, len(axes)):
            axes[idx].set_visible(False)

        fig.suptitle('Parameter Distribution Histograms', fontweight='bold')
        plt.tight_layout()

        # Save plot
        plot_path = plots_path / "param_distributions.png"
        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _generate_trial_states(self, study: Any, plots_path: Path) -> Optional[Path]:
        """
        Generate trial state distribution chart.

        Shows the proportion of completed, failed, pruned, and running trials.

        :param study: Optuna study object
        :param plots_path: Directory to save the plot
        :return: Path to the saved plot, or None if generation failed
        """
        if len(study.trials) == 0:
            return None

        # Count trials by state
        state_counts = {}
        for trial in study.trials:
            state_name = trial.state.name
            state_counts[state_name] = state_counts.get(state_name, 0) + 1

        # Define colors for each state
        state_colors = {
            'COMPLETE': '#2ecc71',  # Green
            'FAIL': '#e74c3c',      # Red
            'PRUNED': '#f39c12',    # Orange
            'RUNNING': '#3498db',   # Blue
            'WAITING': '#95a5a6',   # Gray
        }

        # Prepare data for plotting
        states = list(state_counts.keys())
        counts = list(state_counts.values())
        colors = [state_colors.get(state, '#95a5a6') for state in states]

        # Create figure with two subplots: pie chart and bar chart
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # Pie chart
        wedges, texts, autotexts = ax1.pie(
            counts,
            labels=states,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 10}
        )
        # Make percentage text bold
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax1.set_title('Trial State Distribution (Pie Chart)', fontweight='bold', pad=10)

        # Bar chart
        bars = ax2.bar(states, counts, color=colors, alpha=0.85, edgecolor='#333333', linewidth=1.5)
        ax2.set_ylabel('Number of Trials', fontweight='bold')
        ax2.set_xlabel('Trial State', fontweight='bold')
        ax2.set_title('Trial State Distribution (Bar Chart)', fontweight='bold', pad=10)

        # Add count labels on bars with better styling
        for bar, count in zip(bars, counts):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2., height,
                    f'{int(count)}',
                    ha='center', va='bottom', fontweight='bold', fontsize=11)

        # Rotate x-axis labels if needed
        if len(states) > 3:
            ax2.tick_params(axis='x', rotation=45)

        fig.suptitle(f'Trial States Summary (Total: {len(study.trials)} trials)',
                    fontweight='bold')
        plt.tight_layout()

        # Save plot
        plot_path = plots_path / "trial_states.png"
        fig.savefig(plot_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return plot_path

    def _create_html_report(
        self,
        study_info: dict,
        plot_files: dict,
        report_path: Path
    ) -> Path:
        """Generate the HTML report file."""
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optuna Study Report: {study_info['name']}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}

        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 30px;
            font-size: 2.5em;
        }}

        h2 {{
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #ecf0f1;
            font-size: 1.8em;
        }}

        h3 {{
            color: #7f8c8d;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}

        .summary {{
            background-color: #ecf0f1;
            padding: 25px;
            border-radius: 6px;
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .summary-item {{
            background-color: white;
            padding: 15px;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .summary-label {{
            font-weight: 600;
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}

        .summary-value {{
            font-size: 1.5em;
            color: #2c3e50;
            font-weight: bold;
        }}

        .best-trial {{
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}

        .best-trial h3 {{
            color: #155724;
            margin-top: 0;
        }}

        .best-value {{
            font-size: 2em;
            color: #155724;
            font-weight: bold;
            margin: 10px 0;
        }}

        .param-list {{
            margin-top: 15px;
        }}

        .param-item {{
            background-color: white;
            padding: 8px 12px;
            margin: 5px 0;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}

        .param-name {{
            font-weight: bold;
            color: #155724;
        }}

        .plot-section {{
            margin: 30px 0;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 6px;
        }}

        .plot-section img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-top: 15px;
        }}

        .plot-description {{
            color: #6c757d;
            font-style: italic;
            margin-top: 10px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}

        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }}

        tr:hover {{
            background-color: #f8f9fa;
        }}

        .best-row {{
            background-color: #d4edda !important;
            font-weight: bold;
        }}

        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }}

        .timestamp {{
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Optuna Study Report: {study_info['name']}</h1>

        <!-- Study Summary -->
        <div class="summary">
            <div class="summary-item">
                <div class="summary-label">Total Trials</div>
                <div class="summary-value">{study_info['n_trials']}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Direction</div>
                <div class="summary-value">{study_info['direction']}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Best Trial</div>
                <div class="summary-value">#{study_info['best_trial'] if study_info['best_trial'] is not None else 'N/A'}</div>
            </div>
        </div>

        <!-- Best Trial -->
        {self._generate_best_trial_html(study_info)}

        <!-- Visualizations -->
        <h2>Visualizations</h2>

        {self._generate_plots_html(plot_files)}

        <!-- All Trials Table -->
        <h2>All Trials</h2>
        {self._generate_trials_table_html(study_info)}

        <!-- Footer -->
        <div class="footer">
            <p>Generated by PyComex Optuna Plugin</p>
            <p class="timestamp">Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>"""

        html_path = report_path / "index.html"
        html_path.write_text(html_content)

        return html_path

    def _generate_best_trial_html(self, study_info: dict) -> str:
        """Generate HTML for best trial section."""
        if study_info['best_trial'] is None:
            return ""

        best_value = study_info['best_value']
        best_params = study_info['best_params']

        params_html = ""
        for param_name, param_value in best_params.items():
            params_html += f'<div class="param-item"><span class="param-name">{param_name}</span>: {param_value}</div>\n'

        return f"""
        <div class="best-trial">
            <h3>Best Trial Results</h3>
            <div class="best-value">Objective Value: {best_value:.6f}</div>
            <div class="param-list">
                <strong>Parameters:</strong>
                {params_html}
            </div>
        </div>
        """

    def _generate_plots_html(self, plot_files: dict) -> str:
        """Generate HTML for visualization plots."""
        plots_html = ""

        # Plot descriptions
        descriptions = {
            'optimization_history': 'Shows how the objective value improves across trials. Helps identify convergence patterns and optimization progress.',
            'param_importances': 'Ranks hyperparameters by their importance in affecting the objective value. Helps identify which parameters matter most.',
            'parallel_coordinate': 'Visualizes relationships across all parameters simultaneously. Good trials are typically clustered together.',
            'slice': 'Shows the effect of each individual parameter on the objective value. Helps identify optimal ranges for each parameter.',
            'contour': 'Visualizes interactions between pairs of parameters. Helps understand how parameters work together.',
            'edf': 'Empirical distribution function of objective values. Shows the distribution and quality of explored solutions.',
            'timeline': 'Shows when trials were executed. Useful for understanding parallelization and identifying slow trials.',
            'param_correlation': 'Correlation heatmap showing relationships between parameters and objective value. Strong correlations indicate important parameter interactions.',
            'param_distributions': 'Distribution histograms showing how the sampler explored each parameter space. Helps identify sampling patterns and concentration regions.',
            'trial_states': 'Distribution of trial states (completed, failed, pruned). Provides diagnostic information about optimization health and stability.'
        }

        plot_titles = {
            'optimization_history': 'Optimization History',
            'param_importances': 'Parameter Importances',
            'parallel_coordinate': 'Parallel Coordinate Plot',
            'slice': 'Slice Plot',
            'contour': 'Contour Plots',
            'edf': 'Empirical Distribution Function',
            'timeline': 'Trial Timeline',
            'param_correlation': 'Parameter Correlation Heatmap',
            'param_distributions': 'Parameter Distribution Histograms',
            'trial_states': 'Trial State Distribution'
        }

        for plot_key, plot_path in plot_files.items():
            if plot_key == 'contour' and isinstance(plot_path, list):
                # Handle multiple contour plots
                plots_html += f"""
                <div class="plot-section">
                    <h3>{plot_titles[plot_key]}</h3>
                    <p class="plot-description">{descriptions[plot_key]}</p>
                """
                for contour_path in plot_path:
                    rel_path = os.path.relpath(contour_path, contour_path.parent.parent)
                    plots_html += f'<img src="{rel_path}" alt="Contour Plot">\n'
                plots_html += "</div>\n"
            else:
                rel_path = os.path.relpath(plot_path, plot_path.parent.parent)
                plots_html += f"""
                <div class="plot-section">
                    <h3>{plot_titles.get(plot_key, plot_key.replace('_', ' ').title())}</h3>
                    <p class="plot-description">{descriptions.get(plot_key, '')}</p>
                    <img src="{rel_path}" alt="{plot_titles.get(plot_key, plot_key)}">
                </div>
                """

        return plots_html

    def _generate_trials_table_html(self, study_info: dict) -> str:
        """Generate HTML table for all trials."""
        trials = study_info['trials']
        best_trial_number = study_info['best_trial']

        # Get all unique parameter names
        all_params = set()
        for trial in trials:
            all_params.update(trial['params'].keys())
        all_params = sorted(all_params)

        # Table header
        table_html = """
        <table>
            <thead>
                <tr>
                    <th>Trial</th>
                    <th>State</th>
                    <th>Value</th>
        """

        for param in all_params:
            table_html += f"<th>{param}</th>\n"

        table_html += """
                    <th>Duration (s)</th>
                </tr>
            </thead>
            <tbody>
        """

        # Table rows
        for trial in trials:
            row_class = ' class="best-row"' if trial['number'] == best_trial_number else ''
            value_str = f"{trial['value']:.6f}" if trial['value'] is not None else "N/A"
            duration_str = f"{trial['duration']:.2f}" if trial['duration'] is not None else "N/A"

            table_html += f'<tr{row_class}>\n'
            table_html += f"<td>{trial['number']}</td>\n"
            table_html += f"<td>{trial['state']}</td>\n"
            table_html += f"<td>{value_str}</td>\n"

            for param in all_params:
                param_value = trial['params'].get(param, 'N/A')
                if isinstance(param_value, float):
                    param_value = f"{param_value:.6f}"
                table_html += f"<td>{param_value}</td>\n"

            table_html += f"<td>{duration_str}</td>\n"
            table_html += "</tr>\n"

        table_html += """
            </tbody>
        </table>
        """

        return table_html
