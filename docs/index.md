# Ape Safe Documentation

Ape Safe is an account plugin for [Safe](https://safe.global/) multisignature wallets (previously known as Gnosis Safe) that integrates with the [Ape Framework](https://github.com/ApeWorX/ape) for Ethereum development.

## Key Features

- **Safe Account Management**: Add, list, and remove Safe multisig wallets
- **Transaction Management**: Create, propose, sign, and execute Safe transactions
- **Multisig Workflows**: Manage transaction approval workflows with multiple signers
- **MultiSend Support**: Batch multiple transactions together efficiently
- **CLI Interface**: Comprehensive command line tools for Safe management
- **Python API**: Programmatic access to all Safe functionality

## Installation

You can install the plugin using ape's built-in plugin manager:

```bash
ape plugins install safe
```

Alternatively, you can install via pip:

```bash
pip install ape-safe
```

## Quick Start

```python
from ape import accounts
from ape_safe import multisend
from ape_tokens import tokens

# Load a Safe account
safe = accounts.load("my-safe")

# Simple transfer
tx = safe.transfer("0xRecipientAddress", "1 ether")

# Contract interaction using ape-tokens
usdc = tokens["USDC"]
usdc.transfer("wallet.apeworx.eth", "100 USDC", sender=safe)

# Batch multiple transactions together
txn = multisend.MultiSend()
txn.add(usdc.approve, spender, amount)
txn.add(spender.deposit, amount)
txn(sender=safe)
```

## Contents

- [Setup](./setup.md) - Configuration and initial setup
- [Basic Usage](./basic_usage.md) - Essential operations
- [Safe Management](./safe_management.md) - Adding, listing and removing Safes
- [Transaction Workflows](./transactions.md) - Understanding the transaction lifecycle
- [MultiSend](./multisend.md) - Batching transactions
- [CLI Reference](./cli.md) - Command line interface documentation
- [API Reference](./api.md) - Python API documentation