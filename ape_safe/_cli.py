import click
from ape import Contract, accounts, convert, networks
from ape.cli import (
    NetworkBoundCommand,
    ape_cli_context,
    existing_alias_argument,
    network_option,
    non_existing_alias_argument,
)
from ape.exceptions import ChainError
from ape.types import AddressType

from .accounts import SafeAccount
from .client import ExecutedTxData, SafeClient


@click.group(short_help="Manage Safe accounts and view Safe API data")
def cli():
    """
    Command-line helpder for managing Safes. You can add Safes to your local accounts,
    or view data from any Safe using the Safe API client.
    """


@cli.command(name="list", cls=NetworkBoundCommand, short_help="Show locally-tracked Safes")
@ape_cli_context()
@network_option()
def _list(cli_ctx, network):
    safes = accounts.get_accounts_by_type(type_=SafeAccount)
    num_of_accts = len(safes)

    if num_of_accts == 0:
        cli_ctx.logger.warning("No Safes found.")
        return

    header = f"Found {num_of_accts} Safe"
    header += "s:" if num_of_accts > 1 else ":"
    click.echo(header)

    for account in safes:
        extras = []
        if account.alias:
            extras.append(f"alias: '{account.alias}'")

        try:
            extras.append(f"version: '{account.version}'")
        except ChainError:
            cli_ctx.logger.warning(
                f"Not connected to the network that {account.address} is deployed"
            )

        extras_display = f" ({', '.join(extras)})" if extras else ""
        click.echo(f"  {account.address}{extras_display}")


@cli.command(cls=NetworkBoundCommand, short_help="Add a Safe to locally tracked Safes")
@ape_cli_context()
@network_option()
@click.argument("address", type=AddressType)
@non_existing_alias_argument()
def add(cli_ctx, network, address, alias):
    address = convert(address, AddressType)
    safe_contract = Contract(address)
    version_display = safe_contract.VERSION()
    req_confs = safe_contract.getThreshold()
    signers_display = "\n    - ".join(safe_contract.getOwners())

    cli_ctx.logger.info(
        f"""Safe Found
    network: {network}
    address: {safe_contract.address}
    version: {version_display}
    required confirmations: {req_confs}
    signers:
    - {signers_display}
    """
    )

    if click.confirm("Add safe"):
        accounts.containers["safe"].save_account(alias, address)


@cli.command(short_help="Stop tracking a locally-tracked Safe")
@ape_cli_context()
@existing_alias_argument()
def remove(cli_ctx, alias):
    safe_container = accounts.containers["safe"]

    if alias not in safe_container.aliases:
        raise

    address = safe_container.load_account(alias).address
    if click.confirm(f"Remove safe {address} ({alias})"):
        safe_container.delete_account(alias)


@cli.command(
    cls=NetworkBoundCommand, short_help="See pending transactions for a locally-tracked Safe"
)
@network_option()
@click.option("sign_with_local_signers", "--sign", is_flag=True)
@click.option("--execute", is_flag=False, flag_value=True, default=False)
@existing_alias_argument(account_type=SafeAccount)
def pending(network, sign_with_local_signers, execute, alias):
    safe = accounts.load(alias)

    if isinstance(execute, str):
        if execute in accounts.aliases:
            submitter = accounts.load(execute)
        else:
            raise

    elif execute is True:
        submitter = safe.local_signers[0]

    for safe_tx, confirmations in safe.pending_transactions():
        if sign_with_local_signers and len(confirmations) < safe.confirmations_required:
            pass  # TODO: sign `safe_tx` with local signers not in `confirmations`

        else:
            click.echo(f"Txn {safe_tx.nonce}: ({len(confirmations)}/{safe.confirmations_required})")

        if execute is not False:
            signatures = safe.get_confirmations(safe_tx)
            if len(signatures) >= safe.confirmations_required and click.confirm(
                f"Submit Txn {safe_tx.nonce}"
            ):
                submitter.call(safe.create_execute_transaction(safe_tx, signatures))


@cli.command(cls=NetworkBoundCommand, short_help="Reject one or more pending transactions")
@network_option()
@existing_alias_argument(account_type=SafeAccount)
@click.argument("txn-ids", type=int, nargs=-1)
@ape_cli_context()
def reject(cli_ctx, network, alias, txn_ids):
    safe = accounts.load(alias)
    pending = safe.client.get_transactions(starting_nonce=safe.next_nonce)

    for txn_id in txn_ids:
        try:
            txn = next(txn for txn in pending if txn_id == txn.nonce)
        except StopIteration:
            cli_ctx.logger.error(f"Transaction ID '{txn_id}' is not a pending transaction.")
            continue

        if click.confirm(f"{txn}\nCancel Transaction?"):
            safe.transfer(safe, "0 ether", nonce=txn_id, submit_transaction=False)


@cli.command(
    cls=NetworkBoundCommand,
    short_help="View and filter all transactions for a given Safe using Safe API",
)
@network_option()
@click.argument("address", type=AddressType)
@click.option("--confirmed", type=bool, default=None)
def all_txns(network, address, confirmed):
    safe_container = accounts.containers["safe"]

    if address in safe_container.aliases:
        address = safe_container.load_account(address).address

    else:
        address = convert(address, AddressType)

    client = SafeClient(address=address, chain_id=networks.provider.chain_id)

    for txn in client.get_transactions(confirmed=confirmed):
        if isinstance(txn, ExecutedTxData):
            success_str = "success" if txn.isSuccessful else "revert"
            click.echo(f"Txn {txn.nonce}: {success_str} @ {txn.executionDate}")
        else:
            click.echo(
                f"Txn {txn.nonce}: pending ({len(txn.confirmations)}/{txn.confirmationsRequired})"
            )
