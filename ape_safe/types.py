from ape.types.address import AddressType
from pydantic import BaseModel


class SafeCacheData(BaseModel):
    """Model for cached Safe data under `~/.ape/safe/*.json`"""

    address: AddressType
    """Address of the Safe"""

    deployed_chain_ids: list[int] = []
    """Networks (by chain ID) this Safe is deployed on"""
