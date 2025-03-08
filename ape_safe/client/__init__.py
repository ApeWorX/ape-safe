import json
from collections.abc import Iterator
from datetime import datetime
from functools import reduce
from typing import Optional, Union, cast

from ape.types import AddressType, HexBytes, MessageSignature
from ape.utils import USER_AGENT, get_package_version
from eip712.common import SafeTxV1, SafeTxV2
from eth_utils import to_hex

from ape_safe.client.base import BaseSafeClient
from ape_safe.client.mock import MockSafeClient
from ape_safe.client.types import (
    ExecutedTxData,
    OperationType,
    SafeApiTxData,
    SafeDetails,
    SafeTx,
    SafeTxConfirmation,
    SafeTxID,
    SignatureType,
    UnexecutedTxData,
)
from ape_safe.exceptions import (
    ClientResponseError,
    ClientUnsupportedChainError,
    MultisigTransactionNotFoundError,
)
from ape_safe.utils import get_safe_tx_hash, order_by_signer

APE_SAFE_VERSION = get_package_version(__name__)
APE_SAFE_USER_AGENT = f"Ape-Safe/{APE_SAFE_VERSION} {USER_AGENT}"
# NOTE: Origin must be a string, but can be json that contains url & name fields
ORIGIN = json.dumps(dict(url="https://apeworx.io", name="Ape Safe", ua=APE_SAFE_USER_AGENT))
assert len(ORIGIN) <= 200  # NOTE: Must be less than 200 chars

# URL for the multichain client gateway
SAFE_CLIENT_GATEWAY_URL = "https://safe-client.safe.global"


class SafeClient(BaseSafeClient):
    def __init__(
        self,
        address: AddressType,
        override_url: Optional[str] = None,
        chain_id: Optional[int] = None,
    ) -> None:
        self.address = address
        self.chain_id = chain_id

        if override_url:
            base_url = override_url
            self.use_client_gateway = False
        elif chain_id:
            base_url = SAFE_CLIENT_GATEWAY_URL
            self.use_client_gateway = True
        else:
            raise ValueError("Must provide one of chain_id or override_url.")

        super().__init__(base_url)

    @property
    def safe_details(self) -> SafeDetails:
        response = self._get(f"safes/{self.address}")
        return SafeDetails.model_validate(response.json())

    def get_next_nonce(self) -> int:
        return self.safe_details.nonce

    def _all_transactions(self) -> Iterator[SafeApiTxData]:
        """
        Get all transactions from safe, both confirmed and unconfirmed
        """

        url = f"safes/{self.address}/all-transactions"
        while url:
            response = self._get(url)
            data = response.json()

            for txn in data.get("results"):
                # NOTE: Using construct because of pydantic v2 back import validation error.
                if "isExecuted" in txn:
                    if txn["isExecuted"]:
                        yield ExecutedTxData.model_validate(txn)

                    else:
                        yield UnexecutedTxData.model_validate(txn)

                # else it is an incoming transaction

            url = data.get("next")

    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]:
        url = f"multisig-transactions/{str(safe_tx_hash)}/confirmations"
        while url:
            response = self._get(url)
            data = response.json()
            yield from map(SafeTxConfirmation.model_validate, data.get("results"))
            url = data.get("next")

    def post_transaction(
        self, safe_tx: SafeTx, signatures: dict[AddressType, MessageSignature], **kwargs
    ):
        tx_data = UnexecutedTxData.from_safe_tx(safe_tx, self.safe_details.threshold)
        signature = HexBytes(
            reduce(
                lambda raw_sig, next_sig: raw_sig
                + (next_sig.encode_rsv() if isinstance(next_sig, MessageSignature) else next_sig),
                order_by_signer(signatures),
                b"",
            )
        )
        post_dict: dict = {"signature": to_hex(signature), "origin": ORIGIN}

        for key, value in tx_data.model_dump(by_alias=True, mode="json").items():
            if isinstance(value, HexBytes):
                post_dict[key] = to_hex(value)
            elif isinstance(value, OperationType):
                post_dict[key] = int(value)
            elif isinstance(value, datetime):
                # not needed
                continue
            else:
                post_dict[key] = value

        post_dict = {**post_dict, **kwargs}

        if "signatures" in post_dict:
            # Signature handled above.
            post_dict.pop("signatures")

        url = f"safes/{tx_data.safe}/multisig-transactions"
        response = self._post(url, json=post_dict)
        return response

    def post_signatures(
        self,
        safe_tx_or_hash: Union[SafeTx, SafeTxID],
        signatures: dict[AddressType, MessageSignature],
    ):
        if isinstance(safe_tx_or_hash, (SafeTxV1, SafeTxV2)):
            safe_tx = safe_tx_or_hash
            safe_tx_hash = get_safe_tx_hash(safe_tx)
        else:
            safe_tx_hash = safe_tx_or_hash

        safe_tx_hash = cast(SafeTxID, to_hex(HexBytes(safe_tx_hash)))
        url = f"multisig-transactions/{safe_tx_hash}/confirmations"
        signature = to_hex(
            HexBytes(b"".join([x.encode_rsv() for x in order_by_signer(signatures)]))
        )
        try:
            self._post(url, json={"signature": signature})
        except ClientResponseError as err:
            if "The requested resource was not found on this server" in err.response.text:
                raise MultisigTransactionNotFoundError(safe_tx_hash, url, err.response) from err

            raise  # The error from BaseClient we are already raising (no changes)

    def estimate_gas_cost(
        self, receiver: AddressType, value: int, data: bytes, operation: int = 0
    ) -> Optional[int]:
        url = f"safes/{self.address}/multisig-transactions/estimations"
        request: dict = {
            "to": receiver,
            "value": value,
            "data": to_hex(HexBytes(data)),
            "operation": operation,
        }
        result = self._post(url, json=request).json()
        gas = result.get("safeTxGas")
        return int(to_hex(HexBytes(gas)), 16)


__all__ = [
    "ExecutedTxData",
    "MockSafeClient",
    "OperationType",
    "SafeApiTxData",
    "SafeClient",
    "SafeDetails",
    "SafeTx",
    "SafeTxConfirmation",
    "SignatureType",
    "UnexecutedTxData",
]
