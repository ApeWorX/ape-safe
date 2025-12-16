# Managing your Safe in Production

When co-managing a Safe with a larger team, ape-safe brings extra tools to the table to help you.

## Queue Scripts

You can define "queue scripts" which are scripts under your project's `scripts/` folder that use
the [`propose_from_simulation`](../methoddocs/cli) decorator in your script.

```{important}
These scripts should follow a recommended naming convention by naming them either
`scripts/nonce<N>.py` or `scripts/<ecosystem>_<network>_nonce<N>.py`).
This will automatically registry with the [queue management](#queue-management)
subcommand that ships with ape-safe.

The value of the nonce `N` must correspond to a specific nonce above the current on-chain contract
value of `nonce` from the Safe, or it will not be collected by the queue management command.
```

An example:

```py
# scripts/nonce<N>.py
from ape_safe.cli import propose_from_simulation


@propose_from_simulation()
def cli():
    # This entire function is executed within a fork/isolated context

    # Use normal Ape features
    my_contract = Contract("<address>")

    # Any transaction is performed as if `sender=safe.address` (using Ape's default sender support)
    my_contract.mutableMethod(...)

    # You can make assertions that will cause your simulation to fail if tripped
    assert my_contract.viewMethod() == ...

    # You can also add conditional calls
    if my_contract.viewMethod() < some_number:
        my_contract.mutableMethod()
```

```{warning}
The callback function **MUST** be named `cli` or it won't work with Ape's script runner.
```

Once the simulation is complete, the decorator will collect all receipts it finds from the `safe`'s
history during that session, and collect them into a single SafeTx to propose to a public network.

```{note}
If only one transaction is detected, it will "condense" that as a direct call,
instead of using `MultiSend` (which is used for >1 detected transactions).
```

The decorated function may have `safe` or `submitter` args in it,
in order to access their values within your simulation.

```{note}
If `submitter` is needed, `safe` must also be present in the args.
```

```py
@propose_from_simulation()
# NOTE: Can also just use `def cli(safe):` if you don't need `submitter`
def cli(safe, submitter):
    # You can use `safe` or `submitter` in your script to query values from the chain
    bal_before = token.balanceOf(submitter)
    amount = token.balanceOf(safe)
    token.transfer(submitter, amount)
    assert token.balanceOf(submitter) == bal_before + amount
```

You can run the script directly using the following command, and it will "dry-run" the `SafeTx`:

```sh
$ ape run nonce<N> your-safe --network ethereum:mainnet-fork --submitter TEST::0
```

## Queue Management

We also provide a command [`ape safe pending ensure`](../../commands/pending#ape-safe-pending-ensure)
that allows you to execute **all** matching queue scripts you have defined in `scripts/`.
This allows you to check side-effects from running all commands in the queue,
helping to reduce human error.

To execute a dry-run of all matching queue scripts for your Safe, execute the following:

```sh
$ ape safe pending ensure --safe your-safe --network ethereum:mainnet-fork --submitter TEST::0
```

Once you are ready, you can "push" your queue scripts to the Safe API via the following:

```sh
$ ape safe pending ensure --safe your-safe --network ethereum:mainnet --submitter local-wallet
```

```{warning}
The wallet you use for `--submitter` must either be one of the signers on the safe, or pre-approved
by the Safe API as a delegate for another signer, otherwise it will fail to propose the new script.
```

```{note}
It is recommended to use our `ensure` command in a secure context, such as Github Actions, where all
scripts can be reviewed by signers, and access is controlled behind Github's access control system.
```

<!-- TODO: Add Github Action for `pending ensure` command? -->

<!-- TODO: Add self-hosting the Safe API w/ `ape safe host`? -->
