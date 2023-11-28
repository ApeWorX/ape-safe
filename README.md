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

```bash
ape safe add --network ethereum:mainnet "my-safe.eth" my-safe
```

If you only add 1 safe, you will not have to specify in future commands.
Otherwise, for most commands, specify the safe using the `--safe` option by alias.

Once you've added a safe, you manage pending transactions:

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

You can use the CLI extension to view and sign for pending transactions:

```bash
ape safe pending list --network ethereum:goerli:alchemy
ape safe pending show-confs 2 --network ethereum:goerli:alchemy
ape safe pending approve 3 --network ethereum:goerli:alchemy
ape safe pending reject 4 --network ethereum:goerli:alchemy
```

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## Acknowledgements

This package was inspired by [the original ape-safe](https://github.com/banteg/ape-safe#readme) by [banteg](https://github.com/banteg).
For versions prior to v0.6.0, the original package should be referenced.
