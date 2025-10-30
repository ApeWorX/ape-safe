import inspect
from typing import TYPE_CHECKING, Callable

import click
from ape.api.accounts import ImpersonatedAccount
from ape.cli import (
    ApeCliContextObject,
    ConnectedProviderCommand,
    account_option,
    ape_cli_context,
    network_option,
)

from ape_safe._cli.click_ext import safe_argument

if TYPE_CHECKING:
    from ape.api import AccountAPI, NetworkAPI

    from ape_safe.accounts import SafeAccount


def propose_from_simulation():
    """
    Create and propose a new SafeTx from transaction receipts inside a fork.

    Usage::

        @propose_from_simulation()
        # NOTE: Name of decorated function *must* be called `cli`
        # NOTE: Decorated function may have `safe` or `submitter` args in it
        def cli():
            # This entire function is executed within a fork/isolated context
            # Use normal Ape features
            my_contract = Contract("<address>")

            # Any transaction is performed as if `sender=safe.address`
            my_contract.mutableMethod(...)

            # You can make assertions that will cause your simulation to fail if tripped
            assert my_contract.viewMethod() == ...

            # You can also add conditional calls
            if my_contract.viewMethod() < some_number:
                my_contract.mutableMethod()

            # Once you are done with your transactions, the simulation will complete after exiting


        # Once the simulation is complete, the decorator will collect all receipts it finds
        # from the `safe` and collect them into a single SafeTx to propose to a public network
    """

    def decorator(
        cmd: (
            Callable[[], None]
            | Callable[["SafeAccount"], None]
            | Callable[["SafeAccount", "AccountAPI"], None]
        ),
    ) -> click.Command:
        args: dict = {}
        parameters = inspect.signature(cmd).parameters
        if "safe" in parameters:
            args["safe"] = None

        if "submitter" in parameters:
            args["submitter"] = None

        if (script_name := cmd.__module__.split(".")[-1]).startswith("nonce"):
            if not script_name[5:].isnumeric():
                raise click.UsageError(
                    f"Script 'scripts/{script_name}.py' must follow 'nonce<N>.py', "
                    "where <N> is convertible to an integer value"
                )

            script_nonce = int(script_name[5:])

        else:
            script_nonce = None  # Auto-determine nonce later

        @click.command(cls=ConnectedProviderCommand, name=cmd.__module__)
        @ape_cli_context()
        @network_option()
        @account_option("--submitter")
        @safe_argument
        def new_cmd(
            cli_ctx: ApeCliContextObject,
            network: "NetworkAPI",
            submitter: "AccountAPI",
            safe: "SafeAccount",
        ):
            if "safe" in args:
                args["safe"] = safe
            if "submitter" in args:
                args["submitter"] = submitter

            # TODO: Use name of script to determine nonce? If starts with `nonce<XXX>.py`
            batch = safe.create_batch()
            total_gas_used = 0

            with (
                cli_ctx.chain_manager.isolate()
                if network.is_fork
                else cli_ctx.network_manager.fork()
            ):
                with cli_ctx.account_manager.use_sender(
                    # NOTE: Use impersonated account to skip processing w/ `SafeAccount`
                    ImpersonatedAccount(raw_address=safe.address)
                ):
                    # NOTE: Make sure the safe has money for gas
                    if not safe.balance:
                        safe.balance += int(1e20)

                    cmd(*args.values())  # NOTE: 1 or more receipts should be mined from calling cmd

                cli_ctx.logger.success(
                    "Simulation complete, collecting receipts into batch to propose"
                )

                for txn in safe.history.sessional:
                    if txn.sender != safe.address:
                        raise RuntimeError("Don't execute other transactions!")

                    elif txn.failed:
                        raise RuntimeError("Transaction failed!")

                    total_gas_used += txn.gas_used
                    batch.add_from_receipt(txn)

                # NOTE: After here, we are exiting the isolation context (either fork or rollback)

            cli_ctx.logger.info(
                f"Collected {len(batch.calls)} receipts into batch (gas used: {total_gas_used})"
            )

            if len(batch.calls) > 1:
                safe_tx = batch.as_safe_tx(nonce=script_nonce)

            else:  # When only one transaction receipt exits, just directly call that
                cli_ctx.logger.info("Only 1 call found, calling directly instead of MultiSend")
                txn = batch.calls[0]
                safe_tx = safe.create_safe_tx(
                    to=txn["target"], value=txn["value"], data=txn["callData"]
                )

            if network.is_fork:  # Testing, execute as a simulation (don't set nonce)
                cli_ctx.logger.info("Using fork network, dry-running SafeTx")
                safe.create_execute_transaction(safe_tx, {}, impersonate=True, submitter=submitter)

            elif not (confirmations := safe.get_api_confirmations(safe_tx)):
                # Real mainnet, propose if not already in queue
                cli_ctx.logger.info("Using public network, proposing SafeTx to Safe API")
                safe.propose_safe_tx(safe_tx, submitter=submitter)

                safe_tx_id = safe_tx._message_hash_
                cli_ctx.logger.success("'{safe_tx_id.to_0x_hex()}' proposed to queue")

            else:
                safe_tx_id = safe_tx._message_hash_
                cli_ctx.logger.info(
                    f"SafeTxID '{safe_tx_id.to_0x_hex()}' already in queue "
                    f"({len(confirmations)}/{safe.confirmations_required})"
                )

        new_cmd.help = cmd.__doc__
        return new_cmd

    return decorator
