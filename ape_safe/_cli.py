from typing import Optional

import click
from ape.api import AccountAPI
from ape.cli import (
    ApeCliContextObject,
    NetworkBoundCommand,
    ape_cli_context,
    existing_alias_argument,
    get_user_selected_account,
    network_option,
    non_existing_alias_argument,
)
from ape.exceptions import ChainError
from ape.types import AddressType
from click import BadArgumentUsage, BadOptionUsage

from ape_safe.accounts import SafeAccount, SafeContainer
from ape_safe.client import ExecutedTxData


class SafeCliContext(ApeCliContextObject):
    @property
    def safes(self) -> SafeContainer:
        # NOTE: Would only happen in local development of this plugin.
        assert "safe" in self.account_manager.containers, "Are all API methods implemented?"
        return self.account_manager.containers["safe"]


safe_cli_ctx = ape_cli_context(obj_type=SafeCliContext)


@click.group(short_help="Manage Safe accounts and view Safe API data")
def cli():
    """
    Command-line helper for managing Safes. You can add Safes to your local accounts,
    or view data from any Safe using the Safe API client.
    """


@cli.command(name="list", cls=NetworkBoundCommand, short_help="Show locally-tracked Safes")
@safe_cli_ctx
@network_option()
def _list(cli_ctx: SafeCliContext, network):
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


@cli.command(cls=NetworkBoundCommand, short_help="Add a Safe to locally tracked Safes")
@safe_cli_ctx
@network_option()
@click.argument("address", type=AddressType)
@non_existing_alias_argument()
def add(cli_ctx: SafeCliContext, network, address, alias):
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


@cli.command(short_help="Stop tracking a locally-tracked Safe")
@safe_cli_ctx
@existing_alias_argument()
def remove(cli_ctx: SafeCliContext, alias):
    if alias not in cli_ctx.safes.aliases:
        raise BadArgumentUsage(f"There is no safe with the alias `{alias}`.")

    address = cli_ctx.safes.load_account(alias).address
    if click.confirm(f"Remove safe {address} ({alias})"):
        cli_ctx.safes.delete_account(alias)

    cli_ctx.logger.success(f"Safe '{address}' ({alias}) removed.")


# NOTE: The handling of the `--execute` flag in the `pending` CLI
#    all happens here EXCEPT if a pending tx is executable and no
#    value of `--execute` was provided.
def _handle_execute_cli_arg(ctx, param, val):
    # Account alias - execute using this account.
    if val in ctx.obj.account_manager.aliases:
        return ctx.obj.account_manager.load(val)

    # Account address - execute using this account.
    elif val in ctx.obj.account_manager:
        return ctx.obj.account_manager[val]

    # Saying "yes, execute". Use first "local signer".
    elif val.lower() in ("true", "t", "1"):
        return True

    # Saying "no, do not execute", even if we could.
    elif val.lower() in ("false", "f", "0"):
        return False

    elif val is None:
        # Was not given any value.
        # If it is determined in `pending` that a tx can execute,
        # the user will get prompted.
        # Avoid this by always doing `--execute false`.
        return val

    raise BadOptionUsage(
        "--execute", f"`--execute` value '{val}` not a boolean or account identifier."
    )


@cli.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@click.option("sign_with_local_signers", "--sign", is_flag=True)
@click.option("--execute", callback=_handle_execute_cli_arg)
@existing_alias_argument(account_type=SafeAccount)
def pending(cli_ctx: SafeCliContext, network, sign_with_local_signers, execute, alias) -> None:
    """
    View pending transactions for a Safe
    """

    _ = network  # Needed for NetworkBoundCommand
    safe = cli_ctx.account_manager.load(alias)
    submitter: Optional[AccountAPI] = None

    if execute is True:
        if not safe.local_signers:
            cli_ctx.abort("Cannot use `--execute TRUE` without a local signer.")

        submitter = get_user_selected_account(account_list=safe.local_signers)

    elif isinstance(execute, AccountAPI):
        # The callback handler loaded the local account.
        submitter = execute

    # NOTE: --execute is only None when not specified at all.
    #   In this case, for any found executable txns, the user will be prompted.
    execute_cli_arg_specified = execute is not None

    for safe_tx, confirmations in safe.pending_transactions():
        click.echo(
            f"Transaction {safe_tx.nonce}: ({len(confirmations)}/{safe.confirmations_required})"
        )

        # Add signatures, if was requested to do so.
        if sign_with_local_signers and len(confirmations) < safe.confirmations_required - 1:
            safe.add_signatures(safe_tx, confirmations)
            cli_ctx.logger.success(f"Signature added to 'Transaction {safe_tx.nonce}'.")

        # NOTE: Lazily check signatures.
        signatures = None

        if not execute_cli_arg_specified:
            # Check if we _can_ execute and ask the user.
            signatures = safe.get_api_confirmations(safe_tx)
            do_execute = (
                len(safe.local_signers) > 0
                and len(signatures) >= safe.confirmations_required
                and click.confirm(f"Submit Transaction {safe_tx.nonce}")
            )
            if do_execute:
                submitter = get_user_selected_account(account_list=safe.local_signers)

        if submitter:
            # NOTE: Signatures may have gotten set above already.
            signatures = signatures or safe.get_api_confirmations(safe_tx)

            exc_tx = safe.create_execute_transaction(safe_tx, signatures)
            submitter.call(exc_tx)


@cli.command(cls=NetworkBoundCommand, short_help="Reject one or more pending transactions")
@safe_cli_ctx
@network_option()
@existing_alias_argument(account_type=SafeAccount)
@click.argument("txn-ids", type=int, nargs=-1)
def reject(cli_ctx: SafeCliContext, network, alias, txn_ids):
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
@safe_cli_ctx
@network_option()
@click.argument("address", type=AddressType)
@click.option("--confirmed", is_flag=True, default=None)
def all_txns(cli_ctx: SafeCliContext, network, address, confirmed):
    _ = network  # Needed for NetworkBoundCommand
    client = cli_ctx.safes._get_client(address)

    for txn in client.get_transactions(confirmed=confirmed):
        if isinstance(txn, ExecutedTxData):
            success_str = "success" if txn.isSuccessful else "revert"
            click.echo(f"Txn {txn.nonce}: {success_str} @ {txn.executionDate}")
        else:
            click.echo(
                f"Txn {txn.nonce}: pending ({len(txn.confirmations)}/{txn.confirmations_required})"
            )
