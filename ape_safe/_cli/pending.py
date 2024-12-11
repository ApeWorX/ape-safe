from collections.abc import Sequence
from typing import TYPE_CHECKING, Optional, Union, cast

import click
import rich
from ape.cli import ConnectedProviderCommand
from ape.exceptions import SignatureError
from eth_typing import ChecksumAddress, Hash32
from eth_utils import humanize_hash, to_hex
from hexbytes import HexBytes

from ape_safe._cli.click_ext import (
    SafeCliContext,
    execute_option,
    safe_cli_ctx,
    safe_option,
    sender_option,
    submitter_option,
    txn_ids_argument,
)

if TYPE_CHECKING:
    from ape.api import AccountAPI

    from ape_safe.accounts import SafeAccount
    from ape_safe.client import UnexecutedTxData


@click.group()
def pending():
    """
    Commands for handling pending transactions
    """


@pending.command("list", cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@click.option("--verbose", is_flag=True)
def _list(cli_ctx, safe, verbose) -> None:
    """
    View pending transactions for a Safe
    """

    txns = list(safe.client.get_transactions(starting_nonce=safe.next_nonce, confirmed=False))
    if not txns:
        rich.print("There are no pending transactions.")
        return

    txns_by_nonce: dict[int, list[UnexecutedTxData]] = {}
    for txn in txns:
        if txn.nonce in txns_by_nonce:
            txns_by_nonce[txn.nonce].append(txn)
        else:
            txns_by_nonce[txn.nonce] = [txn]

    all_items = txns_by_nonce.items()
    total_items = len(all_items)
    max_op_len = len("rejection")
    for root_idx, (nonce, tx_list) in enumerate(all_items):
        tx_len = len(tx_list)
        for idx, tx in enumerate(tx_list):
            title = f"Transaction {nonce}"
            is_rejection = not tx.value and not tx.data and tx.to == tx.safe
            operation_name = tx.operation.name if tx.data else "transfer"
            if is_rejection:
                operation_name = "rejection"

            # Add spacing (unless verbose) so columns are aligned.
            spaces = "" if verbose else (max(0, max_op_len - len(operation_name))) * " "
            title = f"{title} {operation_name}{spaces}"
            confirmations = tx.confirmations
            rich.print(
                f"{title} "
                f"({len(confirmations)}/{safe.confirmations_required}) "
                f"safe_tx_hash={tx.safe_tx_hash}"
            )

            if verbose:
                fields = ("to", "value", "data", "base_gas", "gas_price")
                data = {}
                for field_name, value in tx.model_dump(by_alias=True, mode="json").items():
                    if field_name not in fields:
                        continue

                    if field_name in ("data",) and not value:
                        value = "0x"
                    elif not value:
                        value = "0"

                    if isinstance(value, bytes):
                        value_str = str(to_hex(HexBytes(value)))
                    else:
                        value_str = f"{value}"

                    if len(value_str) > 42:
                        value_str = f"{humanize_hash(cast(Hash32, HexBytes(value_str)))}"

                    data[field_name] = value_str

                data_str = ", ".join([f"{k}={v}" for k, v in data.items()])
                rich.print(f"\t{data_str}")
                _show_confs(tx.confirmations, extra_line=False, prefix="\t")
                if root_idx < total_items - 1 or idx < tx_len - 1:
                    click.echo()


@pending.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@click.option("--data", type=HexBytes, help="Transaction data", default=HexBytes(""))
@click.option("--gas-price", type=int, help="Transaction gas price")
@click.option("--value", type=int, help="Transaction value", default=0)
@click.option("--to", "receiver", type=ChecksumAddress, help="Transaction receiver")
@click.option("--nonce", type=int, help="Transaction nonce")
@sender_option
@click.option("--execute", help="Execute if possible after proposal", is_flag=True)
def propose(cli_ctx, ecosystem, safe, data, gas_price, value, receiver, nonce, sender, execute):
    """
    Create a new transaction
    """
    from ape.api import AccountAPI

    from ape_safe.accounts import get_signatures
    from ape_safe.utils import get_safe_tx_hash

    nonce = safe.new_nonce if nonce is None else nonce
    txn = ecosystem.create_transaction(
        value=value,
        data=data,
        gas_price=gas_price,
        nonce=nonce,
        receiver=receiver,
    )
    safe_tx = safe.create_safe_tx(txn)
    safe_tx_hash = get_safe_tx_hash(safe_tx)
    signatures = get_signatures(safe_tx, safe.local_signers)

    num_confirmations = 0
    submitter = sender if isinstance(sender, AccountAPI) else None
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
            submitter = safe.select_signer(for_="submitter")

    sender = submitter if isinstance(submitter, AccountAPI) else safe.select_signer(for_="sender")
    safe.client.post_transaction(
        safe_tx, signatures, sender=sender.address, contractTransactionHash=safe_tx_hash
    )

    # Wait for new transaction to appear
    timeout = 3
    new_tx = None

    while new_tx is None and timeout > 0:
        new_tx = next(
            safe.client.get_transactions(
                starting_nonce=safe.next_nonce, confirmed=False, filter_by_ids=[safe_tx_hash]
            ),
            None,
        )
        timeout -= 1

    if new_tx:
        cli_ctx.logger.success(f"Proposed transaction '{safe_tx_hash}'.")
    else:
        cli_ctx.abort("Failed to propose transaction.")

    if execute:
        _execute(safe, new_tx, sender)


@pending.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@txn_ids_argument
@execute_option
def approve(cli_ctx: SafeCliContext, safe, txn_ids, execute):
    from ape.api import AccountAPI

    from ape_safe.utils import get_safe_tx_hash

    submitter: Optional[AccountAPI] = execute if isinstance(execute, AccountAPI) else None
    pending_transactions = list(
        safe.client.get_transactions(confirmed=False, starting_nonce=safe.next_nonce)
    )
    for txn in pending_transactions:
        # Figure out which given ID(s) we are handling.
        length_before = len(txn_ids)
        txn_ids = _filter_tx_from_ids(txn_ids, txn)
        if len(txn_ids) == length_before:
            # Not a specified txn.
            continue

        safe_tx = safe.create_safe_tx(**txn.model_dump(by_alias=True, mode="json"))
        num_confirmations = len(txn.confirmations)

        if num_confirmations < safe.confirmations_required:
            signatures_added = safe.add_signatures(safe_tx, confirmations=txn.confirmations)
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
                submitter = safe.select_signer(for_="submitter")

        if submitter:
            safe_tx_hash = get_safe_tx_hash(safe_tx)
            txn.confirmations = safe.client.get_confirmations(safe_tx_hash)
            _execute(safe, txn, submitter)

    # If any txn_ids remain, they were not handled.
    if txn_ids:
        cli_ctx.abort_txns_not_found(txn_ids)


@pending.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@txn_ids_argument
# NOTE: Doesn't use --execute because we don't need BOOL values.
@submitter_option
@click.option("--nonce", help="Submitter nonce")
def execute(cli_ctx, safe, txn_ids, submitter, nonce):
    """
    Execute a transaction
    """
    pending_transactions = list(
        safe.client.get_transactions(confirmed=False, starting_nonce=safe.next_nonce)
    )

    if not submitter:
        submitter = safe.select_signer(for_="submitter")

    for txn in pending_transactions:
        # Figure out which given ID(s) we are handling.
        length_before = len(txn_ids)
        txn_ids = _filter_tx_from_ids(txn_ids, txn)
        if len(txn_ids) == length_before:
            # Not a specified txn.
            continue

        _execute(safe, txn, submitter, nonce=nonce)

    # If any txn_ids remain, they were not handled.
    if txn_ids:
        cli_ctx.abort_txns_not_found(txn_ids)


def _execute(safe: "SafeAccount", txn: "UnexecutedTxData", submitter: "AccountAPI", **tx_kwargs):
    # perf: Avoid these imports during CLI load time for `ape --help` performance.
    from ape.types import AddressType, MessageSignature

    safe_tx = safe.create_safe_tx(**txn.model_dump(mode="json", by_alias=True))
    signatures: dict[AddressType, MessageSignature] = {
        c.owner: MessageSignature.from_rsv(c.signature) for c in txn.confirmations
    }
    exc_tx = safe.create_execute_transaction(safe_tx, signatures, **tx_kwargs)
    submitter.call(exc_tx)


@pending.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@txn_ids_argument
@execute_option
def reject(cli_ctx: SafeCliContext, safe, txn_ids, execute):
    """
    Reject one or more pending transactions
    """
    from ape.api import AccountAPI

    submit = False if execute in (False, None) else True
    submitter = execute if isinstance(execute, AccountAPI) else None
    if submitter is None and submit:
        submitter = safe.select_signer(for_="submitter")

    pending_transactions = safe.client.get_transactions(
        confirmed=False, starting_nonce=safe.next_nonce
    )

    for txn in pending_transactions:
        # Figure out which given ID(s) we are handling.
        length_before = len(txn_ids)
        txn_ids = _filter_tx_from_ids(txn_ids, txn)
        if len(txn_ids) == length_before:
            # Not a specified txn.
            continue

        is_rejection = not txn.value and not txn.data and txn.to == txn.safe
        if is_rejection:
            click.echo(f"Transaction '{txn.safe_tx_hash}' already canceled!")
            continue

        elif click.confirm(f"{txn}\nCancel Transaction?"):
            try:
                safe.transfer(
                    safe, 0, nonce=txn.nonce, submit_transaction=submit, submitter=submitter
                )
            except SignatureError:
                # These are expected because of how the plugin works
                # when not submitting
                pass

            cli_ctx.logger.success(f"Canceled transaction '{txn.safe_tx_hash}'.")

    # If any txn_ids remain, they were not handled.
    if txn_ids:
        cli_ctx.abort_txns_not_found(txn_ids)


@pending.command(cls=ConnectedProviderCommand)
@safe_cli_ctx()
@safe_option
@click.argument("txn_id")
def show_confs(cli_ctx, safe, txn_id):
    """
    Show existing confirmations
    """

    if txn_id.isnumeric():
        nonce = int(txn_id)

        # NOTE: May be more than 1 if conflicting transactions
        txns = list(
            safe.client.get_transactions(starting_nonce=nonce, ending_nonce=nonce, confirmed=False)
        )
    else:
        txns = list(
            safe.client.get_transactions(
                starting_nonce=safe.next_nonce, filter_by_ids=txn_id, confirmed=False
            )
        )

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


def _show_confs(confs, extra_line: bool = True, prefix: Optional[str] = None):
    prefix = prefix or ""
    length = len(confs)
    for idx, conf in enumerate(confs):
        signature_str = f"[default]{humanize_hash(conf.signature)}[/default]"
        rich.print(f"{prefix}Confirmation {idx + 1} owner={conf.owner} signature='{signature_str}'")
        if extra_line and idx < length - 1:
            click.echo()


# Helper method for handling transactions in a loop.
def _filter_tx_from_ids(
    txn_ids: Sequence[Union[int, str]], txn: "UnexecutedTxData"
) -> Sequence[Union[int, str]]:
    if txn.nonce in txn_ids:
        # Filter out all transactions with the same nonce
        return [x for x in txn_ids if x != txn.nonce]

    # Handle if given nonce and hash for same txn.
    if txn.safe_tx_hash in txn_ids:
        return [x for x in txn_ids if x != txn.safe_tx_hash]

    return txn_ids
