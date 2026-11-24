import json
import os
import time
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

from ape.types import AddressType, HexBytes, MessageSignature
from ape.utils import USER_AGENT, ZERO_ADDRESS, get_package_version
from eip712.common import SafeTxV1, SafeTxV2
from eth_abi import encode
from eth_utils import keccak, to_checksum_address, to_hex

from ape_safe.client.base import BaseSafeClient, RequestsClient
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
    remove_null_params,
)
from ape_safe.exceptions import (
    ActionNotPerformedError,
    ClientResponseError,
    MultisigTransactionNotFoundError,
    SafeClientException,
)
from ape_safe.utils import encode_signatures, get_safe_tx_hash

if TYPE_CHECKING:
    from ape.api import AccountAPI
    from requests import Response

APE_SAFE_VERSION = get_package_version(__name__)
APE_SAFE_USER_AGENT = f"Ape-Safe/{APE_SAFE_VERSION} {USER_AGENT}"
# NOTE: Origin must be a string, but can be json that contains url & name fields
ORIGIN = json.dumps({"url": "https://apeworx.io", "name": "Ape Safe", "ua": APE_SAFE_USER_AGENT})
assert len(ORIGIN) <= 200  # NOTE: Must be less than 200 chars

# URL for the multichain client gateway
SAFE_CLIENT_GATEWAY_URL = "https://api.safe.global/tx-service"
SAFE_QUEUE_API_URL = "https://api.safe.global/queue/api"
GATEWAY_API_KEY = os.environ.get("APE_SAFE_GATEWAY_API_KEY")
EIP3770_BLOCKCHAIN_NAMES_BY_CHAIN_ID = {
    1: "eth",  # Ethereum Mainnet
    11155111: "sep",  # Ethereum Sepolia
    10: "oeth",  # Optimism Mainnet
    42161: "arb1",  # Arbitrum One Mainnet
    56: "bnb",  # Binance Smart Chain
    146: "sonic",
    5000: "mantle",
    43114: "avax",
    1313161554: "aurora",
    8453: "base",  # Base Mainnet
    84532: "basesep",  # Base Sepolia
    42220: "celo",  # Celo Mainnet
    100: "gno",  # Gnosis Chain
    59144: "linea",  # Linea Mainnet
    137: "pol",  # Polygon
    534352: "scr",  # Scroll
    130: "unichain",  # Unichain Mainnet
    480: "wc",  # Worldchain Mainnet
    324: "zksync",  # zkSync Mainnet
    57073: "ink",  # Ink Mainnet
    800094: "berachain",  # Berachain Mainnet
}


