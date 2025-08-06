from typing import TYPE_CHECKING

import click
from ape.cli import ConnectedProviderCommand, account_option, network_option
from ape.types import AddressType

from ape_safe._cli.click_ext import safe_argument

if TYPE_CHECKING:
    from ape.api import AccountAPI

    from ape_safe.accounts import SafeAccount


@click.group()
def modules():
    """
    Commands for handling safe modules
    """


@modules.command("list", cls=ConnectedProviderCommand)
@network_option()
@safe_argument
def _list(safe: "SafeAccount"):
    """List all modules enabled for SAFE"""
    for module in safe.modules:
        click.echo(repr(module))


@modules.command(cls=ConnectedProviderCommand)
@network_option()
@safe_argument
def guard(safe: "SafeAccount"):
    """Show module guard (if enabled) for SAFE"""
    if guard := safe.modules.guard:
        click.echo(f"Guard: {guard}")

    else:
        click.secho("No Module Guard set", fg="red")


@modules.command(cls=ConnectedProviderCommand)
@network_option()
@account_option()
@safe_argument
@click.argument("module", type=AddressType)
def enable(safe: "SafeAccount", account: "AccountAPI", module: AddressType):
    """
    Enable MODULE for SAFE

    **WARNING**: This is a potentially destructive action, and may make your safe vulnerable.
    """
    safe.modules.enable(module, submitter=account)


@modules.command(cls=ConnectedProviderCommand)
@network_option()
@account_option()
@safe_argument
@click.argument("module", type=AddressType)
def disable(safe: "SafeAccount", account: "AccountAPI", module: AddressType):
    """
    Disable MODULE for SAFE

    **WARNING**: This is a potentially destructive action, and may impact operations of your safe.
    """
    safe.modules.disable(module, submitter=account)
