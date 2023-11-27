from datetime import datetime
from functools import reduce
from typing import Dict, Iterator, Optional, Union

import requests
from ape.types import AddressType, HexBytes, MessageSignature
from eip712.common import SafeTxV1, SafeTxV2
from eip712.messages import hash_eip712_message

from ape_safe.client.base import BaseSafeClient
from ape_safe.client.mock import MockSafeClient
from ape_safe.client.models import (
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
from ape_safe.utils import order_by_signer

TRANSACTION_SERVICE_URL = {
    # NOTE: If URLs need to be updated, a list of available service URLs can be found at
    # https://docs.safe.global/safe-core-api/available-services.
    # NOTE: There should be no trailing slashes at the end of the URL.
    1: "https://safe-transaction-mainnet.safe.global",
    5: "https://safe-transaction-goerli.safe.global",
    10: "https://safe-transaction-optimism.safe.global",
    56: "https://safe-transaction-bsc.safe.global",
    100: "https://safe-transaction-gnosis-chain.safe.global",
    137: "https://safe-transaction-polygon.safe.global",
    250: "https://safe-txservice.fantom.network",
    288: "https://safe-transaction.mainnet.boba.network",
    8453: "https://safe-transaction-base.safe.global",
    42161: "https://safe-transaction-arbitrum.safe.global",
    43114: "https://safe-transaction-avalanche.safe.global",
    84531: "https://safe-transaction-base-testnet.safe.global",
}


class SafeClient(BaseSafeClient):
    def __init__(
        self,
        address: AddressType,
        override_url: Optional[str] = None,
        chain_id: Optional[int] = None,
    ) -> None:
        self.address = address

        if override_url:
            self.transaction_service_url = override_url

        elif chain_id:
            if chain_id not in TRANSACTION_SERVICE_URL:
                raise ClientUnsupportedChainError(chain_id)

            self.transaction_service_url = TRANSACTION_SERVICE_URL.get(  # type: ignore[assignment]
                chain_id
            )

        else:
            raise ValueError("Must provide one of chain_id or override_url.")

    @property
    def safe_details(self) -> SafeDetails:
        url = f"{self.transaction_service_url}/api/v1/safes/{self.address}"
        response = requests.get(url)
        if not response.ok:
            raise ClientResponseError(url, response)

        return SafeDetails.parse_obj(response.json())

    def get_next_nonce(self) -> int:
        return self.safe_details.nonce

    def _all_transactions(self) -> Iterator[SafeApiTxData]:
        """
        confirmed: Confirmed if True, not confirmed if False, both if None
        """

        url = f"{self.transaction_service_url}/api/v1/safes/{self.address}/transactions"
        while url:
            response = requests.get(url)
            if not response.ok:
                raise ClientResponseError(url, response)

            data = response.json()

            for txn in data.get("results"):
                if "isExecuted" in txn and txn["isExecuted"]:
                    yield ExecutedTxData.parse_obj(txn)

                else:
                    yield UnexecutedTxData.parse_obj(txn)

            url = data.get("next")

    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]:
        url = (
            f"{self.transaction_service_url}/api"
            f"/v1/multisig-transactions/{str(safe_tx_hash)}/confirmations"
        )
        while url:
            response = requests.get(url)
            if not response.ok:
                raise ClientResponseError(url, response)

            data = response.json()
            yield from map(SafeTxConfirmation.parse_obj, data.get("results"))
            url = data.get("next")

    def post_transaction(self, safe_tx: SafeTx, sigs: Dict[AddressType, MessageSignature]):
        tx_data = UnexecutedTxData.from_safe_tx(safe_tx, self.safe_details.threshold)
        tx_data.signatures = HexBytes(
            reduce(
                lambda raw_sig, next_sig: raw_sig + next_sig.encode_rsv(),
                order_by_signer(sigs),
                b"",
            )
        )
        post_dict: Dict = {}
        for key, value in tx_data.dict().items():
            if isinstance(value, HexBytes):
                post_dict[key] = value.hex()
            elif isinstance(value, OperationType):
                post_dict[key] = int(value)
            elif isinstance(value, datetime):
                # not needed
                continue
            else:
                post_dict[key] = value

        url = f"{self.transaction_service_url}/api/v1/safes/{tx_data.safe}/multisig-transactions"
        json_data = {"origin": "ApeWorX/ape-safe", **post_dict}
        response = requests.post(url, json=json_data)

        if not response.ok:
            raise ClientResponseError(url, response)

    def post_signature(
        self,
        safe_tx_or_hash: Union[SafeTx, SafeTxID],
        signer: AddressType,
        signature: MessageSignature,
    ):
        if isinstance(safe_tx_or_hash, (SafeTxV1, SafeTxV2)):
            safe_tx = safe_tx_or_hash
            safe_tx_hash = hash_eip712_message(safe_tx).hex()
        else:
            safe_tx_hash = safe_tx_or_hash

        if not isinstance(safe_tx_hash, str):
            raise TypeError("Expecting str-like type for 'safe_tx_hash'.")

        url = (
            f"{self.transaction_service_url}/api"
            f"/v1/multisig-transactions/{safe_tx_hash}/confirmations"
        )
        response = requests.post(
            url, json={"origin": "ApeWorX/ape-safe", "signature": signature.encode_rsv().hex()}
        )

        if not response.ok:
            if "The requested resource was not found on this server" in response.text:
                raise MultisigTransactionNotFoundError(safe_tx_hash, url, response)

            raise ClientResponseError(url, response)


__all__ = [
    "ExecutedTxData",
    "MockSafeClient",
    "OperationType",
    "SafeApiTxData",
    "SafeClient",
    "SafeDetails",
    "SafeTx",
    "SafeTxConfirmation",
    "SafeTxV2",
    "SignatureType",
    "UnexecutedTxData",
]
