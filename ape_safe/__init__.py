from typing import Optional

from ape import plugins
from ape.api import PluginConfig

from .accounts import SafeAccount, SafeContainer
from .multisend import MultiSend


class SafeConfig(PluginConfig):
    default_safe: Optional[str] = None
    """Alias of the default safe."""


@plugins.register(plugins.Config)
def config_class():
    return SafeConfig


@plugins.register(plugins.AccountPlugin)
def account_types():
    return SafeContainer, SafeAccount


__all__ = [
    "MultiSend",
    "SafeAccount",
]
