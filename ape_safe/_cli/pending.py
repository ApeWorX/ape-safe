from typing import Optional

import click
import rich
from ape.api import AccountAPI
from ape.cli import NetworkBoundCommand, get_user_selected_account, network_option
from click.exceptions import BadOptionUsage
from hexbytes import HexBytes

from ape_safe._cli.click_ext import SafeCliContext, safe_cli_ctx, safe_option


@click.group()
def pending():
    """
    Commands for handling pending transactions
    """


@pending.command("list", cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
def _list(cli_ctx: SafeCliContext, network, safe) -> None:
    """
    View pending transactions for a Safe
    """

    _ = network  # Needed for NetworkBoundCommand
    tx = None
    for tx in safe.client.get_transactions(confirmed=False):
        rich.print(
            f"Transaction {tx.nonce}: "
            f"({len(tx.confirmations)}/{safe.confirmations_required}) "
            f"safe_tx_hash={tx.safe_tx_hash}"
        )

    if tx is None:
        rich.print("There are no pending transactions.")


# NOTE: The handling of the `--execute` flag in the `pending` CLI
#    all happens here EXCEPT if a pending tx is executable and no
#    value of `--execute` was provided.
def _handle_execute_cli_arg(ctx, param, val):
    """
    Either returns the account or ``False`` meaning don't execute
    """

    if val is None:
        # Was not given any value.
        # If it is determined in `pending` that a tx can execute,
        # the user will get prompted.
        # Avoid this by always doing `--execute false`.
        return None

    elif submitter := _load_submitter(ctx, param, val):
        return submitter

    # Saying "no, do not execute", even if we could.
    elif val.lower() in ("false", "f", "0"):
        return False

    raise BadOptionUsage(
        "--execute", f"`--execute` value '{val}` not a boolean or account identifier."
    )


def _load_submitter(ctx, param, val):
    if val in ctx.obj.account_manager.aliases:
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

    return None


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@click.argument("nonce", type=int)
@click.option("--execute", callback=_handle_execute_cli_arg)
def approve(cli_ctx: SafeCliContext, network, safe, nonce, execute):
    _ = network  # Needed for NetworkBoundCommand
    submitter: Optional[AccountAPI] = execute if isinstance(execute, AccountAPI) else None
    if not (txn := safe.client.get_transaction(nonce, confirmed=False)):
        cli_ctx.abort(f"Pending transaction '{nonce}' not found.")

    safe_tx = safe.create_safe_tx(**txn.dict(by_alias=True))
    num_confirmations = len(txn.confirmations)
    signatures_added = {}

    if num_confirmations < safe.confirmations_required:
        signatures_added = safe.add_signatures(safe_tx, txn.confirmations)
        if signatures_added:
            accounts_used_str = ", ".join(list(signatures_added.keys()))
            cli_ctx.logger.success(
                f"Signatures added to transaction '{safe_tx.nonce}' "
                f"using accounts '{accounts_used_str}'."
            )
            num_confirmations += len(signatures_added)

    if execute is None and submitter is None:
        # Check if we _can_ execute and ask the user.
        do_execute = (
            len(safe.local_signers) > 0
            and num_confirmations >= safe.confirmations_required
            and click.confirm(f"Submit transaction '{safe_tx.nonce}'")
        )
        if do_execute:
            # The user did provider a value for `--execute` however we are able to
            # So we prompt them.
            submitter = get_user_selected_account(account_type=safe.local_signers)

    if submitter:
        signatures = {c.owner: c.signature for c in txn.confirmations}
        signatures = {**signatures, **signatures_added}
        exc_tx = safe.create_execute_transaction(safe_tx, signatures)
        submitter.call(exc_tx)


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@click.argument("nonce", type=int)
@click.option("--submitter", callback=_load_submitter)
def execute(cli_ctx, network, safe, nonce, submitter):
    """
    Execute a transaction
    """
    if not (txn := safe.client.get_transaction(nonce, confirmed=False)):
        cli_ctx.abort(f"Pending transaction '{nonce}' not found.")

    safe_tx = safe.create_safe_tx(**txn.dict(by_alias=True))
    signatures = {c.owner: c.signature for c in txn.confirmations}
    exc_tx = safe.create_execute_transaction(safe_tx, signatures)
    submitter.call(exc_tx)


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@click.argument("txn-ids", type=int, nargs=-1)
def reject(cli_ctx: SafeCliContext, network, safe, txn_ids):
    """
    Reject one or more pending transactions
    """

    _ = network  # Needed for NetworkBoundCommand
    pending_transactions = safe.client.get_transaction(confirmed=False, nonce=safe.next_nonce)

    for txn_id in txn_ids:
        try:
            txn = next(txn for txn in pending_transactions if txn_id == txn.nonce)
        except StopIteration:
            # NOTE: Not a pending transaction.
            continue

        if click.confirm(f"{txn}\nCancel Transaction?"):
            safe.transfer(safe, "0 ether", nonce=txn_id, submit_transaction=False)


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@click.argument("nonce", type=int)
def show_confs(cli_ctx, network, safe, nonce):
    """
    Show existing confirmations
    """
    _ = network  # Needed for NetworkBoundCommand
    if not (txn := safe.client.get_transaction(nonce, confirmed=False)):
        cli_ctx.abort(f"Pending transaction '{nonce}' not found.")

    rich.print(f"Showing confirmations for transaction '{txn.nonce}'")
    length = len(txn.confirmations)
    for idx, conf in enumerate(txn.confirmations):
        rich.print(
            f"Confirmation {idx + 1} owner={conf.owner} signature={HexBytes(conf.signature).hex()}"
        )
        if idx < length - 1:
            click.echo()
