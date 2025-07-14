from collections.abc import Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Union, cast

from ape.utils import ZERO_ADDRESS, ManagerAccessMixin
from eth_utils import keccak, to_hex
from hexbytes import HexBytes

from ape_safe.client.base import BaseSafeClient
from ape_safe.client.types import (
    SafeApiTxData,
    SafeDetails,
    SafeTx,
    SafeTxConfirmation,
    SafeTxID,
    SignatureType,
    UnexecutedTxData,
)
from ape_safe.exceptions import SafeClientException
from ape_safe.utils import get_safe_tx_hash

if TYPE_CHECKING:
    from ape.api import AccountAPI
    from ape.contracts import ContractInstance
    from ape.types import AddressType, MessageSignature


class MockSafeClient(BaseSafeClient, ManagerAccessMixin):
    def __init__(self, contract: "ContractInstance"):
        self.contract = contract
        self.transactions: dict[SafeTxID, SafeApiTxData] = {}
        self.transactions_by_nonce: dict[int, list[SafeTxID]] = {}
        self.delegates: dict["AddressType", list["AddressType"]] = {}

    @property
    def safe_details(self) -> SafeDetails:
        slot = keccak(text="fallback_manager.handler.address")
        value = self.provider.get_storage(self.contract.address, slot)
        fallback_address = self.network_manager.ecosystem.decode_address(value[-20:])

        return SafeDetails(
            address=self.contract.address,
            nonce=self.get_next_nonce(),
            threshold=self.contract.getThreshold(),
            owners=self.contract.getOwners(),
            masterCopy=self.contract.masterCopy(),
            modules=self.modules,
            # TODO: Add fallback handler getter
            fallbackHandler=fallback_address,
            guard=self.guard,
            version=self.contract.VERSION(),
        )

    @property
    def guard(self) -> "AddressType":
        return (
            self.contract.getGuard() if "getGuard" in self.contract._view_methods_ else ZERO_ADDRESS
        )

    @property
    def modules(self) -> list["AddressType"]:
        return self.contract.getModules() if "getModules" in self.contract._view_methods_ else []

    def get_next_nonce(self) -> int:
        return self.contract._view_methods_["nonce"]()

    def _all_transactions(
        self,
    ) -> Iterator[SafeApiTxData]:
        for nonce in sorted(self.transactions_by_nonce.keys(), reverse=True):
            for tx in map(self.transactions.get, self.transactions_by_nonce[nonce]):
                if tx:
                    yield tx

    def get_safe_tx(self, safe_tx_hash: SafeTxID) -> SafeApiTxData:
        tx_hash = cast(SafeTxID, to_hex(HexBytes(safe_tx_hash)))

        if safe_tx := self.transactions.get(tx_hash):
            return safe_tx

        for safe_tx in self._all_transactions():
            if safe_tx.safe_tx_hash == safe_tx_hash:
                return safe_tx

        raise SafeClientException(f"Unable to find SafeTx '{safe_tx_hash}'.")

    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]:
        tx_hash = cast(SafeTxID, to_hex(HexBytes(safe_tx_hash)))
        if safe_tx_data := self.transactions.get(tx_hash):
            yield from safe_tx_data.confirmations

    def post_transaction(
        self, safe_tx: SafeTx, signatures: dict["AddressType", "MessageSignature"], **kwargs
    ):
        owners = self.safe_details.owners

        safe_tx_data = UnexecutedTxData.from_safe_tx(safe_tx, self.safe_details.threshold)
        safe_tx_data.confirmations.extend(
            SafeTxConfirmation(
                owner=signer,
                submissionDate=datetime.now(timezone.utc),
                signature=sig.encode_rsv(),
                signatureType=SignatureType.EOA,
            )
            for signer, sig in signatures.items()
            if signer in owners
        )

        # Ensure that if this is a zero-conf SafeTx, that at least one signature is from a delegate
        # NOTE: More strict than Safe API check that silently ignores if no signatures are valid or
        #       from delegates, but should help us to get correct logic for mock testing purposes
        if len(safe_tx_data.confirmations) == 0 and not any(
            self.delegator_for_delegate(delegate) in owners
            for delegate in filter(lambda signer: signer not in owners, signatures)
        ):
            # NOTE: mimic real exception for mock testing purposes
            raise SafeClientException(
                "At least one signature must be from a valid owner of the safe"
            )

        tx_id = cast(SafeTxID, to_hex(HexBytes(safe_tx_data.safe_tx_hash)))
        self.transactions[tx_id] = safe_tx_data
        if safe_tx_data.nonce in self.transactions_by_nonce:
            self.transactions_by_nonce[safe_tx_data.nonce].append(tx_id)
        else:
            self.transactions_by_nonce[safe_tx_data.nonce] = [tx_id]

    def post_signatures(
        self,
        safe_tx_or_hash: Union[SafeTx, SafeTxID],
        signatures: dict["AddressType", "MessageSignature"],
    ):
        for signer, signature in signatures.items():
            safe_tx_id = (
                safe_tx_or_hash
                if isinstance(safe_tx_or_hash, (str, bytes, int))
                else get_safe_tx_hash(safe_tx_or_hash)
            )
            tx_id = cast(SafeTxID, to_hex(HexBytes(safe_tx_id)))
            self.transactions[tx_id].confirmations.append(
                SafeTxConfirmation(
                    owner=signer,
                    submissionDate=datetime.now(timezone.utc),
                    signature=signature.encode_rsv(),
                    signatureType=SignatureType.EOA,
                )
            )

    def estimate_gas_cost(
        self, receiver: "AddressType", value: int, data: bytes, operation: int = 0
    ) -> Optional[int]:
        return None  # Estimate gas normally

    def get_delegates(self) -> dict["AddressType", list["AddressType"]]:
        return self.delegates

    def delegator_for_delegate(self, delegate: "AddressType") -> Optional["AddressType"]:
        for delegator, delegates in self.delegates.items():
            if delegate in delegates:
                return delegator

        return None

    def add_delegate(self, delegate: "AddressType", label: str, delegator: "AccountAPI"):
        if delegator.address not in self.safe_details.owners:
            raise SafeClientException(f"'{delegator}' not a valid owner.")

        if delegator.address in self.delegates:
            self.delegates[delegator.address].append(delegate)

        else:
            self.delegates[delegator.address] = [delegate]

    def remove_delegate(self, delegate: "AddressType", delegator: "AccountAPI"):
        if delegator.address not in self.safe_details.owners:
            raise SafeClientException(f"'{delegator.address}' not a valid owner.")

        elif delegator.address not in self.delegates:
            raise SafeClientException(
                f"'{delegate}' not a valid delegate for '{delegator.address}'."
            )

        self.delegates[delegator.address].remove(delegate)

        if len(self.delegates[delegator.address]) == 0:
            del self.delegates[delegator.address]
