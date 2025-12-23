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

## Simulating Side Effects in Scripts

Typically, it is useful to validate your multisend scripts through the use of simulating their
side effects via a "forked" network context.
We have provided a feature `batch.add_from_receipt` which allows you to add calls directly from
the results of simulated network calls (executing as the Safe itself), which reduces human error.

```python
# Create MultiSend transaction outside the fork context (important!)
# NOTE: You should be connected to a live "public"  network when executing this
batch = safe.create_batch()

# Enter a "simulated" context as a "fork" of the public network you want to propose to
with networks.fork():
    # NOTE: We must use `sender=safe.address` to skip ape-safe's local signer processing
    # NOTE: You typically must provide an eth balance to `safe.address`, or it will fail
    #       due to no funds to pay for gas in order to perform the transaction.
    receipt = dai.approve(vault, amount, sender=safe.address)
    # NOTE: You can now test "side effects" of the transaction here.
    assert dai.allowance(safe, vault) == amount
    # This will add the call as a step in the MultiSend batch
    batch.add_from_receipt(receipt)

    # ...add as many steps as you would like to the batch while inside this forked context.
    receipt = vault.deposit(amount, sender=safe.address)
    assert vault.balanceOf(safe) == amount
    batch.add_from_receipt(receipt)

# After exiting the forked context, submit it as a real transaction on-chain
batch(submitter=me)

# Or, propose to the API
safe_tx = batch.propose(submitter=me)
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
