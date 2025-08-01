from typing import TYPE_CHECKING

import click
from ape.cli import ConnectedProviderCommand

from ape_safe._cli.click_ext import safe_cli_ctx, safe_option

if TYPE_CHECKING:

    from ape_safe.accounts import SafeAccount


@click.group()
def modules():
    """
    Commands for handling safe modules
    """


@modules.command("list", cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@click.option("--verbose", is_flag=True)
def _list(cli_ctx, safe: "SafeAccount", verbose: bool) -> None:
    """List all modules enabled for SAFE"""
    for module in safe.modules:
        click.echo(repr(module))


@modules.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@click.option("--verbose", is_flag=True)
def guard(cli_ctx, safe: "SafeAccount", verbose: bool) -> None:
    """Show module guard (if enabled) for SAFE"""
    if guard := safe.modules.guard:
        click.echo(f"Guard: {guard}")

    else:
        click.secho("No Module Guard set", fg="red")
