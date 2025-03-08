import click
import rich
from ape.cli import (
    ConnectedProviderCommand,
    network_option,
    non_existing_alias_argument,
    skip_confirmation_option,
)
from ape.exceptions import ChainError, ProviderNotConnectedError
from eth_typing import ChecksumAddress

from ape_safe._cli.click_ext import SafeCliContext, safe_argument, safe_cli_ctx
from ape_safe.client import SafeClient


@click.command(name="list")
@safe_cli_ctx()
@network_option(default=None)
@click.option("--verbose", help="Show verbose info about each safe", is_flag=True)
def _list(cli_ctx: SafeCliContext, network, provider, verbose):
    """
    Show locally-tracked Safes
    """
    if verbose and network is None:
        cli_ctx.abort("Must use '--network' with '--verbose'.")

    network_ctx = None
    if network is not None:
        network_ctx = network.use_provider(provider.name)
        network_ctx.__enter__()

    try:
        number_of_safes = len(cli_ctx.safes)

        if number_of_safes == 0:
            cli_ctx.logger.warning("No Safes found.")
            return

        header = f"Found {number_of_safes} Safe"
        header += "s:" if number_of_safes > 1 else ":"
        click.echo(header)
        total = len(cli_ctx.safes)

        for idx, safe in enumerate(cli_ctx.safes):
            extras = []
            if safe.alias:
                extras.append(f"alias: '{safe.alias}'")

            output: str = ""
            try:
                extras.append(f"version: '{safe.version}'")
            except (ChainError, ProviderNotConnectedError):
                # Not connected to the network where safe is deployed
                extras.append("version: (not connected)")

            else:
                # NOTE: Only handle verbose if we are connected.

                if verbose:
                    local_signers = safe.local_signers or []
                    if local_signers:
                        local_signers_str = ", ".join([x.alias for x in local_signers if x.alias])
                        if local_signers_str:
                            extras.append(f"\n  local signers: '{local_signers_str}'")

                    extras.append(f"next nonce: '{safe.next_nonce}'")
                    extras_joined = ", ".join(extras)
                    extras_display = f"  {extras_joined}" if extras else ""
                    output = f"  {safe.address}{extras_display}"
                    if idx < total - 1:
                        output = f"{output}\n"

            if not output:
                extras_display = f" ({', '.join(extras)})" if extras else ""
                output = f"  {safe.address}{extras_display}"

            rich.print(output)

    finally:
        if network_ctx:
            network_ctx.__exit__(None)


@click.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@click.argument("address", type=ChecksumAddress)
@non_existing_alias_argument()
def add(cli_ctx: SafeCliContext, ecosystem, network, address, alias):
    """
    Add a Safe to locally tracked Safes
    """
    from ape.types import AddressType

    address = cli_ctx.conversion_manager.convert(address, AddressType)
    safe_contract = cli_ctx.chain_manager.contracts.instance_at(address)
    version_display = safe_contract.VERSION()
    required_confirmations = safe_contract.getThreshold()
    signers_display = "\n    - ".join(safe_contract.getOwners())

    cli_ctx.logger.info(
        f"""Safe Found
    network: {ecosystem.name}:{network.name}
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
@safe_cli_ctx()
@safe_argument
@skip_confirmation_option()
def remove(cli_ctx: SafeCliContext, safe, skip_confirmation):
    """
    Stop tracking a locally-tracked Safe
    """

    alias = safe.alias
    address = safe.address

    if skip_confirmation or click.confirm(f"Remove safe {address} ({alias})"):
        cli_ctx.safes.delete_account(alias)
        cli_ctx.logger.success(f"Safe '{address}' ({alias}) removed.")


@click.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@click.argument("account")
@click.option("--confirmed", is_flag=True, default=None)
def all_txns(cli_ctx: SafeCliContext, account, confirmed):
    """
    View and filter all transactions for a given Safe using Safe API
    """
    from ape.types import AddressType

    from ape_safe.client import ExecutedTxData

    if account in cli_ctx.account_manager.aliases:
        account = cli_ctx.account_manager.load(account)

    address = cli_ctx.conversion_manager.convert(account, AddressType)
    chain_id = cli_ctx.provider.chain_id
    client = SafeClient(address=address, chain_id=chain_id)

    for txn in client.get_transactions(confirmed=confirmed):
        if isinstance(txn, ExecutedTxData):
            success_str = "success" if txn.is_successful else "revert"
            click.echo(f"Txn {txn.nonce}: {success_str} @ {txn.execution_date}")
        else:
            click.echo(
                f"Txn {txn.nonce}: pending ({len(txn.confirmations)}/{txn.confirmations_required})"
            )
