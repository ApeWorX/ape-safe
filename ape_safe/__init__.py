from importlib import import_module
from typing import Any

from ape import plugins


@plugins.register(plugins.Config)
def config_class():
    from ape_safe.config import SafeConfig

    return SafeConfig


@plugins.register(plugins.AccountPlugin)
def account_types():
    from .accounts import SafeAccount, SafeContainer

    return SafeContainer, SafeAccount


def __getattr__(name: str) -> Any:
    if name == "MultiSend":
        from .multisend import MultiSend

        return MultiSend

    elif name in ("SafeAccount", "SafeContainer"):
        return getattr(import_module("ape_safe.accounts"), name)

    elif name == "SafeConfig":
        from ape_safe.config import SafeConfig

        return SafeConfig

    else:
        raise AttributeError(name)


__all__ = [
    "MultiSend",
    "SafeAccount",
    "SafeConfig",
    "SafeContainer",
]
