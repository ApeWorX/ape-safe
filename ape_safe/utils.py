from typing import List, Mapping, Union

from ape.types import AddressType, MessageSignature
from eth_utils import to_int
from hexbytes import HexBytes


def order_by_signer(
    signatures: Mapping[AddressType, Union[MessageSignature, HexBytes]]
) -> List[Union[MessageSignature, HexBytes]]:
    # NOTE: Must order signatures in ascending order of signer address (converted to int)
    def addr_to_int(a: AddressType) -> int:
        return to_int(hexstr=a)

    return list(signatures[signer] for signer in sorted(signatures, key=addr_to_int))
