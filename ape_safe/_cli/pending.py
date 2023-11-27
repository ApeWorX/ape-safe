from typing import Optional

import click
from ape.api import AccountAPI
from ape.cli import (
    NetworkBoundCommand,
    existing_alias_argument,
    get_user_selected_account,
    network_option,
)
from click.exceptions import BadOptionUsage

from ape_safe._cli.click_ext import SafeCliContext, safe_alias_argument, safe_cli_ctx
from ape_safe.accounts import SafeAccount


@click.group()
def pending():
    """
    Commands for handling pending transactions
    """


@pending.command("list", cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_alias_argument
def _list(cli_ctx: SafeCliContext, network, alias) -> None:
    """
    View pending transactions for a Safe
    """

    _ = network  # Needed for NetworkBoundCommand
    safe = alias  # Handled in callback

    for safe_tx, confirmations in safe.pending_transactions():
        click.echo(
            f"Transaction {safe_tx.nonce}: ({len(confirmations)}/{safe.confirmations_required})"
        )


# NOTE: The handling of the `--execute` flag in the `pending` CLI
#    all happens here EXCEPT if a pending tx is executable and no
#    value of `--execute` was provided.
def _handle_execute_cli_arg(ctx, param, val):
    # Account alias - execute using this account.
    if val is None:
        # Was not given any value.
        # If it is determined in `pending` that a tx can execute,
        # the user will get prompted.
        # Avoid this by always doing `--execute false`.

        return val

    elif val in ctx.obj.account_manager.aliases:
        return ctx.obj.account_manager.load(val)

    # Account address - execute using this account.
    elif val in ctx.obj.account_manager:
        return ctx.obj.account_manager[val]

    # Saying "yes, execute". Use first "local signer".
    elif val.lower() in ("true", "t", "1"):
        safe = ctx.obj.account_manager.load(ctx.params["alias"])
        if not safe.local_signers:
            ctx.obj.abort("Cannot use `--execute TRUE` without a local signer.")

        return get_user_selected_account(account_type=safe.local_signers)

    # Saying "no, do not execute", even if we could.
    elif val.lower() in ("false", "f", "0"):
        return False

    raise BadOptionUsage(
        "--execute", f"`--execute` value '{val}` not a boolean or account identifier."
    )


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_alias_argument
@click.argument("txn_id")
@click.option("--execute", callback=_handle_execute_cli_arg)
def approve(cli_ctx: SafeCliContext, network, alias, txn_id, execute):
    _ = network  # Needed for NetworkBoundCommand
    safe = alias  # Handled in callback
    submitter: Optional[AccountAPI] = execute if isinstance(execute, AccountAPI) else None
    txn = safe.pending_transactions

    #
    # # Add signatures, if was requested to do so.
    #
    # if sign_with_local_signers:
    #     threshold = safe.confirmations_required - 1
    #     num_confirmations = len(confirmations)
    #     if num_confirmations == threshold:
    #         proceed = click.prompt("Additional signatures not required. Proceed?")
    #         if proceed:
    #             safe.add_signatures(safe_tx, confirmations)
    #             cli_ctx.logger.success(f"Signature added to 'Transaction {safe_tx.nonce}'.")
    #
    #     elif num_confirmations < threshold:
    #         safe.add_signatures(safe_tx, confirmations)
    #         cli_ctx.logger.success(f"Signature added to 'Transaction {safe_tx.nonce}'.")
    #
    #     else:
    #         cli_ctx.logger.error("Unable to add signatures. Transaction fully signed.")
    #
    # # NOTE: Lazily check signatures.
    # signatures = None
    #
    # # The user did provider a value for `--execute` however we are able to
    # # So we prompt them.
    # if execute is None and submitter is None:
    #     # Check if we _can_ execute and ask the user.
    #     signatures = safe.get_api_confirmations(safe_tx)
    #     do_execute = (
    #         len(safe.local_signers) > 0
    #         and len(signatures) >= safe.confirmations_required
    #         and click.confirm(f"Submit Transaction {safe_tx.nonce}")
    #     )
    #     if do_execute:
    #         submitter = get_user_selected_account(account_type=safe.local_signers)
    #
    # if submitter:
    #     # NOTE: Signatures may have gotten set above already.
    #     signatures = signatures or safe.get_api_confirmations(safe_tx)
    #
    #     exc_tx = safe.create_execute_transaction(safe_tx, signatures)
    #     submitter.call(exc_tx)


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_alias_argument
@click.argument("txn-ids", type=int, nargs=-1)
def reject(cli_ctx: SafeCliContext, network, alias, txn_ids):
    """
    Reject one or more pending transactions
    """

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
