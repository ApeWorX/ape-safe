# MultiSend

The `MultiSend` feature allows you to batch multiple transactions into a single transaction, which is more gas-efficient and ensures atomic execution (all operations succeed or all fail).

## Basic Usage

```python
from ape_safe import multisend
from ape import accounts

# Load your Safe
safe = accounts.load("my-safe")

# Create a MultiSend transaction
txn = multisend.MultiSend()

# Add transactions to the batch
txn.add(safe.transfer, "0xRecipient1", "1 ether")
txn.add(safe.transfer, "0xRecipient2", "0.5 ether")

# Execute the batch (collects signatures and submits)
txn(sender=safe)
```

## Working with Contracts

MultiSend is particularly useful for contract interactions:

```python
from ape_safe import multisend
from ape import accounts
from ape_tokens import tokens

# Load Safe and contracts
safe = accounts.load("my-safe")
dai = tokens["DAI"]
vault = tokens["yvDAI"]
amount = dai.balanceOf(safe)

# Create batch with approval and deposit
txn = multisend.MultiSend()
txn.add(dai.approve, vault, amount)
txn.add(vault.deposit, amount)

# Execute
txn(sender=safe)
```

## Adding ETH Value to Calls

You can include ETH value with transactions in the batch:

```python
# Create a MultiSend transaction
txn = multisend.MultiSend()

# Add a transaction that sends ETH with the call
txn.add(contract.deposit, value="1 ether")

# Add another call without value
txn.add(contract.stake, amount)

# Execute
txn(sender=safe)
```

## Advanced Control

You can create the transaction without executing it immediately:

```python
# Create MultiSend transaction
txn = multisend.MultiSend()
txn.add(dai.approve, vault, amount)
txn.add(vault.deposit, amount)

# Convert to a transaction object
tx = txn.as_transaction(sender=safe)

# Manually handle the signing process
signatures = safe.add_signatures(tx)

# Later execute when ready
receipt = safe.submit_safe_tx(tx)
```

## Decoding Existing MultiSend Transactions

You can decode and inspect existing MultiSend transactions:

```python
from ape_safe import multisend

# Create an empty MultiSend object
txn = multisend.MultiSend()

# Add calls from existing calldata
calldata = "0x..."  # MultiSend calldata from a transaction
txn.add_from_calldata(calldata)

# Now you can inspect the calls
for call in txn.calls:
    print(f"To: {call.to}")
    print(f"Value: {call.value}")
    print(f"Data: {call.data}")
```

## MultiSend Contract Detection

The MultiSend functionality automatically detects the appropriate MultiSend contract on the current chain:

```python
from ape_safe import multisend

# Print the MultiSend contract address for the current chain
txn = multisend.MultiSend()
print(f"MultiSend contract: {txn.contract.address}")
```

## Handling Errors

When using MultiSend, remember:

1. All operations are atomic - if one fails, all fail
2. Some operations may not be compatible with batching
3. Gas estimation may be challenging for complex batches

To handle potential issues:

```python
from ape_safe import multisend
from ape.exceptions import TransactionError

# Load your Safe
safe = accounts.load("my-safe")

# Create a MultiSend transaction
txn = multisend.MultiSend()
txn.add(contract1.method1)
txn.add(contract2.method2)

try:
    # Try to execute with manual gas limit if estimation fails
    txn(sender=safe, gas=1000000)
except TransactionError as e:
    print(f"Transaction failed: {e}")
```