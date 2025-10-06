from collections.abc import Mapping
from typing import TYPE_CHECKING

from ape.types import AddressType, HexBytes, MessageSignature
from eip712.messages import calculate_hash
from eth_utils import to_hex, to_int

if TYPE_CHECKING:
    from .client.types import SafeTx, SafeTxID


def order_by_signer(signatures: Mapping[AddressType, MessageSignature]) -> list[MessageSignature]:
    # NOTE: Must order signatures in ascending order of signer address (converted to int)
    return [signatures[signer] for signer in sorted(signatures, key=lambda a: to_int(hexstr=a))]


def encode_signatures(signatures: Mapping[AddressType, MessageSignature]) -> HexBytes:
    return HexBytes(
        b"".join(
            sig.encode_rsv() if isinstance(sig, MessageSignature) else sig
            for sig in order_by_signer(signatures)
        )
    )


def get_safe_tx_hash(safe_tx: "SafeTx") -> "SafeTxID":
    message_hash = calculate_hash(safe_tx.signable_message)
    return HexBytes(to_hex(message_hash))
