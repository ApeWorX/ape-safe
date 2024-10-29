from typing import Optional

from ape.api import PluginConfig


class SafeConfig(PluginConfig):
    default_safe: Optional[str] = None
    """Alias of the default safe."""
