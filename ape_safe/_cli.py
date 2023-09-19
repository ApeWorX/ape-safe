import click
from ape.cli import (
    NetworkBoundCommand,
    ape_cli_context,
    existing_alias_argument,
    network_option,
    non_existing_alias_argument,
)
from ape.exceptions import ChainError
from ape.types import AddressType
from click import BadArgumentUsage, BadOptionUsage

from ape_safe.accounts import SafeAccount
from ape_safe.client import ExecutedTxData, SafeClient


@click.group(short_help="Manage Safe accounts and view Safe API data")
def cli():
    """
    Command-line helper for managing Safes. You can add Safes to your local accounts,
    or view data from any Safe using the Safe API client.
    """


@cli.command(name="list", cls=NetworkBoundCommand, short_help="Show locally-tracked Safes")
@ape_cli_context()
@network_option()
def _list(cli_ctx, network):
    _ = network  # Needed for NetworkBoundCommand
    safes = cli_ctx.account_manager.get_accounts_by_type(type_=SafeAccount)
    safes_length = len(safes)

    if safes_length == 0:
        cli_ctx.logger.warning("No Safes found.")
        return

    header = f"Found {safes_length} Safe"
    header += "s:" if safes_length > 1 else ":"
    click.echo(header)

    for account in safes:
        extras = []
        if account.alias:
            extras.append(f"alias: '{account.alias}'")

        try:
            extras.append(f"version: '{account.version}'")
        except ChainError:
            # Not connected to the network where safe is deployed
            pass

        extras_display = f" ({', '.join(extras)})" if extras else ""
        click.echo(f"  {account.address}{extras_display}")


@cli.command(cls=NetworkBoundCommand, short_help="Add a Safe to locally tracked Safes")
@ape_cli_context()
@network_option()
@click.argument("address", type=AddressType)
@non_existing_alias_argument()
def add(cli_ctx, network, address, alias):
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
        cli_ctx.account_manager.containers["safe"].save_account(alias, address)


@cli.command(short_help="Stop tracking a locally-tracked Safe")
@ape_cli_context()
@existing_alias_argument()
def remove(cli_ctx, alias):
    safe_container = cli_ctx.account_manager.containers["safe"]

    if alias not in safe_container.aliases:
        raise BadArgumentUsage(
            f"There is no account with the alias `{alias}` in the safe accounts."
        )

    address = safe_container.load_account(alias).address
    if click.confirm(f"Remove safe {address} ({alias})"):
        safe_container.delete_account(alias)


def _execute_callback(ctx, param, val):
    if isinstance(val, str):
        if val in ctx.obj.account_manager.aliases:
            return ctx.obj.account_manager.load(val)
        elif val in ctx.obj.account_manager:
            return ctx.obj.account_manager[val]
        else:
            raise BadOptionUsage(
                "--execute", f"`--execute` value '{val}` not found in local accounts."
            )

    # Additional handling may occur in command definition.
    return val


@cli.command(
    cls=NetworkBoundCommand, short_help="See pending transactions for a locally-tracked Safe"
)
@ape_cli_context()
@network_option()
@click.option("sign_with_local_signers", "--sign", is_flag=True)
@click.option("--execute", is_flag=True, flag_value=True, default=False, callback=_execute_callback)
@existing_alias_argument(account_type=SafeAccount)
def pending(cli_ctx, network, sign_with_local_signers, execute, alias):
    _ = network  # Needed for NetworkBoundCommand
    safe = cli_ctx.account_manager.load(alias)
    submitter = execute
    if submitter is True:
        if not safe.local_signers:
            cli_ctx.abort("Cannot execute without a local signer.")

        submitter = safe.local_signers[0]

    for safe_tx, confirmations in safe.pending_transactions():
        click.echo(
            f"Transaction {safe_tx.nonce}: ({len(confirmations)}/{safe.confirmations_required})"
        )

        if sign_with_local_signers and len(confirmations) < safe.confirmations_required:
            pass  # TODO: sign `safe_tx` with local signers not in `confirmations`

        if not execute:
            signatures = safe.get_api_confirmations(safe_tx)
            if len(signatures) >= safe.confirmations_required and click.confirm(
                f"Submit Transaction {safe_tx.nonce}"
            ):
                submitter.call(safe.create_execute_transaction(safe_tx, signatures))


@cli.command(cls=NetworkBoundCommand, short_help="Reject one or more pending transactions")
@network_option()
@existing_alias_argument(account_type=SafeAccount)
@click.argument("txn-ids", type=int, nargs=-1)
@ape_cli_context()
def reject(cli_ctx, network, alias, txn_ids):
    _ = network  # Needed for NetworkBoundCommand
    safe = cli_ctx.account_manager.load(alias)
    pending_transactions = safe.client.get_transactions(starting_nonce=safe.next_nonce)

    for txn_id in txn_ids:
        try:
            txn = next(txn for txn in pending_transactions if txn_id == txn.nonce)
        except StopIteration:
            # NOTE: Not a pending transaction.
            continue

        if click.confirm(f"{txn}\nCancel Transaction?"):
            safe.transfer(safe, "0 ether", nonce=txn_id, submit_transaction=False)


@cli.command(
    cls=NetworkBoundCommand,
    short_help="View and filter all transactions for a given Safe using Safe API",
)
@ape_cli_context()
@network_option()
@click.argument("address", type=AddressType)
@click.option("--confirmed", is_flag=True, default=None)
def all_txns(cli_ctx, network, address, confirmed):
    _ = network  # Needed for NetworkBoundCommand
    safe_container = cli_ctx.account_manager.containers["safe"]
    address = (
        safe_container.load_account(address).address
        if address in safe_container.aliases
        else cli_ctx.conversion_manager.convert(address, AddressType)
    )
    client = SafeClient(address=address, chain_id=cli_ctx.chain_manager.provider.chain_id)

    for txn in client.get_transactions(confirmed=confirmed):
        if isinstance(txn, ExecutedTxData):
            success_str = "success" if txn.isSuccessful else "revert"
            click.echo(f"Txn {txn.nonce}: {success_str} @ {txn.executionDate}")
        else:
            click.echo(
                f"Txn {txn.nonce}: pending ({len(txn.confirmations)}/{txn.confirmationsRequired})"
            )
