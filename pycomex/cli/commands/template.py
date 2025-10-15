"""
Command implementations for template-related operations.
"""

import inspect
import os
import sys

import rich_click as click

from pycomex.functional.experiment import Experiment
from pycomex.utils import (
    TEMPLATE_ENV,
    has_file_extension,
    set_file_extension,
)


class TemplateCommandsMixin:
    """
    Mixin class providing template-related CLI commands.

    This mixin provides commands for:
    - template group: Container for all template commands
    - analysis: Create analysis notebook templates
    - experiment: Create new experiment templates
    - extend: Create experiments by extending existing ones
    - config: Create config files from experiments
    - validate: Validate config files
    """

    @click.group(
        "template", short_help="Command group for templating common file types."
    )
    @click.pass_obj
    def template_group(self):
        """
        This command group contains commands that can be used to create new files from common templates, such
        as experiment modules or analysis notebooks.
        """
        pass

    @click.command("analysis", short_help="Create a template for an analysis notebook.")
    @click.option(
        "-t",
        "--type",
        type=click.Choice(["jupyter"]),
        default="jupyter",
        help="The type of the analysis template to create.",
    )
    @click.option("-o", "--output", type=click.STRING, default="analysis")
    @click.pass_obj
    def template_analysis_command(self, type: str, output: str) -> None:
        """
        Will create a new jupyter notebook file which contains boilerplate code for experiment analysis. These
        analysis notebooks can be used to load specific experiments from an archive folder, access their results,
        sort them according to a customizable criterion and then process the aggregated results into a visualization
        or a table.
        """
        click.echo("Creating analysis template...")

        # If the given "output" string is an absolute path, we use it as it is. Otherwise,
        # we resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        if type == "jupyter":

            template = TEMPLATE_ENV.get_template("analysis.ipynb")

            if not has_file_extension(output_path):
                output_path = set_file_extension(output_path, ".ipynb")

            content = template.render()
            with open(output_path, "w") as file:
                file.write(content)

        elif type == "python":

            template = TEMPLATE_ENV.get_template("analysis.py.j2")

            if not has_file_extension(output_path):
                output_path = set_file_extension(output_path, ".py")

            content = template.render()
            with open(output_path, "w") as file:
                file.write(content)

        click.secho(f"✅ created analysis template @ {output_path}", bold=True)

    @click.command(
        "experiment", short_help="Create a template for a Python experiment module."
    )
    @click.option(
        "-n",
        "--name",
        type=click.STRING,
        required=True,
        help="The name of the experiment module.",
    )
    @click.option(
        "-d",
        "--description",
        type=click.STRING,
        default="A new computational experiment.",
        help="Description of the experiment.",
    )
    @click.pass_obj
    def template_experiment_command(
        self,
        name: str,
        description: str,
    ) -> None:
        """
        Will create a new Python experiment module from a template. The experiment will include
        basic boilerplate code for setting up parameters, logging, and result collection.
        """
        click.echo("Creating experiment template...")

        output = f"{name}.py"

        # If the given "output" string is an absolute path, use it as it is. Otherwise,
        # resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        # Ensure .py extension
        if not has_file_extension(output_path):
            output_path = set_file_extension(output_path, ".py")
        elif not output_path.endswith(".py"):
            output_path = set_file_extension(output_path, ".py")

        template = TEMPLATE_ENV.get_template("experiment.py.j2")
        content = template.render(experiment_name=name, description=description)

        with open(output_path, "w") as file:
            file.write(content)

        click.secho(f"✅ created experiment template @ {output_path}", bold=True)

    @click.command(
        "extend", short_help="Create a new experiment by extending an existing one."
    )
    @click.option(
        "-n",
        "--name",
        type=click.STRING,
        required=True,
        help="The name of the newly created experiment file.",
    )
    @click.option(
        "--from",
        "from_path",
        type=click.Path(exists=True),
        required=True,
        help="File path to an existing experiment module to extend from.",
    )
    @click.pass_obj
    def template_extend_command(
        self,
        name: str,
        from_path: str,
    ) -> None:
        """
        Will create a new Python experiment module by extending an existing experiment. The new
        experiment will inherit all parameters and hook stubs from the base experiment, allowing
        for easy creation of sub-experiments with modified behavior.
        """
        click.echo("Creating extended experiment template...")

        # Load the base experiment
        try:
            # First try to import from the module to get the experiment definition
            base_experiment = Experiment.import_from(from_path, {})
        except Exception as e:
            click.secho(f"Error loading base experiment: {e}", fg="red")
            return

        output = f"{name}.py"

        # If the given "output" string is an absolute path, use it as it is. Otherwise,
        # resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        # Ensure .py extension
        if not has_file_extension(output_path):
            output_path = set_file_extension(output_path, ".py")
        elif not output_path.endswith(".py"):
            output_path = set_file_extension(output_path, ".py")

        # Extract parameters from base experiment
        parameters = base_experiment.metadata.get("parameters", {})
        hooks = base_experiment.metadata.get("hooks", {})

        # Also get the actual parameter values from the parameters dict
        for param_name, param_value in base_experiment.parameters.items():
            if param_name in parameters:
                # Format the value appropriately for Python code
                if isinstance(param_value, str):
                    parameters[param_name]["value"] = repr(param_value)
                else:
                    parameters[param_name]["value"] = param_value

        # Extract function signatures from hook implementations
        # Process all hooks from hook_map to extract their signatures
        for hook_name, hook_functions in base_experiment.hook_map.items():
            if not hook_name.startswith("__") and hook_functions:
                # Ensure the hook exists in our hooks dict
                if hook_name not in hooks:
                    hooks[hook_name] = {"name": hook_name}

                # Get the first hook function implementation for signature extraction
                func = hook_functions[0]
                try:
                    signature = inspect.signature(func)
                    # Format the signature as a string for the template
                    params = []
                    for param_name, param in signature.parameters.items():
                        if param.annotation != param.empty:
                            # Handle typing annotations properly
                            annotation_name = getattr(
                                param.annotation, "__name__", str(param.annotation)
                            )
                            params.append(f"{param_name}: {annotation_name}")
                        else:
                            params.append(param_name)
                    hooks[hook_name]["signature"] = ", ".join(params)

                    # Also try to get the docstring as description
                    if func.__doc__ and "description" not in hooks[hook_name]:
                        hooks[hook_name]["description"] = func.__doc__.strip()

                except Exception:
                    # Fallback to basic signature if inspection fails
                    hooks[hook_name]["signature"] = "e: Experiment"

        # Get the base experiment name for the extend call
        base_experiment_name = os.path.basename(from_path)
        if base_experiment_name.endswith(".py"):
            base_experiment_name = base_experiment_name[:-3]

        template = TEMPLATE_ENV.get_template("experiment_extend.py.j2")
        content = template.render(
            experiment_name=name,
            base_experiment_path=from_path,
            base_experiment_name=base_experiment_name,
            parameters=parameters,
            hooks=hooks,
            description=f"Extended experiment based on {base_experiment_name}",
        )

        with open(output_path, "w") as file:
            file.write(content)

        click.secho(
            f"✅ created extended experiment template @ {output_path}", bold=True
        )

    @click.command(
        "config",
        short_help="Create a new config.yml file by extracting parameters from an existing experiment.",
    )
    @click.option(
        "-n",
        "--name",
        type=click.STRING,
        required=True,
        help="The name of the newly created config file.",
    )
    @click.option(
        "--from",
        "from_path",
        type=click.Path(exists=True),
        required=True,
        help="File path to an existing experiment module to extract configuration from.",
    )
    @click.pass_obj
    def template_config_command(
        self,
        name: str,
        from_path: str,
    ) -> None:
        """
        Will create a new config.yml file by extracting parameters from an existing experiment.
        The config file will extend the base experiment and include all its default parameters.
        """
        click.echo("Creating config template...")

        # Load the base experiment
        try:
            # Import from the module to get the experiment definition
            base_experiment = Experiment.import_from(from_path, {})
        except Exception as e:
            click.secho(f"Error loading base experiment: {e}", fg="red")
            return

        output = f"{name}.yml"

        # If the given "output" string is an absolute path, use it as it is. Otherwise,
        # resolve it to an absolute path relative to the current working directory.
        output_path: str = None
        if os.path.isabs(output):
            output_path = output
        else:
            output_path = os.path.abspath(output)

        # Ensure .yml extension
        if not has_file_extension(output_path):
            output_path = set_file_extension(output_path, ".yml")
        elif not output_path.endswith(".yml"):
            output_path = set_file_extension(output_path, ".yml")

        # Extract parameters from base experiment
        parameters = {}

        # Get parameter values from the parameters dict
        for param_name, param_value in base_experiment.parameters.items():
            if not param_name.startswith("__"):
                parameters[param_name] = param_value

        # Get the base experiment name for the extend reference
        base_experiment_name = os.path.basename(from_path)

        template = TEMPLATE_ENV.get_template("config.yml.j2")
        content = template.render(
            config_name=name,
            base_experiment_path=from_path,
            base_experiment_name=base_experiment_name,
            parameters=parameters,
            description=f"Configuration file extending {base_experiment_name}",
        )

        with open(output_path, "w") as file:
            file.write(content)

        click.secho(f"✅ created config template @ {output_path}", bold=True)

    @click.command("validate", short_help="Validate a config file for correctness.")
    @click.argument("config_path", type=click.Path(exists=True))
    @click.option(
        "--verbose",
        "-v",
        is_flag=True,
        help="Show detailed validation information for all checks.",
    )
    @click.option(
        "--warnings-as-errors",
        is_flag=True,
        help="Treat warnings as errors (fail validation if warnings are present).",
    )
    @click.pass_obj
    def template_validate_command(
        self,
        config_path: str,
        verbose: bool,
        warnings_as_errors: bool,
    ) -> None:
        """
        Validates a PyComex configuration file for correctness.

        This command performs comprehensive validation checks including:
        - YAML syntax correctness
        - Required fields presence
        - Extended experiment existence and validity
        - Parameter name matching with base experiment
        - Mixin file existence and validity
        - Environment variable availability
        - Path field validity

        The validation helps catch errors before running experiments, providing
        helpful suggestions for typos and missing dependencies.

        Example:

            pycomex template validate my_config.yml

            pycomex template validate my_config.yml --verbose

            pycomex template validate my_config.yml --warnings-as-errors
        """
        from pycomex.functional.validate import ConfigValidator

        # Create validator
        validator = ConfigValidator(config_path, warnings_as_errors=warnings_as_errors)

        # Run validation
        success, results = validator.validate()

        # Display formatted results
        output = validator.format_results(verbose=verbose)
        click.echo(output)

        # Exit with appropriate code
        sys.exit(0 if success else 1)
