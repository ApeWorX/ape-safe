# Safe Management

This guide explains how to modify your Safe configuration programmatically.

## Working with Safe Contracts

You can directly access the underlying Safe protocol smart contract via `safe.contract`:

```python
# Accessible as `safe.signers`
owners = safe.contract.getOwners()
assert owners == safe.signers

# Accessible as `safe.confirmations_required`
threshold = safe.contract.getThreshold()
assert threshold == safe.confirmations_required
```

## Changing Safe Ownership and Threshold

Using the Safe contract provides methods to modify the Safe's owner set:

```python
# Add a new owner with the current threshold
receipt = safe.contract.addOwnerWithThreshold(
    "0xNewOwnerAddress",
    safe.confirmations_required,  # NOTE: Can also change threshold as the same time
    sender=safe
)

# Remove an owner
prev_owner = safe.compute_prev_signer("0xOwnerToRemove")
receipt = safe.contract.removeOwner(
    safe.compute_prev_signer("0xOwnerToRemove"),
    "0xOwnerToRemove",
    safe.confirmations_required,  # NOTE: Can also change threshold as the same time
    sender=safe
)

# Swap an owner
prev_owner = safe.compute_prev_signer("0xOldOwner")
receipt = safe.contract.swapOwner(
    safe.compute_prev_signer("0xOwnerToRemove"),
    "0xOldOwner",
    "0xNewOwner",
    # NOTE: Cannot modify threshold this way
    sender=safe
)

# Change threshold
receipt = safe.contract.changeThreshold(
    new_threshold,
    sender=safe
)
```

Note that these are multisig transactions themselves and require the appropriate number of confirmations.

## Safe Modules

The Safe protocol supports configuring "Modules", which are contracts that have special capabilities to access your Safe.

You can enable or disable modules using the Safe contract as followsnot :

```python
assert not safe.contract.isModuleEnabled("0xModule")
safe.contract.enableModule("0xModule", sender=safe)
assert safe.contract.isModuleEnabled("0xModule")
safe.contract.disableModule("0xModule", sender=safe)
assert not safe.contract.isModuleEnabled("0xModule")
```

<!-- TODO better module support -->

## Safe Guard

Since version v1.3.0, the Safe protocol supports setting a transaction "Guard", which is a contract that can disallow certain actions to occur unless conditions are met after a proposed transaction executes.
To check if your safe has a Guard implemented, you can use the `.guard` property, which will return a contract if the guard is set.

You can also change or set a guard using the `.set_guard` function:

```python
assert not safe.guard
safe.set_guard("0xMyGuard", submitter=me)
assert safe.guard
```

```{warning}
Setting a Guard is a dangerous action.
Do *NOT* attempt unless you know what you are doing.
If a Guard is set improperly, it may render your Safe (and all it's assets) permanently inaccessible.
```

## Understanding Safe Versions

Safe contracts have different versions with varying features. Ape Safe supports all major Safe versions:

- Safe v1.1.1
- Safe v1.3.0
- Safe v1.4.1

You can check the version of your Safe by examining the master copy address when listing Safes with the `--verbose` flag.
