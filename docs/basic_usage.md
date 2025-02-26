# Basic Usage

This guide covers the essential operations for working with Safe accounts in both Python code and via the CLI.

## Loading a Safe in Python

After you've [added a Safe](./setup.md), you can load it in Python code using Ape's accounts system:

```python
from ape import accounts

# Load a Safe by alias
safe = accounts.load("my-safe")
```

## Safe Account Properties

Once loaded, you can access various properties of the Safe:

```python
# Safe address
print(f"Address: {safe.address}")

# Current signers (owners)
print(f"Signers: {safe.signers}")

# Required confirmations (threshold)
print(f"Required confirmations: {safe.confirmations_required}")

# Local signers available (accounts that can sign transactions)
print(f"Local signers: {[str(signer) for signer in safe.local_signers]}")

# Next nonce for transactions
print(f"Next nonce: {safe.next_nonce}")

# Next nonce including pending transactions
print(f"New nonce: {safe.new_nonce}")
```

## Simple Transactions

### Sending ETH

```python
# Transfer 1 ETH to an address
receipt = safe.transfer("0xRecipientAddress", "1 ether")

# If you have enough local signers to meet the threshold,
# the transaction will be executed automatically
```

### Interacting with Contracts

```python
from ape_tokens import tokens

# Load a token contract via ape-tokens
usdc = tokens["USDC"]

# Call contract methods using the Safe as sender
receipt = usdc.transfer("wallet.apeworx.eth", "100 USDC", sender=safe)
```

Using a custom contract:

```python
from ape import Contract

# Load a contract directly
contract = Contract("0xContractAddress")

# Interact with it using the Safe as sender
receipt = contract.someMethod(arg1, arg2, sender=safe)
```

## Transaction Workflow Control

You can control whether transactions are immediately submitted or just prepared:

```python
# Create transaction without immediate submission
tx = safe.transfer("wallet.apeworx.eth", "1 ether", submit=False)

# Add signatures from local signers
signatures = safe.add_signatures(tx)

# Later, when ready to execute
receipt = safe.submit_safe_tx(tx)
```

## Viewing Pending Transactions

### In Python

```python
# Get all pending transactions
for tx, confirmations in safe.pending_transactions():
    print(f"Nonce: {tx.nonce}, To: {tx.to}, Value: {tx.value}")
    print(f"Confirmations: {len(confirmations)}/{safe.confirmations_required}")
```

### Via CLI

```bash
# List all pending transactions
ape safe pending list

# Show more details
ape safe pending list --verbose
```

## Approving Transactions

Transactions need enough signatures to meet the Safe's threshold.

### In Python

```python
# Find the transaction by nonce
for tx, _ in safe.pending_transactions():
    if tx.nonce == 42:  # The nonce you're looking for
        # Add signatures from local signers
        signatures = safe.add_signatures(tx)
```

### Via CLI

```bash
# Approve by transaction hash
ape safe pending approve 0x123abc...

# Or approve by nonce (if only one transaction with that nonce)
ape safe pending approve 42

# Approve and execute if threshold is met
ape safe pending approve 42 --execute my-account
```

## Executing Transactions

When a transaction has enough signatures, it can be executed.

### In Python

```python
from ape import accounts

# Get a regular account to submit the transaction
submitter = accounts.load("my-account")

# Execute a transaction that has enough signatures
safe.submit_safe_tx(tx, submitter=submitter)
```

### Via CLI

```bash
# Execute a transaction
ape safe pending execute 42 --submitter my-account
```

## Rejecting Transactions

Rejecting a transaction replaces it with a 0 ETH self-send.

### In Python

```python
# Create a rejection transaction for nonce 42
tx = safe.create_rejection(42)
safe.sign_transaction(tx)
```

### Via CLI

```bash
# Reject a transaction
ape safe pending reject 42

# Reject and execute immediately
ape safe pending reject 42 --execute my-account
```