# Modules

The modules feature of your Safe account allows you to manage "extensions" to the behavior of your Safe,
unlocking the ability to support automated actions or custom transaction logic _without signer approval_.

```{warning}
Safe Modules can be very dangerous to enable on your Safe, as it allows the Module
(and accounts with access to the Module) to completely bypass the authentication logic in your Safe smart contract.
Use at your own risk.
```

```{note}
Read more about Safe Modules in the [docs](https://docs.safe.global/advanced/smart-account-modules).
```

## Basic Usage

To enable or disable a Module in your Safe, you can do so via:

```python
from ape import accounts
from ape_safe import multisend
from ape_tokens import tokens

me = accounts.load("my-key")
safe = accounts.load("my-safe")

module = Contract(...)  # NOTE: Deploy it yourself, or use vetted Safe modules

# Check if module is enabled
assert module not in safe.modules

# Then add it
receipt = safe.modules.enable(module, submitter=me)
assert module in safe.modules

# You can always disable it later
receipt = safe.modules.disable(module, submitter=me)
```

## Advanced Usage

Safe Modules also come with a Module Guard functionality, similiar to your Safe's Guard functionality.

To set (or unset) a Module Guard, do so via:

```python
guard = Contract(...)  # NOTE: Deploy it yourself, or use a vetted Safe Module Guard

assert not safe.modules.guard  # NOTE: Not set by default

# Add a Module Guard
safe.modules.set_guard(guard, submitter=me)

# Remove a Module Guard
safe.modules.remove_guard(submitter=me)
```
