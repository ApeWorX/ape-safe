from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from eip712.messages import calculate_hash
from eth_utils import to_hex, to_int

if TYPE_CHECKING:
    from ape.types import AddressType, MessageSignature

    from ape_safe.client.types import SafeTxID


def order_by_signer(
    signatures: Mapping["AddressType", "MessageSignature"]
) -> list["MessageSignature"]:
    # NOTE: Must order signatures in ascending order of signer address (converted to int)
    return list(signatures[signer] for signer in sorted(signatures, key=lambda a: to_int(hexstr=a)))


def get_safe_tx_hash(safe_tx) -> "SafeTxID":
    message_hash = calculate_hash(safe_tx.signable_message)
    return cast("SafeTxID", to_hex(message_hash))
