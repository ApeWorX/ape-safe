from typing import TYPE_CHECKING, List, Mapping, cast

from ape.types import AddressType, MessageSignature
from eip712.messages import calculate_hash
from eth_utils import to_int
from hexbytes import HexBytes

if TYPE_CHECKING:
    from ape_safe.client.types import SafeTxID


def order_by_signer(signatures: Mapping[AddressType, MessageSignature]) -> List[MessageSignature]:
    # NOTE: Must order signatures in ascending order of signer address (converted to int)
    def addr_to_int(a: AddressType) -> int:
        return to_int(hexstr=a)

    return list(signatures[signer] for signer in sorted(signatures, key=addr_to_int))


def get_safe_tx_hash(safe_tx) -> "SafeTxID":
    message_hash = calculate_hash(safe_tx.signable_message)
    return cast("SafeTxID", message_hash.hex())


def _rsv_to_message_signature(rsv: HexBytes) -> MessageSignature:
    # TODO: Can use Signature.from_rsv() in next version of Ape.
    if len(rsv) != 65:
        raise ValueError("Length of RSV bytes must be 65.")

    return MessageSignature(r=HexBytes(rsv[:32]), s=HexBytes(rsv[32:64]), v=rsv[64])
