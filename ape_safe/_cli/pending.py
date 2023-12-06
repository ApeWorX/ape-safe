from typing import Dict, List, Optional, Sequence, Union

import click
import rich
from ape.api import AccountAPI
from ape.cli import NetworkBoundCommand, get_user_selected_account, network_option
from ape.exceptions import SignatureError
from click.exceptions import BadOptionUsage
from hexbytes import HexBytes

from ape_safe import SafeAccount
from ape_safe._cli.click_ext import SafeCliContext, safe_cli_ctx, safe_option, txn_ids_argument
from ape_safe.client import UnexecutedTxData


@click.group()
def pending():
    """
    Commands for handling pending transactions
    """


@pending.command("list", cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@click.option("--show-confs", is_flag=True)
def _list(cli_ctx: SafeCliContext, network, safe, show_confs) -> None:
    """
    View pending transactions for a Safe
    """

    _ = network  # Needed for NetworkBoundCommand
    txns = list(safe.client.get_transactions(confirmed=False))
    if not txns:
        rich.print("There are no pending transactions.")
        return

    txns_by_nonce: Dict[int, List[UnexecutedTxData]] = {}
    for txn in txns:
        if txn.nonce in txns_by_nonce:
            txns_by_nonce[txn.nonce].append(txn)
        else:
            txns_by_nonce[txn.nonce] = [txn]

    all_items = txns_by_nonce.items()
    total_items = len(all_items)
    for root_idx, (nonce, tx_list) in enumerate(all_items):
        tx_len = len(tx_list)
        for idx, tx in enumerate(tx_list):
            title = f"Transaction {nonce}"
            is_rejection = not tx.value and not tx.data and tx.to == tx.safe
            operation_name = tx.operation.name if tx.data else "transfer"
            if is_rejection:
                title = f"{title} rejection"
            else:
                title = f"{title} {operation_name}"

            confirmations = tx.confirmations
            rich.print(
                f"{title} "
                f"({len(confirmations)}/{safe.confirmations_required}) "
                f"safe_tx_hash={tx.safe_tx_hash}"
            )

            if show_confs:
                _show_confs(tx.confirmations, extra_line=False)
                if root_idx < total_items - 1 or idx < tx_len - 1:
                    click.echo()


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
@txn_ids_argument
@click.option("--execute", callback=_handle_execute_cli_arg)
def approve(cli_ctx: SafeCliContext, network, safe, txn_ids, execute):
    _ = network  # Needed for NetworkBoundCommand
    submitter: Optional[AccountAPI] = execute if isinstance(execute, AccountAPI) else None
    pending_transactions = list(
        safe.client.get_transactions(confirmed=False, starting_nonce=safe.next_nonce)
    )
    for txn in pending_transactions:
        # Figure out which given ID(s) we are handling.
        length_before = len(txn_ids)
        txn_ids = _check_tx_ids(txn_ids, txn)
        if len(txn_ids) == length_before:
            # Not a specified txn.
            continue

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

    # If any txn_ids remain, they were not handled.
    if txn_ids:
        cli_ctx.abort_txns_not_found(txn_ids)


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@txn_ids_argument
@click.option("--submitter", callback=_load_submitter)
def execute(cli_ctx, network, safe, txn_ids, submitter):
    """
    Execute a transaction
    """
    pending_transactions = list(
        safe.client.get_transactions(confirmed=False, starting_nonce=safe.next_nonce)
    )
    for txn in pending_transactions:
        # Figure out which given ID(s) we are handling.
        length_before = len(txn_ids)
        txn_ids = _check_tx_ids(txn_ids, txn)
        if len(txn_ids) == length_before:
            # Not a specified txn.
            continue

        _execute(safe, txn, submitter)

    # If any txn_ids remain, they were not handled.
    if txn_ids:
        cli_ctx.abort_txns_not_found(txn_ids)


def _execute(safe: SafeAccount, txn: UnexecutedTxData, submitter: AccountAPI):
    safe_tx = safe.create_safe_tx(**txn.dict(by_alias=True))
    signatures = {c.owner: c.signature for c in txn.confirmations}

    # NOTE: We have a hack that allows bytes in the mapping, hence type ignore
    exc_tx = safe.create_execute_transaction(safe_tx, signatures)  # type: ignore

    submitter.call(exc_tx)


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@txn_ids_argument
def reject(cli_ctx: SafeCliContext, network, safe, txn_ids):
    """
    Reject one or more pending transactions
    """

    _ = network  # Needed for NetworkBoundCommand
    pending_transactions = safe.client.get_transactions(
        confirmed=False, starting_nonce=safe.next_nonce
    )

    for txn in pending_transactions:
        # Figure out which given ID(s) we are handling.
        length_before = len(txn_ids)
        txn_ids = _check_tx_ids(txn_ids, txn)
        if len(txn_ids) == length_before:
            # Not a specified txn.
            continue

        is_rejection = not txn.value and not txn.data and txn.to == txn.safe
        if is_rejection:
            click.echo(f"Transaction '{txn.safe_tx_hash}' already canceled!")
            continue

        elif click.confirm(f"{txn}\nCancel Transaction?"):
            try:
                safe.transfer(safe, "0 ether", nonce=txn.nonce, submit_transaction=False)
            except SignatureError:
                # These are expected because of how the plugin works
                # when not submitting
                pass

            cli_ctx.logger.success(f"Canceled transaction '{txn.safe_tx_hash}'.")

    # If any txn_ids remain, they were not handled.
    if txn_ids:
        cli_ctx.abort_txns_not_found(txn_ids)


@pending.command(cls=NetworkBoundCommand)
@safe_cli_ctx
@network_option()
@safe_option
@click.argument("txn_id")
def show_confs(cli_ctx, network, safe, txn_id):
    """
    Show existing confirmations
    """
    _ = network  # Needed for NetworkBoundCommand

    if txn_id.isnumeric():
        nonce = int(txn_id)

        # NOTE: May be more than 1 if conflicting transactions
        txns = list(
            safe.client.get_transactions(starting_nonce=nonce, ending_nonce=nonce, confirmed=False)
        )
    else:
        txns = list(safe.client.get_transactions(filter_by_ids=txn_id, confirmed=False))

    if not txns:
        cli_ctx.abort_txns_not_found([txn_id])

    num_txns = len(txns)
    for root_idx, txn in enumerate(txns):
        header = f"Showing confirmations for transaction '{txn.nonce}'"
        operation_name = txn.operation.name if txn.data else "transfer"
        is_rejection = not txn.value and not txn.data and txn.to == txn.safe
        if is_rejection:
            header = f"{header} rejection"
        else:
            header = f"{header} {operation_name}"

        rich.print(header)
        _show_confs(txn.confirmations)
        if root_idx < num_txns - 1:
            click.echo()


def _show_confs(confs, extra_line: bool = True):
    length = len(confs)
    for idx, conf in enumerate(confs):
        rich.print(
            f"Confirmation {idx + 1} owner={conf.owner} signature={HexBytes(conf.signature).hex()}"
        )
        if extra_line and idx < length - 1:
            click.echo()


def _check_tx_ids(
    txn_ids: Sequence[Union[int, str]], txn: UnexecutedTxData
) -> Sequence[Union[int, str]]:
    if txn.nonce in txn_ids:
        return [x for x in txn_ids if x != txn.nonce]

    # Handle if given nonce and hash for same txn.
    if txn.safe_tx_hash in txn_ids:
        return [x for x in txn_ids if x != txn.nonce]

    return txn_ids
