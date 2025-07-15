# Transaction Workflows

This guide explains the lifecycle of a Safe transaction and how to manage each stage of the process.

## Transaction Lifecycle

Safe transactions follow a specific workflow:

1. **Creation**: A transaction is created and signed by the first signer
2. **Proposal**: The transaction is proposed to the Safe Transaction Service
3. **Confirmation**: Other signers add their signatures (confirmations)
4. **Execution**: When enough signatures are collected, the transaction is executed on-chain

## Creating and Proposing Transactions

### Via Python API

```python
from ape import accounts

# Load your Safe
safe = accounts.load("my-safe")

# Create a simple transfer
tx = safe.transfer(
    "0xRecipientAddress",
    "1 ether",
    submit=True  # This will automatically propose to the Safe Transaction Service
)
```

For contract interactions:

```python
# Load a contract
token = Contract("0xTokenAddress")

# Call a contract method
tx = token.transfer(
    "0xRecipientAddress",
    amount,
    sender=safe,
    submit=True
)
```

### Via CLI

```bash
# Propose a simple ETH transfer
ape safe pending propose --to 0xRecipientAddress --value "1 ether"

# Propose a contract interaction
ape safe pending propose --to 0xContractAddress --data 0x123abc...
```

## Listing Pending Transactions

### Via Python API

```python
# Get all pending transactions
for tx, confirmations in safe.pending_transactions():
    print(f"Nonce: {tx.nonce}, To: {tx.to}, Value: {tx.value}")
    print(f"Confirmations: {len(confirmations)}/{safe.confirmations_required}")
```

### Via CLI

```bash
# List pending transactions
ape safe pending list

# Show more details
ape safe pending list --verbose
```

## Viewing Transaction Details

```bash
# Get transaction hash
safe_tx_hash = "0x123abc..."

# Show confirmations for a transaction
ape safe pending show-confs safe_tx_hash
```

## Adding Confirmations to Transactions

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

When a transaction has enough signatures, it can be executed.

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
```

## Approve and Execute in One Step

```bash
# Approve and execute if the threshold is met
ape safe pending approve 42 --execute my-account
```

## Rejecting Transactions

Rejecting a transaction replaces it with a 0 ETH self-send transaction at the same nonce, effectively cancelling it.

### Via Python API

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

## Transaction Nonce Management

Safe uses nonces to ensure transactions are executed in order:

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

## Transaction Signatures

Safe uses EIP-712 signatures for off-chain approval:

```python
from ape_safe.utils import get_safe_tx_hash

# Get the EIP-712 hash for a transaction
tx_hash = get_safe_tx_hash(tx)

# Collect signatures from local signers
signatures = safe.add_signatures(tx)
```
