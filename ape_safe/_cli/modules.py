from typing import TYPE_CHECKING

import click
from ape.cli import ConnectedProviderCommand, network_option

from ape_safe._cli.click_ext import safe_cli_ctx, safe_option

if TYPE_CHECKING:

    from ape_safe.accounts import SafeAccount


@click.group()
def modules():
    """
    Commands for handling safe modules
    """


@modules.command("list", cls=ConnectedProviderCommand)
@network_option()
@safe_cli_ctx()
@safe_option
def _list(cli_ctx, safe: "SafeAccount") -> None:
    """List all modules enabled for SAFE"""
    for module in safe.modules:
        click.echo(repr(module))


@modules.command(cls=ConnectedProviderCommand)
@network_option()
@safe_cli_ctx()
@safe_option
def guard(cli_ctx, safe: "SafeAccount") -> None:
    """Show module guard (if enabled) for SAFE"""
    if guard := safe.modules.guard:
        click.echo(f"Guard: {guard}")

    else:
        click.secho("No Module Guard set", fg="red")
