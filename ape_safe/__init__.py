from ape import plugins

from .accounts import SafeAccount, SafeContainer
from .multisend import MultiSend


@plugins.register(plugins.AccountPlugin)
def account_types():
    return SafeContainer, SafeAccount


__all__ = [
    "MultiSend",
    "SafeAccount",
]
