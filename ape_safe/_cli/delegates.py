import click
from ape.cli import ConnectedProviderCommand, account_option
from ape.types import AddressType
from eth_typing import ChecksumAddress

from ape_safe._cli.click_ext import safe_argument, safe_cli_ctx, safe_option


@click.group()
def delegates():
    """
    View and configure delegates
    """


@delegates.command("list", cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_argument
def _list(cli_ctx, safe):
    """
    Show delegates for signers in a Safe
    """
    if delegates := safe.client.get_delegates():
        cli_ctx.logger.success(f"Found delegates for {safe.address} ({safe.alias})")
        for delegator in delegates:
            click.echo(f"\nSigner {delegator}:")
            click.echo("- " + "\n- ".join(delegates[delegator]))

    else:
        cli_ctx.logger.info(f"No delegates for {safe.address} ({safe.alias})")


@delegates.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@click.argument("delegate", type=ChecksumAddress)
@click.argument("label")
@account_option()
def add(cli_ctx, safe, delegate, label, account):
    """
    Add a delegate for a signer in a Safe
    """
    delegate = cli_ctx.conversion_manager.convert(delegate, AddressType)
    safe.client.add_delegate(delegate, label, account)
    cli_ctx.logger.success(
        f"Added delegate {delegate} ({label}) for {account.address} "
        f"in {safe.address} ({safe.alias})"
    )


@delegates.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@click.argument("delegate", type=ChecksumAddress)
@account_option()
def remove(cli_ctx, safe, delegate, account):
    """
    Remove a delegate for a specific signer in a Safe
    """
    delegate = cli_ctx.conversion_manager.convert(delegate, AddressType)
    safe.client.remove_delegate(delegate, account)
    cli_ctx.logger.success(
        f"Removed delegate {delegate} for {account.address} in {safe.address} ({safe.alias})"
    )
