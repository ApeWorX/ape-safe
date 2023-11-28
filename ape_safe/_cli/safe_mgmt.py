import click
from ape.cli import NetworkBoundCommand, network_option, non_existing_alias_argument
from ape.exceptions import ChainError
from ape.types import AddressType

from ape_safe._cli.click_ext import SafeCliContext, safe_cli_ctx, safe_option
from ape_safe.client import ExecutedTxData


@click.command(name="list", cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
def _list(cli_ctx: SafeCliContext, network):
    """
    Show locally-tracked Safes
    """

    _ = network  # Needed for NetworkBoundCommand
    number_of_safes = len(cli_ctx.safes)

    if number_of_safes == 0:
        cli_ctx.logger.warning("No Safes found.")
        return

    header = f"Found {number_of_safes} Safe"
    header += "s:" if number_of_safes > 1 else ":"
    click.echo(header)

    for account in cli_ctx.safes:
        extras = []
        if account.alias:
            extras.append(f"alias: '{account.alias}'")

        try:
            extras.append(f"version: '{account.version}'")
        except ChainError:
            # Not connected to the network where safe is deployed
            extras.append("version: (not connected)")

        extras_display = f" ({', '.join(extras)})" if extras else ""
        click.echo(f"  {account.address}{extras_display}")


@click.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@click.argument("address", type=AddressType)
@non_existing_alias_argument()
def add(cli_ctx: SafeCliContext, network, address, alias):
    """
    Add a Safe to locally tracked Safes
    """

    _ = network  # Needed for NetworkBoundCommand
    address = cli_ctx.conversion_manager.convert(address, AddressType)
    safe_contract = cli_ctx.chain_manager.contracts.instance_at(address)
    version_display = safe_contract.VERSION()
    required_confirmations = safe_contract.getThreshold()
    signers_display = "\n    - ".join(safe_contract.getOwners())

    cli_ctx.logger.info(
        f"""Safe Found
    network: {network}
    address: {safe_contract.address}
    version: {version_display}
    required confirmations: {required_confirmations}
    signers:
    - {signers_display}
    """
    )

    if click.confirm("Add safe"):
        cli_ctx.safes.save_account(alias, address)
        cli_ctx.logger.success(f"Safe '{address}' ({alias}) added.")


@click.command()
@safe_cli_ctx
@safe_option
def remove(cli_ctx: SafeCliContext, safe):
    """
    Stop tracking a locally-tracked Safe
    """

    if click.confirm(f"Remove safe {safe.address} ({safe.alias})"):
        cli_ctx.safes.delete_account(safe.alias)
        cli_ctx.logger.success(f"Safe '{safe.address}' ({safe.alias}) removed.")


@click.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@click.argument("address", type=AddressType)
@click.option("--confirmed", is_flag=True, default=None)
def all_txns(cli_ctx: SafeCliContext, network, address, confirmed):
    """
    View and filter all transactions for a given Safe using Safe API
    """

    _ = network  # Needed for NetworkBoundCommand

    # NOTE: Create a client to support non-local safes.
    client = cli_ctx.safes.create_client(address)

    for txn in client.get_transactions(confirmed=confirmed):
        if isinstance(txn, ExecutedTxData):
            success_str = "success" if txn.is_successful else "revert"
            click.echo(f"Txn {txn.nonce}: {success_str} @ {txn.execution_date}")
        else:
            click.echo(
                f"Txn {txn.nonce}: pending ({len(txn.confirmations)}/{txn.confirmations_required})"
            )