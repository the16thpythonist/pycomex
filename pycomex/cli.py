"""Console script for pycomex."""
import sys
import click

from pycomex.util import get_version


@click.group(invoke_without_command=True)
@click.option("-v", "--version", is_flag=True)
@click.pass_context
def cli(ctx: click.Context, version: bool):
    """Console script for pycomex."""
    if version:
        version = get_version()
        click.secho(version)
        sys.exit(0)


if __name__ == "__main__":
    cli()  # pragma: no cover
