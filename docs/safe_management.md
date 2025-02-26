# Safe Management

This guide explains how to add, list, and remove Safe accounts from your local configuration.

## Listing Safes

To view all Safes currently configured in your environment:

```bash
ape safe list
```

This will display basic information about each Safe:

```
my-safe: 0x1234567890123456789012345678901234567890 (ethereum:mainnet)
team-safe: 0xabcdef1234567890abcdef1234567890abcdef12 (optimism:mainnet)
```

For more detailed information:

```bash
ape safe list --verbose
```

This includes additional information like:

- Number of owners (signers)
- Required confirmations (threshold)
- Implementation version
- Master copy address

## Adding a Safe

To start using a Safe, you need to add it to your local configuration:

```bash
ape safe add --network ethereum:mainnet "0x1234567890123456789012345678901234567890" my-safe
```

You can also use ENS names:

```bash
ape safe add --network ethereum:mainnet "mysafe.eth" my-safe
```

### Arguments

- `ADDRESS`: The address or ENS name of your Safe
- `ALIAS`: A local name to reference this Safe

### Options

- `--network`: The network where the Safe is deployed (required unless a default is set in config)
- `--force`: Overwrite an existing Safe with the same alias

## Removing a Safe

To stop tracking a Safe:

```bash
ape safe remove my-safe
```

You'll be prompted to confirm. Use the `--yes` flag to skip confirmation:

```bash
ape safe remove my-safe --yes
```

## Viewing All Transactions

To view all transactions (pending and executed) for a Safe:

```bash
ape safe all-txns my-safe
```

To only show confirmed (executed) transactions:

```bash
ape safe all-txns my-safe --confirmed
```

## Safe Configuration

You can set a default Safe in your `ape-config.yaml` file:

```yaml
safe:
  default_safe: my-safe
```

With a default Safe configured, you won't need to specify which Safe to use for commands.

## Safe Account Access in Python

To access a Safe in your Python code:

```python
from ape import accounts

# Load by alias
safe = accounts.load("my-safe")

# Check safe properties
print(f"Address: {safe.address}")
print(f"Network: {safe.network.name}")
print(f"Signers: {safe.signers}")
print(f"Confirmations required: {safe.confirmations_required}")
```

## Working with Safe Contracts

You can directly access the underlying Safe contract:

```python
# Access the Safe contract
safe_contract = safe.contract

# Call contract methods
owners = safe_contract.getOwners()
threshold = safe_contract.getThreshold()
```

## Safe Management Operations

The Safe contract provides methods to modify the Safe configuration:

```python
# Add a new owner with the current threshold
receipt = safe.contract.addOwnerWithThreshold(
    "0xNewOwnerAddress",
    safe.confirmations_required,
    sender=safe
)

# Remove an owner
prev_owner = safe.compute_prev_signer("0xOwnerToRemove")
receipt = safe.contract.removeOwner(
    prev_owner,
    "0xOwnerToRemove",
    safe.confirmations_required,
    sender=safe
)

# Swap an owner
prev_owner = safe.compute_prev_signer("0xOldOwner")
receipt = safe.contract.swapOwner(
    prev_owner,
    "0xOldOwner",
    "0xNewOwner",
    sender=safe
)

# Change threshold
receipt = safe.contract.changeThreshold(
    new_threshold,
    sender=safe
)
```

Note that these are multisig transactions themselves and require the appropriate number of confirmations.

## Understanding Safe Versions

Safe contracts have different versions with varying features. Ape Safe supports all major Safe versions:

- Safe v1.1.1
- Safe v1.3.0
- Safe v1.4.1

You can check the version of your Safe by examining the master copy address when listing Safes with the `--verbose` flag.