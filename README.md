# Quick Start

Account plugin for the [Safe](https://safe.global//) Multisig wallet (previously known as Gnosis Safe).

## Dependencies

- [python3](https://www.python.org/downloads) version 3.8 up to 3.11.

## Installation

### via `ape`

You can install using the [ape](https://github.com/ApeWorX/ape) built-in plugin manager:

```bash
$ ape plugins install safe
```

### via `pip`

You can install the latest release via [`pip`](https://pypi.org/project/pip/):

```bash
$ pip install ape-safe
```

### via `setuptools`

You can clone the repository and use [`setuptools`](https://github.com/pypa/setuptools) for the most up-to-date version:

```bash
$ git clone https://github.com/ApeWorX/ape-safe.git
$ cd ape-safe
$ python3 setup.py install
```

## Quick Usage

To use the plugin, first use the CLI extension to add a safe you created:

```sh
ape safe add --network ethereum:mainnet "my-safe.eth" my-safe
```

If you made a mistake or just need to remove the safe, use the `remove` command:

```sh
ape safe remove my-safe --yes
```

**NOTE** `--yes` is a way to skip the prompt.

If you only add one safe, you will not have to specify which safe to use other commands.
Otherwise, for most `pending` commands, you specify the safe to use (by alias) via the `--safe` option.

Additionally, you can configure a safe to use as the default in your `ape-config.yaml` file:

```yaml
safe:
  default_safe: my-safe
```

**NOTE**: Also, to avoid always needing to specify `--network`, you can set a default ecosystem, network, and provider in your config file.
The rest of the guide with not specify `--network` on each command but assume the correct one is set in the config file.
Here is an example:

```yaml
default_ecosystem: optimism

ethereum:
  default_network: sepolia
  sepolia:
    default_provider: infura
```

Once you have a safe, you can view pending transactions:

```sh
ape safe pending list
```

It should show transactions like this:

```sh
Transaction 8 rejection (1/2) safe_tx_hash=0x09ab9a229fc60da66ec0fa8fa886ab7c95902fdf5df5a5009ba06010fbb9a9a7
Transaction 8 transfer  (1/2) safe_tx_hash=0xed43d80255bcd5ffacb755e8f51bee825913373705d6baea006419d2a33a0a5b
```

**NOTE**: Use the `--verbose` flag to see more information about each transaction.

```sh
ape safe pending list --verbose
```

There are several operations you can do on a pending transaction.
One of them is "approve" which adds your local signers' signatures to the transaction.

```sh
ape safe pending approve 0x09ab9a229fc60da66ec0fa8fa886ab7c95902fdf5df5a5009ba06010fbb9a9a7
```

**NOTE**: Here we are using the transaction hash `0x09ab9a229fc60da66ec0fa8fa886ab7c95902fdf5df5a5009ba06010fbb9a9a7` to specify the transaction because there are more than one.
However, you can also use the nonce if there is only a single transaction.

If you want to both execute and approve at the same time, you can use the `--execute` option on approve and specify a sender:

```sh
ape safe pending approve 2 --execute my_account
```

Else, you can use the `execute` command directly:

```sh
ape safe pending execute 2
```

**NOTE**: `execute` requires a full signed transaction ready to be submitted on-chain.

The last main operation is `reject`.
Rejecting a transaction replaces that transaction with a zero-value transfer from the safe to itself.

```sh
ape safe pending reject 2
```

### Multisend

The following example shows how to use multisend:

```python
from ape_safe import multisend
from ape import accounts
from ape_tokens import tokens

safe = accounts.load("my-safe")

# Load some contracts (here using ape-tokens)
dai = tokens["DAI"]
vault = tokens["yvDAI"]
amount = dai.balanceOf(safe)  # How much we want to deposit

# Create a multisend transaction (a transaction that executes multiple calls)
txn = multisend.Transaction()
txn.add(dai.approve, vault, amount)
txn.add(vault.deposit, amount)

# Fetch signatures from any local signers, and broadcast if confirmations are met
# Otherwise, it will post the partially confirmed message to Safe Global's API
txn(sender=safe)
```

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## Acknowledgements

This package was inspired by [the original ape-safe](https://github.com/banteg/ape-safe#readme) by [banteg](https://github.com/banteg).
For versions prior to v0.6.0, the original package should be referenced.
