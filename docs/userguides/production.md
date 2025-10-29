# Managing your Safe in Production

When co-managing a Safe with a larger team, ape-safe brings extra tools to the table to help you.

## Queue Scripts

You can define "queue scripts" which are scripts under your project's `scripts/` folder that follow
a naming convention (either `scripts/nonce<N>.py` or `scripts/<ecosystem>_<network>_nonce<N>.py`),
and then use the [`propose_from_simulation`](../../methoddocs/cli) decorator.

```{note}
The value of the nonce `N` must correspond to a specific nonce above the current on-chain
value of `nonce` from the safe, or it will not be recognized by our other queue management command.
```

An example:

```py
from ape_safe.cli import propose_from_simulation


@propose_from_simulation()
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
```

Once the simulation is complete, the decorator will collect all receipts it finds from the `safe`'s
history during that session, and collect them into a single SafeTx to propose to a public network.

```{note}
The name of the decorated function in your queue script **must** be `cli` for it to work.
```

```{note}
The decorated function may have `safe` or `submitter` args in it, in order to access their values.
```

You can run the script directly using the following command, and it will dry-run the transaction:

```sh
$ ape run nonce<N> your-safe --network ethereum:mainnet-fork --submitter TEST::0
```

We also provide a command [`ape safe pending ensure`](../../commands/pending#ape-safe-pending-ensure)
that allows you to execute all matching nonce commands up to the latest you have defined in sequence.
This allows you to check for side-effects of commands in the queue, helping to reduce human error.

To execute a dry-run of all matching queue scripts for your safe, execute the following:

```sh
$ ape safe pending ensure --safe your-safe --network ethereum:mainnet-fork --submitter TEST::0
```

Once you are ready, you can "propose" your queue script to the Safe API via the following:

```sh
$ ape run nonce<N> your-safe --network ethereum:mainnet --submitter local-wallet
```

You can also propose all of your queue scripts (if there are discrepencies) to the Safe API via:

```sh
$ ape safe pending ensure --safe your-safe --network ethereum:mainnet --submitter local-wallet
```

```{warning}
The wallet you use for `--submitter` must either be one of the signers on the safe, or pre-approved
by the Safe API as a delegate for another signer, otherwise it will fail to propose the new script.
```

```{note}
It is recommended to use our ensure command in a secure context, such as Github Actions, where all
scripts can be reviewed by signers, and access is controlled behind Github's access control system.
```

<!-- TODO: Add Github Action? -->

<!-- TODO: Add self-hosted API? -->
