# Transaction Workflows

This guide explains the lifecycle of a Safe transaction and how to manage each stage of the process.

## Transaction Lifecycle

Safe transactions follow a specific workflow:

1. **Creation**: A transaction is created and signed by the first signer (or a delegate)
2. **Proposal**: The transaction is proposed to the Safe Transaction Gateway Service
3. **Confirmation**: Other signers then add their signatures (confirmations) to the transaction
4. **Execution**: When enough signatures are collected, the transaction can be executed on-chain

## Creating and Proposing Transactions

You can create transactions very easily using your safe account like any other Ape account type:

### Via Python API

```python
# Create a simple transfer
# NOTE: This will fail to execute due to `submit=False`,
#       but will successfully submit to the Safe Gateway
safe.transfer("0xRecipientAddress", "1 ether", submit=False)
```

You can also do more complex contract interactions:

```python
# Load a contract
token = Contract("0xTokenAddress")

# Call a contract method
# NOTE: This will fail to execute due to `submit=False`,
#       but will successfully submit to the Safe Gateway
token.transfer(
    "0xRecipientAddress",
    amount,
    sender=safe,
    submit=False,
)
```

### Via CLI

```bash
# Propose a simple ETH transfer
ape safe pending propose --to 0xRecipientAddress --value "1 ether"

# Propose a contract interaction
ape safe pending propose --to 0xTokenAddress --data 0x123abc...
```

## Listing Pending Transactions

Once a transaction has been signed and proposed to the Safe Gateway, you can fetch them from the service

### Via Python API

```python
# Get all pending transactions in the Safe Gateway's queue
for tx, confirmations in safe.pending_transactions():
    print(f"Nonce: {tx.nonce}, To: {tx.to}, Data: {tx.data}, Value: {tx.value}")
    print(f"Confirmations: {len(confirmations)}/{safe.confirmations_required}")
```

### Via CLI

```bash
# List pending transactions
ape safe pending list

# Show more details
ape safe pending list --verbosoe

# Show confirmations for a transaction
ape safe pending show-confs 0x123...abc
```

## Adding Confirmations to Transactions

You can also add more confirmations (signatures) to proposed transactions in the Safe Gateway queue.

### Via Python API

```python
# Find transaction by nonce
for tx, _ in safe.pending_transactions():
    if tx.nonce == 42:  # The nonce you're looking for
        # Add signatures from local signers
        signatures = safe.add_signatures(tx)

        # Check if we have enough signatures to execute
        if len(signatures) >= safe.confirmations_required:
            print("Transaction ready to execute")
```

### Via CLI

```bash
# Approve by transaction hash
ape safe pending approve 0x123abc...

# Or approve by nonce (if only one transaction with that nonce)
ape safe pending approve 42
```

## Executing Transactions

When a transaction has enough signatures, it can then be executed on-chain.

### Via Python API

```python
from ape import accounts

# Get a regular account to submit the transaction
submitter = accounts.load("my-account")

# Find and execute a transaction that has enough signatures
for tx, confirmations in safe.pending_transactions():
    if tx.nonce == 42 and len(confirmations) >= safe.confirmations_required:
        receipt = safe.submit_safe_tx(tx, submitter=submitter)
        print(f"Transaction executed: {receipt.txn_hash}")
```

### Via CLI

```bash
# Execute a transaction with a specific submitter
ape safe pending execute 42 --submitter my-account

# Approve and also execute if the threshold is met
ape safe pending approve 42 --execute my-account
```

## Rejecting Transactions

Rejecting a transaction replaces it with a 0 ETH self-send transaction at the same nonce, effectively cancelling it.
This is useful if you have mistakenly placed a bad transaction in your queue that you need to avoid executing.

### Via Python API

```python
# Create a rejection transaction for nonce 42
safe.transfer(safe, 0, nonce=42)
```

### Via CLI

```bash
# Reject a transaction
ape safe pending reject 42

# Reject and execute immediately
ape safe pending reject 42 --execute my-account
```

## Transaction Nonce Management

Safe uses nonces to ensure transactions are executed in a specific order:

- Only one transaction can be executed per nonce
- Transactions must be executed in nonce order
- A rejected transaction still consumes its nonce

To check the next available nonce:

```python
# Next on-chain nonce
print(f"Next nonce: {safe.next_nonce}")

# Next available nonce (including pending)
print(f"New nonce: {safe.new_nonce}")
```

```{note}
By default, all transactions use the next "pending" nonce e.g. `.new_nonce` when no `nonce=` is specified.
```

## Transaction Signatures

Safe uses EIP-712 signatures for off-chain approval:

```python
from ape_safe.utils import get_safe_tx_hash

# Get the EIP-712 hash for a transaction
tx_hash = get_safe_tx_hash(tx)

# Collect signatures from local signers
signatures = safe.add_signatures(tx)
```
