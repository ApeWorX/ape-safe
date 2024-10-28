from importlib import import_module
from typing import Any, Optional

from ape import plugins
from ape.api import PluginConfig


class SafeConfig(PluginConfig):
    default_safe: Optional[str] = None
    """Alias of the default safe."""


@plugins.register(plugins.Config)
def config_class():
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

    else:
        raise AttributeError(name)


__all__ = [
    "MultiSend",
    "SafeAccount",
    "SafeContainer",
]
