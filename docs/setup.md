# Setting Up Ape Safe

## Prerequisites

- [Python](https://www.python.org/downloads/) 3.9 or newer
- [Ape Framework](https://github.com/ApeWorX/ape) installed
- A deployed Safe (formerly Gnosis Safe) contract

## Installation

### Via Ape Plugins

The easiest way to install ape-safe is through Ape's plugin manager:

```bash
ape plugins install safe
```

### Via Pip

You can also install directly with pip:

```bash
pip install ape-safe
```

### From Source

For the latest development version:

```bash
git clone https://github.com/ApeWorX/ape-safe.git
cd ape-safe
pip install -e .
```

## Configuration

Ape Safe requires minimal configuration. You can optionally set a default safe in your `ape-config.yaml`:

```yaml
safe:
  default_safe: my-safe
```

You may also want to set default ecosystem and network settings in your config to avoid specifying them in every command:

```yaml
default_ecosystem: ethereum

ethereum:
  default_network: mainnet
  mainnet:
    default_provider: infura
```

## Adding a Safe

Before you can interact with a Safe, you need to add it to your local configuration:

```bash
ape safe add --network ethereum:mainnet "0x1234567890123456789012345678901234567890" my-safe
```

You can also use ENS names:

```bash
ape safe add --network ethereum:mainnet "my-safe.eth" my-safe
```

### Arguments

- `ADDRESS`: The address or ENS name of your Safe
- `ALIAS`: A local name to reference this Safe

### Options

- `--network`: The network where the Safe is deployed (required unless a default is set in config)
- `--force`: Overwrite an existing Safe with the same alias

## Verifying Setup

To verify your Safe was added correctly:

```bash
ape safe list
```

This should show your Safe along with its address and other details.

To see more information, including owners and threshold:

```bash
ape safe list --verbose
```

## Working with Multiple Safes

You can add as many Safes as needed with different aliases:

```bash
ape safe add --network ethereum:mainnet "0x1234..." team-safe
ape safe add --network optimism:mainnet "0xabcd..." project-safe
```

When running commands, you can specify which Safe to use:

```bash
ape safe pending list --safe team-safe
```

If you only have one Safe configured or you've set a default in the config, you don't need to specify which Safe to use.

## Removing a Safe

If you no longer need to track a Safe:

```bash
ape safe remove my-safe
```

Use the `--yes` flag to skip confirmation:

```bash
ape safe remove my-safe --yes
```