# CLI Reference

This page documents all available command-line interface (CLI) commands for ape-safe.

## Safe Management

### List Safes

```bash
ape safe list [OPTIONS]
```

**Options:**
- `--verbose`: Show additional information about each Safe

**Example:**
```bash
ape safe list --verbose
```

### Add Safe

```bash
ape safe add [OPTIONS] ADDRESS ALIAS
```

**Arguments:**
- `ADDRESS`: The address or ENS name of the Safe
- `ALIAS`: Name to use locally for the Safe

**Options:**
- `--network`: The network where the Safe is deployed
- `--force`: Overwrite if a Safe with this alias already exists

**Example:**
```bash
ape safe add --network ethereum:mainnet "0x1234567890123456789012345678901234567890" my-safe
```

### Remove Safe

```bash
ape safe remove [OPTIONS] SAFE
```

**Arguments:**
- `SAFE`: The alias of the Safe to remove

**Options:**
- `--yes`: Skip confirmation prompt

**Example:**
```bash
ape safe remove my-safe --yes
```

### View All Transactions

```bash
ape safe all-txns [OPTIONS] ACCOUNT
```

**Arguments:**
- `ACCOUNT`: The Safe account alias

**Options:**
- `--confirmed`: Only show confirmed (executed) transactions
- `--safe`: Specify which Safe to use (if not using default)
- `--network`: Specify the network (if not using default)

**Example:**
```bash
ape safe all-txns my-safe --confirmed
```

## Pending Transaction Management

### List Pending Transactions

```bash
ape safe pending list [OPTIONS]
```

**Options:**
- `--verbose`: Show additional information
- `--safe`: Specify which Safe to use
- `--network`: Specify the network

**Example:**
```bash
ape safe pending list --verbose
```

### Propose Transaction

```bash
ape safe pending propose [OPTIONS]
```

**Options:**
- `--to`: Recipient address
- `--value`: ETH value to send (in wei)
- `--data`: Transaction data (hex-encoded)
- `--nonce`: Specific nonce to use
- `--operation`: Operation type (CALL, DELEGATECALL, CREATE)
- `--safe-tx-gas`: Gas required for the Safe transaction
- `--base-gas`: Gas required for data and execution
- `--gas-price`: Gas price for the transaction
- `--gas-token`: Address of token used for refunds
- `--refund-receiver`: Address of refund receiver
- `--safe`: Specify which Safe to use
- `--network`: Specify the network

**Example:**
```bash
ape safe pending propose --to 0xRecipient --value "1 ether"
```

### Approve Transaction

```bash
ape safe pending approve [OPTIONS] TXN_IDS
```

**Arguments:**
- `TXN_IDS`: Transaction IDs (hash or nonce) to approve

**Options:**
- `--execute`: Execute immediately if threshold is met
- `--submitter`: Account to use for execution
- `--safe`: Specify which Safe to use
- `--network`: Specify the network

**Example:**
```bash
ape safe pending approve 42 --execute my-account
```

### Execute Transaction

```bash
ape safe pending execute [OPTIONS] TXN_IDS
```

**Arguments:**
- `TXN_IDS`: Transaction IDs (hash or nonce) to execute

**Options:**
- `--submitter`: Account to use for execution (required)
- `--gas`: Gas limit for execution
- `--gas-price`: Gas price for execution
- `--safe`: Specify which Safe to use
- `--network`: Specify the network

**Example:**
```bash
ape safe pending execute 0x123abc... --submitter my-account
```

### Reject Transaction

```bash
ape safe pending reject [OPTIONS] TXN_IDS
```

**Arguments:**
- `TXN_IDS`: Transaction IDs (hash or nonce) to reject

**Options:**
- `--execute`: Execute rejection immediately
- `--submitter`: Account to use for execution
- `--safe`: Specify which Safe to use
- `--network`: Specify the network

**Example:**
```bash
ape safe pending reject 42 --execute my-account
```

### Show Confirmations

```bash
ape safe pending show-confs [OPTIONS] TXN_ID
```

**Arguments:**
- `TXN_ID`: Transaction ID (hash or nonce)

**Options:**
- `--safe`: Specify which Safe to use
- `--network`: Specify the network

**Example:**
```bash
ape safe pending show-confs 0x123abc...
```

## Global Options

These options apply to all commands:

- `--network`: Specify the network (e.g., `ethereum:mainnet`, `optimism:mainnet`)
- `--safe`: Specify which Safe to use (not needed if you only have one Safe or set a default)

## Environment Variables

You can set these environment variables to avoid repeating options:

- `APE_NETWORK`: Default network to use
- `APE_SAFE_DEFAULT`: Default Safe alias to use

## Tips

1. Use tab completion (if your shell supports it) to see available commands and options
2. Use `ape safe --help` to see all available commands
3. Use `ape safe COMMAND --help` to see help for a specific command