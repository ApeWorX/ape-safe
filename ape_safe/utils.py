from typing import Dict, List

from ape.types import AddressType, MessageSignature
from eth_utils import to_int


def order_by_signer(signatures: Dict[AddressType, MessageSignature]) -> List[MessageSignature]:
    # NOTE: Must order signatures in ascending order of signer address (converted to int)
    def addr_to_int(a: AddressType) -> int:
        return to_int(hexstr=a)

    return list(signatures[signer] for signer in sorted(signatures, key=addr_to_int))
