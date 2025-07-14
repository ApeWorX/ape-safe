# Overview

Account plugin for the [Safe](https://safe.global/) multisig wallet (previously known as Gnosis Safe) for the [Ape Framework](https://github.com/ApeWorX/ape).

## Features

- **Safe Account Management**: Add, list, and remove Safe multisig wallets
- **Transaction Management**: Create, propose, sign, and execute Safe transactions
- **Multisig Workflows**: Manage transaction approval workflows with multiple signers
- **MultiSend Support**: Batch multiple transactions together efficiently
- **CLI Interface**: Comprehensive command line tools for Safe management
- **Python API**: Programmatic access to all Safe functionality

## Dependencies

- [python3](https://www.python.org/downloads) version 3.9 or newer

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

or via `pyproject.toml`:

```toml
[tool.ape.safe]
default_safe = "my-safe"
```

To specify via environment variable, do:

```sh
APE_SAFE_DEFAULT_SAFE="my-safe"
```

**NOTE**: To avoid always needing to specify `--network`, you can set a default ecosystem, network, and provider in your config file.
Here is an example:

```yaml
default_ecosystem: ethereum

ethereum:
  default_network: mainnet
  mainnet:
    default_provider: infura
```

The rest of the guide will not specify `--network` on each command but assume the correct one is set in the config file.

---

Once you have a safe, you can view pending transactions:

```sh
ape safe pending list
```

```{note}
You must specify the environment variable `APE_SAFE_GATEWAY_API_KEY=` to use the Safe Gateway API.
Get an API key at https://developer.safe.global/.
```

It should show transactions like this:

```sh
Transaction 8 rejection (1/2) safe_tx_hash=0x09ab9a229fc60da66ec0fa8fa886ab7c95902fdf5df5a5009ba06010fbb9a9a7
Transaction 8 transfer  (1/2) safe_tx_hash=0xed43d80255bcd5ffacb755e8f51bee825913373705d6baea006419d2a33a0a5b
```

Use the `--verbose` flag to see more information about each transaction:

```sh
ape safe pending list --verbose
```

There are several operations you can do on a pending transaction:

```sh
# Approve a transaction (add your signature)
ape safe pending approve 0x09ab9a229fc60da66ec0fa8fa886ab7c95902fdf5df5a5009ba06010fbb9a9a7

# Approve and execute in one step
ape safe pending approve 2 --execute my_account

# Execute a fully signed transaction
ape safe pending execute 2

# Reject a transaction
ape safe pending reject 2
```

## MultiSend Example

The following example shows how to use multisend to batch transactions:

```python
from ape_safe import multisend
from ape import accounts
from ape_tokens import tokens

safe = accounts.load("my-safe")

# Load some contracts using ape-tokens
dai = tokens["DAI"]
vault = tokens["yvDAI"]
amount = dai.balanceOf(safe)  # How much we want to deposit

# Create a multisend transaction (a transaction that executes multiple calls)
txn = multisend.MultiSend()
txn.add(dai.approve, vault, amount)
txn.add(vault.deposit, amount)

# Fetch signatures from local signers and broadcast if confirmations are met
txn(sender=safe, gas=0)
```

<<<<<<< HEAD

## Cloud Usage

To use this plugin in a cloud environment, such as with the [Silverback Platform](https://silverback.apeworx.io), you will need to make sure that you have configured your Safe to exist within the environment.
The easiest way to do this is to use the `require` configuration item.
To specify a required Safe in your `ape-config.yaml` (which adds it into your `~/.ape/safe` folder if it doesn't exist), use:

```yaml
safe:
  require:
    my-safe:
      address: "0x1234...AbCd"
      deployed_chain_ids: [1, ...]
```

or in `pyproject.toml`:

```toml
[tool.ape.safe.require."my-safe"]
address = "0x1234...AbCd"
deployed_chain_ids = [1, ...]
```

To specify via environment variable, do:

```sh
APE_SAFE_REQUIRE='{"my-safe":{"address":"0x1234...AbCd","deployed_chain_ids":[1,...]}}'
```

```{notice}
If a safe with the same alias as an entry in `require` exists in your local environment, this will skip adding it, even if the existing alias points to a different address than the one in the config item.
```

=======

## Documentation

For more detailed documentation, see:

- [Setup](./docs/setup.md) - Configuration and initial setup
- [Basic Usage](./docs/basic_usage.md) - Essential operations
- [Safe Management](./docs/safe_management.md) - Adding, listing and removing Safes
- [Transaction Workflows](./docs/transactions.md) - Understanding the transaction lifecycle
- [MultiSend](./docs/multisend.md) - Batching transactions
- [CLI Reference](./docs/cli.md) - Command line interface documentation
- [API Reference](./docs/api.md) - Python API documentation
  > > > > > > > 1a59826 (docs: create comprehensive modern documentation)

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## Acknowledgements

This package was inspired by the original ape-safe, now [brownie-safe](https://github.com/banteg/brownie-safe) by [banteg](https://github.com/banteg).
For versions prior to v0.6.0, the original package should be referenced.
