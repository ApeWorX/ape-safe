from typing import TYPE_CHECKING, List, Mapping, cast

from ape.types import AddressType, MessageSignature
from eip712.messages import calculate_hash
from eth_typing import HexStr
from eth_utils import add_0x_prefix, keccak, to_int
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


def to_int_array(value) -> List[int]:
    value_hex = HexBytes(value).hex()
    value_int = int(value_hex, 16)

    result: List[int] = []
    while value_int:
        result.insert(0, value_int & 0xFF)
        value_int = value_int // 256

    if len(result) == 0:
        result.append(0)

    return result


def to_utf8_bytes(value: str) -> List[int]:
    result = []
    i = 0
    while i < len(value):
        c = ord(value[i])

        if c < 0x80:
            result.append(c)

        elif c < 0x800:
            result.append((c >> 6) | 0xC0)
            result.append((c & 0x3F) | 0x80)

        elif 0xD800 <= c <= 0xDBFF:
            i += 1
            c2 = ord(value[i])

            if i >= len(value) or not (0xDC00 <= c2 <= 0xDFFF):
                raise ValueError("Invalid UTF-8 string")

            # Surrogate Pair
            pair = 0x10000 + ((c & 0x03FF) << 10) + (c2 & 0x03FF)
            result.append((pair >> 18) | 0xF0)
            result.append(((pair >> 12) & 0x3F) | 0x80)
            result.append(((pair >> 6) & 0x3F) | 0x80)
            result.append((pair & 0x3F) | 0x80)

        else:
            result.append((c >> 12) | 0xE0)
            result.append(((c >> 6) & 0x3F) | 0x80)
            result.append((c & 0x3F) | 0x80)

        i += 1

    return result


def hash_message(message: str) -> str:
    message_array = to_int_array(message)
    message_prefix = "\x19Ethereum Signed Message:\n"
    prefix_bytes = to_utf8_bytes(message_prefix)
    length_bytes = to_utf8_bytes(f"{len(message_array)}")
    full_array = prefix_bytes + length_bytes + message_array
    result = keccak(bytearray(full_array)).hex()
    return add_0x_prefix(cast(HexStr, result))
