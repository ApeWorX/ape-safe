import json
from collections.abc import Iterator
from datetime import datetime
from functools import reduce
from typing import TYPE_CHECKING, Optional, Union, cast

from ape.types import AddressType, HexBytes, MessageSignature
from ape.utils import USER_AGENT, get_package_version
from eip712.common import SafeTxV1, SafeTxV2
from eth_utils import to_hex

from ape_safe.client.base import BaseSafeClient
from ape_safe.client.mock import MockSafeClient
from ape_safe.client.types import (
    DelegateInfo,
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
    ActionNotPerformedError,
    ClientResponseError,
    ClientUnsupportedChainError,
    MultisigTransactionNotFoundError,
)
from ape_safe.utils import get_safe_tx_hash, order_by_signer

if TYPE_CHECKING:
    from ape.api import AccountAPI

APE_SAFE_VERSION = get_package_version(__name__)
APE_SAFE_USER_AGENT = f"Ape-Safe/{APE_SAFE_VERSION} {USER_AGENT}"
# NOTE: Origin must be a string, but can be json that contains url & name fields
ORIGIN = json.dumps(dict(url="https://apeworx.io", name="Ape Safe", ua=APE_SAFE_USER_AGENT))
assert len(ORIGIN) <= 200  # NOTE: Must be less than 200 chars

TRANSACTION_SERVICE_URL = {
    # NOTE: If URLs need to be updated, a list of available service URLs can be found at
    # https://docs.safe.global/safe-core-api/available-services.
    # NOTE: There should be no trailing slashes at the end of the URL.
    1: "https://safe-transaction-mainnet.safe.global",
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
    11155111: "https://safe-transaction-sepolia.safe.global",
    81457: "https://transaction.blast-safe.io",
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
            tx_service_url = override_url

        elif chain_id:
            if chain_id not in TRANSACTION_SERVICE_URL:
                raise ClientUnsupportedChainError(chain_id)

            tx_service_url = TRANSACTION_SERVICE_URL[chain_id]

        else:
            raise ValueError("Must provide one of chain_id or override_url.")

        super().__init__(tx_service_url)

    @property
    def safe_details(self) -> SafeDetails:
        response = self._get(f"safes/{self.address}/")
        return SafeDetails.model_validate(response.json())

    def get_next_nonce(self) -> int:
        return self.safe_details.nonce

    def _all_transactions(self) -> Iterator[SafeApiTxData]:
        """
        Get all transactions from safe, both confirmed and unconfirmed
        """

        url = f"safes/{self.address}/all-transactions/"
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
        url = f"multisig-transactions/{str(safe_tx_hash)}/confirmations/"
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
        post_dict: dict = {"signature": signature.hex() if signature else None, "origin": ORIGIN}

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

        url = f"safes/{tx_data.safe}/multisig-transactions/"
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
        url = f"multisig-transactions/{safe_tx_hash}/confirmations/"
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
        url = f"safes/{self.address}/multisig-transactions/estimations/"
        request: dict = {
            "to": receiver,
            "value": value,
            "data": to_hex(HexBytes(data)),
            "operation": operation,
        }
        result = self._post(url, json=request).json()
        gas = result.get("safeTxGas")
        return int(to_hex(HexBytes(gas)), 16)

    def get_delegates(self) -> dict["AddressType", list["AddressType"]]:
        url = "delegates/"
        delegates: dict[AddressType, list[AddressType]] = {}

        while url:
            response = self._get(url, params={"safe": self.address})
            data = response.json()

            for delegate_info in map(DelegateInfo.model_validate, data.get("results", [])):
                if delegate_info.delegator not in delegates:
                    delegates[delegate_info.delegator] = [delegate_info.delegate]
                else:
                    delegates[delegate_info.delegator].append(delegate_info.delegate)

            url = data.get("next")

        return delegates

    def add_delegate(self, delegate: "AddressType", label: str, delegator: "AccountAPI"):
        msg_hash = self.create_delegate_message(delegate)

        # NOTE: This is required as Safe API uses an antiquated .signHash method
        if not (sig := delegator.sign_raw_msghash(msg_hash)):
            raise ActionNotPerformedError("Did not sign delegate approval")

        payload = {
            "safe": self.address,
            "delegate": delegate,
            "delegator": delegator.address,
            "label": label,
            "signature": sig.encode_rsv().hex(),
        }
        self._post("delegates/", json=payload)

    def remove_delegate(self, delegate: "AddressType", delegator: "AccountAPI"):
        msg_hash = self.create_delegate_message(delegate)

        # NOTE: This is required as Safe API uses an antiquated .signHash method
        if not (sig := delegator.sign_raw_msghash(msg_hash)):
            raise ActionNotPerformedError("Did not sign delegate removal")

        payload = {
            "delegator": delegator.address,
            "signature": sig.encode_rsv().hex(),
        }
        self._delete(f"delegates/{delegate}/", json=payload)


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
