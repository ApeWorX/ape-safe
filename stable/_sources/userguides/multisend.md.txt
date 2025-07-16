# MultiSend

The `MultiSend` feature allows you to batch multiple transactions into a single transaction, which is more gas-efficient and ensures atomic execution (all operations succeed or fail together).

## Basic Usage

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

# Execute (will send Ether from `safe.balance`)
txn(sender=safe)
```

## Advanced Control

You can create the transaction without executing it immediately:

```python
# Create MultiSend transaction
batch = safe.create_batch()

batch.add(dai.approve, vault, amount)
batch.add(vault.deposit, amount)

# Convert to a transaction object
safe_tx = batch.propose(submitter=me)

# Manually handle the signing process
signatures = safe.add_signatures(safe_tx)

# Later execute when ready
receipt = safe.submit_safe_tx(safe_tx)
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

The MultiSend functionality automatically detects the appropriate MultiSend contract on the current chain when using `safe.create_batch`:

```python
# Print the MultiSend contract address for the current chain
ms = safe.create_batch()
print(f"MultiSend contract: {ms.contract.address}")
```

For testing purposes, you may also inject the correct version in order to use it:

```python
from ape_safe import multisend

multisend.MultiSend.inject("1.3.0")
ms = safe.create_batch()
print(f"MultiSend contract: {ms.contract.address}")
```

## Handling Errors

When using MultiSend, remember:

1. All operations are atomic - if one fails, all fail
2. Some operations may not be compatible with batching
3. Gas estimation may be challenging for complex batches

Typically the most common issues have to do with gas estimation, which you can set directly:

```python
# Create a MultiSend transaction
ms = safe.create_batch()
ms.add(contract1.method1)
ms.add(contract2.method2)

# raises `ape.exceptions.TransactionError`
ms()

# Try to execute with manual gas limit if estimation fails
ms(gas_limit=1_000_000)
```