class SafeClient(RequestsClient):
    """Client for the Safe Transaction and Queue Services."""

    def __init__(
        self,
        address: AddressType,
        override_url: str | None = None,
        chain_id: int | None = None,
    ) -> None:
        self.address = address
        self._use_queue = not override_url
        if override_url:
            override = urlsplit(override_url)
            host = override.hostname or ""
            self._use_queue = host == "api.safe.global" or (
                host.startswith("safe-transaction-") and host.endswith(".safe.global")
            )
            if host == "api.safe.global" and override.path.startswith("/tx-service/"):
                url_chain_name = override.path.split("/")[2]
                url_chain_id = next(
                    (
                        key
                        for key, name in EIP3770_BLOCKCHAIN_NAMES_BY_CHAIN_ID.items()
                        if name == url_chain_name
                    ),
                    None,
                )
                if url_chain_id and chain_id and url_chain_id != chain_id:
                    raise ValueError(
                        f"The hosted Safe URL is for chain {url_chain_id}, not {chain_id}."
                    )
                chain_id = chain_id or url_chain_id
            base_url = override_url.rstrip("/")
        else:
            if not chain_id:
                raise ValueError("Must provide one of chain_id or override_url.")
            chain_name = EIP3770_BLOCKCHAIN_NAMES_BY_CHAIN_ID.get(chain_id)
            if chain_name is None:
                raise ValueError(f"Chain ID {chain_id} is not a supported chain.")
            base_url = f"{SAFE_CLIENT_GATEWAY_URL}/{chain_name}/api"

        if self._use_queue:
            if not chain_id:
                raise ValueError("Provide chain_id when the hosted Safe URL does not identify it.")
            if not GATEWAY_API_KEY:
                raise ValueError(
                    """Must provide API key via 'APE_SAFE_GATEWAY_API_KEY='.

    Get one from https://developer.safe.global if you don't have one."""
                )

        self.chain_id = chain_id
        super().__init__(base_url)

    def _request(self, method: str, url: str, json: dict | None = None, **kwargs) -> "Response":
        # NOTE: Add authorization header
        headers = kwargs.pop("headers", {})
        headers.update({"Authorization": f"Bearer {GATEWAY_API_KEY}"})
        return super()._request(method, url, json=json, headers=headers, **kwargs)

    @property
    def safe_details(self) -> SafeDetails:
        response = self._get(f"/safes/{self.address}")
        return SafeDetails.model_validate(response.json())

    def get_next_nonce(self) -> int:
        return self.safe_details.nonce

    def _queue_request(self, method: str, path: str, **kwargs) -> "Response":
        return self._request(method, path, base_url=SAFE_QUEUE_API_URL, **kwargs)

    def _queue_results(self, path: str, params: dict) -> Iterator[dict]:
        offset = 0
        while True:
            page = self._queue_request("GET", path, params=params).json()
            yield from page["results"]
            if not (next_page := page.get("next")):
                return

            # Keep the original endpoint and filters when advancing to the next page.
            query = parse_qs(urlsplit(next_page).query)
            next_offset = int(query.get("offset", ["0"])[0])
            if next_offset <= offset:
                raise SafeClientException("Invalid Safe Queue Service pagination offset.")
            offset = next_offset
            params = {**params, "offset": offset}

    def _pending_transactions(self) -> Iterator[SafeApiTxData]:
        if not self._use_queue:
            yield from super()._pending_transactions()
            return

        details = self.safe_details
        params = {"safes": f"{self.address}:{self.chain_id}", "nonceOrder": "desc"}
        for txn in self._queue_results("/multisig-transactions/queue", params):
            if not self._matches_queue_scope(txn):
                raise SafeClientException(
                    "Safe Queue Service returned a transaction outside this Safe and chain."
                )
            if int(txn["nonce"]) < details.nonce:
                break
            if txn.get("txHash") is None:
                yield UnexecutedTxData.from_queue(txn, details.threshold)

    def _all_transactions(self) -> Iterator[SafeApiTxData]:
        if self._use_queue:
            yield from self._pending_transactions()
            yield from self._indexed_transactions(executed_only=True)
        else:
            yield from self._indexed_transactions()

    def _indexed_transactions(self, executed_only: bool = False) -> Iterator[SafeApiTxData]:
        url = f"/safes/{self.address}/multisig-transactions"
        params = {"executed": "true", "ordering": "-nonce"} if executed_only else {}
        while url:
            response = self._get(url, params=params, api_version="v2" if executed_only else "v1")
            data = response.json()

            for txn in data.get("results"):
                # NOTE: Using construct because of pydantic v2 back import validation error.
                if "isExecuted" in txn:
                    if txn["isExecuted"]:
                        yield ExecutedTxData.model_validate(txn)

                    elif not executed_only:
                        yield UnexecutedTxData.model_validate(txn)

                # else it is an incoming transaction

            url = data.get("next")
            params = {}

    def _indexed_safe_tx(self, safe_tx_hash: SafeTxID) -> SafeApiTxData | None:
        try:
            response = self._get(f"/multisig-transactions/{safe_tx_hash}", api_version="v2")
        except ClientResponseError as err:
            if self._use_queue and err.response.status_code != 404:
                raise
            return None

        data = remove_null_params(response.json())
        if self._use_queue and data["safe"].lower() != self.address.lower():
            return None
        if data.get("isExecuted"):
            return ExecutedTxData.model_validate(data)
        if self._use_queue:
            return None
        return UnexecutedTxData.model_validate(data)

    def get_safe_tx(self, safe_tx_hash: SafeTxID) -> SafeApiTxData | None:
        if self._use_queue:
            txn = self._queue_transaction(safe_tx_hash)
            if txn is not None and txn.get("txHash") is None:
                return UnexecutedTxData.from_queue(txn, self.safe_details.threshold)

        return self._indexed_safe_tx(safe_tx_hash)

    def _queue_transaction(self, safe_tx_hash: SafeTxID, *, required: bool = False) -> dict | None:
        path = f"/multisig-transactions/{safe_tx_hash}"
        response = self._queue_request("GET", path, allowed_statuses=(404,))
        if response.status_code != 404:
            txn = response.json()
            if txn["safeTxHash"].lower() == safe_tx_hash.lower() and self._matches_queue_scope(txn):
                return txn

        if required:
            raise MultisigTransactionNotFoundError(safe_tx_hash, response.url, response)
        return None

    def _matches_queue_scope(self, txn: dict) -> bool:
        return txn["safe"].lower() == self.address.lower() and int(txn["chainId"]) == self.chain_id

    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]:
        if safe_tx := self.get_safe_tx(safe_tx_hash):
            yield from safe_tx.confirmations

    def post_transaction(
        self, safe_tx: SafeTx, signatures: dict[AddressType, MessageSignature], **kwargs
    ):
        if self._use_queue:
            return self._post_queue_transaction(safe_tx, signatures, **kwargs)

        tx_data = UnexecutedTxData.from_safe_tx(safe_tx, self.safe_details.threshold)
        signature = encode_signatures(signatures)
        post_dict: dict = {
            "signature": signature.hex() if signature else None,
            "origin": ORIGIN,
        }

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

        url = f"/safes/{tx_data.safe}/multisig-transactions"
        response = self._post(url, json=post_dict, api_version="v2")
        return response

    def _post_queue_transaction(
        self, safe_tx: SafeTx, signatures: dict[AddressType, MessageSignature], **kwargs
    ) -> "Response":
        if not signatures:
            raise SafeClientException("A Safe Queue Service proposal needs at least one signature.")

        domain = safe_tx._eip712_domain_
        if (domain.verifyingContract or "").lower() != self.address.lower() or (
            isinstance(safe_tx, SafeTxV2) and domain.chainId != self.chain_id
        ):
            raise SafeClientException("The proposal belongs to a different Safe or chain.")

        safe_tx_hash = get_safe_tx_hash(safe_tx)
        if (expected_hash := kwargs.get("contractTransactionHash")) and (
            expected_hash.lower() != safe_tx_hash.lower()
        ):
            raise SafeClientException("The supplied hash does not match the proposal.")

        owners = {owner.lower() for owner in self.safe_details.owners}
        candidates = {address.lower(): signature for address, signature in signatures.items()}
        owner_signatures = {
            address: signature for address, signature in candidates.items() if address in owners
        }
        sender = kwargs.get("sender") or kwargs.get("submitter")
        proposer = sender.lower() if sender else None
        if proposer not in candidates:
            proposer = next(iter(owner_signatures or candidates))

        proposal_signatures = {proposer: candidates[proposer]}
        # A delegate or nested owner must propose with exactly one signature.
        if proposer in owners:
            proposal_signatures.update(owner_signatures)

        fields = safe_tx.model_dump(mode="json")
        if isinstance(safe_tx, SafeTxV1):
            fields["baseGas"] = fields.pop("dataGas")

        payload = {
            **fields,
            "chainId": self.chain_id,
            "safe": self.address,
            "data": to_hex(safe_tx.data) if safe_tx.data else None,
            "signatures": self._encode_queue_signatures(list(proposal_signatures.values())[:50]),
            "originName": kwargs.get("originName", "Ape Safe"),
            "originUrl": kwargs.get("originUrl", "https://apeworx.io"),
        }
        if "notes" in kwargs:
            payload["notes"] = kwargs["notes"]

        response = self._queue_request(
            "POST", "/multisig-transactions", json=payload, allowed_statuses=(409,)
        )
        if response.status_code == 409:
            # A repeated proposal used to add confirmations. Keep that behavior explicitly.
            response = self._queue_request("GET", f"/multisig-transactions/{safe_tx_hash}")

        result = response.json()
        if result["safeTxHash"].lower() != safe_tx_hash.lower() or not self._matches_queue_scope(
            result
        ):
            raise SafeClientException("Safe Queue Service returned a different transaction.")

        if result.get("txHash") is None:
            confirmed = {confirmation["owner"].lower() for confirmation in result["confirmations"]}
            self._post_queue_signatures(
                safe_tx_hash,
                {
                    owner: signature
                    for owner, signature in owner_signatures.items()
                    if owner not in confirmed
                },
            )

        return response

    @staticmethod
    def _encode_queue_signatures(signatures: list[MessageSignature]) -> list[str]:
        return [
            to_hex(signature.encode_rsv() if isinstance(signature, MessageSignature) else signature)
            for signature in signatures
        ]

    def _post_queue_signatures(
        self, safe_tx_hash: SafeTxID, signatures: dict[str, MessageSignature]
    ):
        url = f"/multisig-transactions/{safe_tx_hash}/signatures"
        items = list(signatures.items())
        for offset in range(0, len(items), 50):
            batch = items[offset : offset + 50]
            payload = {"signatures": self._encode_queue_signatures([sig for _, sig in batch])}
            response = self._queue_request("POST", url, json=payload, allowed_statuses=(404, 409))
            if response.status_code == 409:
                # The service rejects the whole batch if another signer beat us to one approval.
                txn = self._queue_transaction(safe_tx_hash)
                if txn is not None and txn.get("txHash") is None:
                    confirmed = {
                        confirmation["owner"].lower() for confirmation in txn["confirmations"]
                    }
                    missing = [sig for owner, sig in batch if owner not in confirmed]
                    if not missing:
                        continue
                    if len(missing) < len(batch):
                        payload = {"signatures": self._encode_queue_signatures(missing)}
                        response = self._queue_request(
                            "POST", url, json=payload, allowed_statuses=(404,)
                        )

            if response.status_code == 404:
                raise MultisigTransactionNotFoundError(safe_tx_hash, response.url, response)
            if response.status_code == 409:
                raise ClientResponseError(response.url, response)

    def post_signatures(
        self,
        safe_tx_or_hash: SafeTx | SafeTxID,
        signatures: dict[AddressType, MessageSignature],
    ):
        if isinstance(safe_tx_or_hash, (SafeTxV1, SafeTxV2)):
            safe_tx = safe_tx_or_hash
            safe_tx_hash = get_safe_tx_hash(safe_tx)
        else:
            safe_tx_hash = safe_tx_or_hash

        safe_tx_hash = cast("SafeTxID", to_hex(HexBytes(safe_tx_hash)))
        if self._use_queue:
            if signatures:
                self._queue_transaction(safe_tx_hash, required=True)
                self._post_queue_signatures(
                    safe_tx_hash,
                    {owner.lower(): signature for owner, signature in signatures.items()},
                )
            return

        url = f"/multisig-transactions/{safe_tx_hash}/confirmations"
        signature = to_hex(encode_signatures(signatures))
        try:
            self._post(url, json={"signature": signature})
        except ClientResponseError as err:
            if "The requested resource was not found on this server" in err.response.text:
                raise MultisigTransactionNotFoundError(safe_tx_hash, url, err.response) from err

            raise  # The error from BaseClient we are already raising (no changes)

    def estimate_gas_cost(
        self, receiver: AddressType, value: int, data: bytes, operation: int = 0
    ) -> int | None:
        url = f"/safes/{self.address}/multisig-transactions/estimations"
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
        url = "/delegates"
        delegates: dict[AddressType, list[AddressType]] = {}

        if self._use_queue:
            for owner in self.safe_details.owners:
                addresses = list(
                    dict.fromkeys(
                        to_checksum_address(entry["delegate"])
                        for entry in self._queue_delegates(delegator=owner)
                    )
                )
                if addresses:
                    delegates[owner] = addresses
            return delegates

        while url:
            response = self._get(url, params={"safe": self.address}, api_version="v2")
            data = response.json()

            for delegate_info in map(DelegateInfo.model_validate, data.get("results", [])):
                if delegate_info.delegator not in delegates:
                    delegates[delegate_info.delegator] = [delegate_info.delegate]
                else:
                    delegates[delegate_info.delegator].append(delegate_info.delegate)

            url = data.get("next")

        return delegates

    def is_delegate(self, address: AddressType) -> bool:
        if not self._use_queue:
            return super().is_delegate(address)

        # Searching by address also finds delegations valid for all Safes.
        owners = {owner.lower() for owner in self.safe_details.owners}
        return any(
            entry["delegator"].lower() in owners
            for entry in self._queue_delegates(delegate=address)
        )

    def _queue_delegates(self, **params) -> Iterator[dict]:
        for entry in self._queue_results("/delegates", params):
            safe = (entry.get("safe") or ZERO_ADDRESS).lower()
            chain_id = int(entry.get("chainId") or 0)
            if safe in (ZERO_ADDRESS, self.address.lower()) and chain_id in (0, self.chain_id):
                yield entry

    def add_delegate(self, delegate: "AddressType", label: str, delegator: "AccountAPI"):
        if self._use_queue:
            if delegator.address.lower() not in {
                owner.lower() for owner in self.safe_details.owners
            }:
                raise SafeClientException(f"'{delegator.address}' is not an owner of this Safe.")

            payload = self._queue_delegate_payload(delegate, delegator, "add")
            payload["label"] = label
            response = self._queue_request(
                "POST", "/delegates", json=payload, allowed_statuses=(409,)
            )
            if response.status_code == 409:
                payload = self._queue_delegate_payload(delegate, delegator, "edit")
                payload["label"] = label
                self._queue_request("PATCH", "/delegates", json=payload)
            return

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
        self._post("/delegates", json=payload, api_version="v2")

    def remove_delegate(self, delegate: "AddressType", delegator: "AccountAPI"):
        if self._use_queue:
            if not self.chain_id or ZERO_ADDRESS in (delegate.lower(), self.address.lower()):
                raise SafeClientException(
                    "Removing a delegate requires a specific delegate and Safe."
                )
            payload = self._queue_delegate_payload(delegate, delegator, "delete")
            response = self._queue_request(
                "DELETE", "/delegates", json=payload, allowed_statuses=(404,)
            )
            if response.status_code == 404:
                if any(
                    entry["delegator"].lower() == delegator.address.lower()
                    and (
                        (entry.get("safe") or ZERO_ADDRESS).lower() == ZERO_ADDRESS
                        or int(entry.get("chainId") or 0) == 0
                    )
                    for entry in self._queue_delegates(delegate=delegate)
                ):
                    raise SafeClientException(
                        "This delegate is registered across multiple Safes or chains. "
                        "Remove it from the service with its original scope."
                    )
                raise ClientResponseError(response.url, response)
            return

        msg_hash = self.create_delegate_message(delegate)

        # NOTE: This is required as Safe API uses an antiquated .signHash method
        if not (sig := delegator.sign_raw_msghash(msg_hash)):
            raise ActionNotPerformedError("Did not sign delegate removal")

        payload = {
            "delegator": delegator.address,
            "signature": sig.encode_rsv().hex(),
        }
        self._delete(f"/delegates/{delegate}", json=payload, api_version="v2")

    def _queue_delegate_payload(
        self, delegate: AddressType, delegator: "AccountAPI", action: str
    ) -> dict:
        digest = self.create_delegate_message(delegate, action=action)
        if not (signature := delegator.sign_raw_msghash(digest)):
            raise ActionNotPerformedError(f"Did not sign delegate action '{action}'")

        return {
            "chainId": self.chain_id,
            "safe": self.address,
            "delegate": delegate,
            "delegator": delegator.address,
            "signature": to_hex(signature.encode_rsv()),
        }

    def create_delegate_message(self, delegate: AddressType, *, action: str = "add") -> HexBytes:
        if not self._use_queue:
            return super().create_delegate_message(delegate)

        # The Queue Service uses a custom EIP-712 domain field named `safe`.
        domain_hash = keccak(
            encode(
                ["bytes32", "bytes32", "bytes32", "uint256", "address"],
                [
                    keccak(
                        text="EIP712Domain(string name,string version,uint256 chainId,address safe)"
                    ),
                    keccak(text="Safe Queue Service"),
                    keccak(text="1.0"),
                    self.chain_id,
                    self.address,
                ],
            )
        )
        delegate_hash = keccak(
            encode(
                ["bytes32", "address", "uint256", "bytes32"],
                [
                    keccak(text="Delegate(address delegateAddress,uint256 totp,string action)"),
                    delegate,
                    int(time.time()) // 3600,
                    keccak(text=action),
                ],
            )
        )
        return HexBytes(keccak(b"\x19\x01" + domain_hash + delegate_hash))


__all__ = [
    "ExecutedTxData",
    "BaseSafeClient",
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
