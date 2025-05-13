from typing import Optional

from ape.api import PluginConfig
from pydantic_settings import SettingsConfigDict

from .types import SafeCacheData


class SafeConfig(PluginConfig):
    default_safe: Optional[str] = None
    """Alias of the default safe."""

    require: dict[str, SafeCacheData] = {}
    """Safes that are required to exist for the project. Useful for cloud-based usage."""

    model_config = SettingsConfigDict(env_prefix="APE_SAFE_")
