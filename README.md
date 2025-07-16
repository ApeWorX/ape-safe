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

To use the plugin, first use the Ape CLI extension to add a safe you want to control:

```sh
# ape safe add ADDRESS ALIAS
ape safe add --network ethereum:mainnet my-safe.eth my-safe
```

If you made a mistake or just need to remove the safe, use the `remove` command:

```sh
# ape safe remove ALIAS
ape safe remove my-safe --yes
```

```{note}
`--yes` is a way to skip the prompt.
```

If you only have one safe, you will not have to specify which safe to use other commands.
Otherwise, for most `pending` commands, you specify the safe to use (by alias) via the `--safe` option.

Additionally, you can configure a safe to use as the default when no `--safe` argument is present by configuring the following in your `ape-config.yaml` file:

```yaml
safe:
  default_safe: my-safe
```

or via `pyproject.toml`:

```toml
[tool.ape.safe]
default_safe = "my-safe"
```

or specify via environment variable:

```sh
export APE_SAFE_DEFAULT_SAFE="my-safe"
```

```{note}
To avoid always needing to specify `--network`, you can set a default ecosystem, network, and provider in your config file.
The rest of the guide will not specify `--network` on each command but assume it matches the network your Safe is on.
```

Once you have a safe, you can view pending transactions:

```sh
ape safe pending list
```

```{note}
You must specify the environment variable `APE_SAFE_GATEWAY_API_KEY=` to use the Safe Gateway API.
Get an API key at the [Safe Developer Portal](https://developer.safe.global).
```

It should show transactions like this:

```sh
Transaction 8 rejection (1/2) safe_tx_hash=0x09ab...a9a7
Transaction 8 transfer  (1/2) safe_tx_hash=0xed43...0a5b
```

Use the `--verbose` flag to see more information about each transaction:

```sh
ape safe pending list --verbose
```

There are several operations you can do on a pending transaction:

```sh
# Add more signatures using locally-configured Ape signer(s)
# NOTE: can specify either SafeTxID or Nonce
ape safe pending approve 0x09ab...a9a7

# Add remaining signatures and execute transction w/ account alias `submitter`
# NOTE: can specify either SafeTxID or Nonce
ape safe pending approve 2 --execute submitter

# Execute an already-signed transaction using `submitter`
ape safe pending execute 2 --account submitter

# Create an on-chain rejection for an existing transaction queue item
ape safe pending reject 2
```

### MultiSend Support

Ape Safe allows sending "batched transactions" using the `MultiSend` module:

```python
from ape import accounts
from ape_safe import multisend
from ape_tokens import tokens

me = accounts.load("my-key")
safe = accounts.load("my-safe")

# Load some contracts using ape-tokens
dai = tokens["DAI"]
vault = tokens["yvDAI"]
amount = dai.balanceOf(safe)  # How much we want to deposit

# Create a multisend batch transaction
batch = safe.create_batch()
batch.add(dai.approve, vault, amount)
batch.add(vault.deposit, amount)

# Fetch signatures from local signer(s)
# NOTE: will broadcast unless `submit=False`
batch(submitter=me)
# OR add to the Safe Gateway for later execution
batch.propose()
```

### Cloud Environment

To use this plugin in a cloud environment, such as with the [Silverback Platform](https://silverback.apeworx.io), you will need to make sure that you have configured your Safe to exist within the environment.
The easiest way to do this is to use the `require` configuration item.
To specify a required Safe in your `ape-config.yaml` (which adds it into your `~/.ape/safe` folder if it doesn't exist), use:

```yaml
safe:
  require:
    my-safe:
      address: "0x1234...AbCd"
      deployed_chain_ids: [1, 10] # Add all deployed chains here
```

or in `pyproject.toml`:

```toml
[tool.ape.safe.require."my-safe"]
address = "0x1234...AbCd"
deployed_chain_ids = [1, 10] # Add all deployed chains here
```

To specify via environment variable, do:

```sh
APE_SAFE_REQUIRE='{"my-safe":{"address":"0x1234...AbCd","deployed_chain_ids":[1,...]}}'
```

```{note}
If a safe with the same alias as an entry in `require` exists in your local environment, this will skip adding it, even if the existing alias points to a different address than the one in the config item.
```

## Development

Please see the [contributing guide](CONTRIBUTING.md) to learn more how to contribute to this project.
Comments, questions, criticisms and pull requests are welcomed.

## Acknowledgements

This package was inspired by the original ape-safe, now [brownie-safe](https://github.com/banteg/brownie-safe) by [banteg](https://github.com/banteg).
For versions prior to v0.6.0, the original package should be referenced.
