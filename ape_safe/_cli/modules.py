import click
from ape.cli import ConnectedProviderCommand, account_option, ape_cli_context
from ape.types import AddressType

from ape_safe._cli.click_ext import safe_argument


@click.group()
def modules():
    """
    Commands for handling safe modules
    """


@modules.command("list", cls=ConnectedProviderCommand)
@safe_argument
def _list(safe):
    """List all modules enabled for SAFE"""
    for module in safe.modules:
        click.echo(repr(module))


@modules.command(cls=ConnectedProviderCommand)
@safe_argument
def guard(safe):
    """Show module guard (if enabled) for SAFE"""
    if guard := safe.modules.guard:
        click.echo(f"Guard: {guard}")

    else:
        click.secho("No Module Guard set", fg="red")


@modules.command(cls=ConnectedProviderCommand)
@ape_cli_context()
@account_option()
@safe_argument
@click.option("--propose", is_flag=True, default=False)
@click.argument("module")
def enable(cli_ctx, safe, account, module, propose):
    """
    Enable MODULE for SAFE

    **WARNING**: This is a potentially destructive action, and may make your safe vulnerable.
    """
    module = cli_ctx.conversion_manager.convert(module, AddressType)
    safe.modules.enable(module, submitter=account, propose=propose)


@modules.command(cls=ConnectedProviderCommand)
@ape_cli_context()
@account_option()
@safe_argument
@click.option("--propose", is_flag=True, default=False)
@click.argument("module")
def disable(cli_ctx, safe, account, module, propose):
    """
    Disable MODULE for SAFE

    **WARNING**: This is a potentially destructive action, and may impact operations of your safe.
    """
    module = cli_ctx.conversion_manager.convert(module, AddressType)
    safe.modules.disable(module, submitter=account, propose=propose)
