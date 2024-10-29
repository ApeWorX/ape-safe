from collections.abc import Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Union, cast

from ape.utils import ZERO_ADDRESS, ManagerAccessMixin
from eth_utils import keccak
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
from ape_safe.utils import get_safe_tx_hash

if TYPE_CHECKING:
    from ape.contracts import ContractInstance
    from ape.types import AddressType, MessageSignature


class MockSafeClient(BaseSafeClient, ManagerAccessMixin):
    def __init__(self, contract: "ContractInstance"):
        self.contract = contract
        self.transactions: dict[SafeTxID, SafeApiTxData] = {}
        self.transactions_by_nonce: dict[int, list[SafeTxID]] = {}

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

    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]:
        tx_hash = cast(SafeTxID, HexBytes(safe_tx_hash).hex())
        if safe_tx_data := self.transactions.get(tx_hash):
            yield from safe_tx_data.confirmations

    def post_transaction(
        self, safe_tx: SafeTx, signatures: dict["AddressType", "MessageSignature"], **kwargs
    ):
        safe_tx_data = UnexecutedTxData.from_safe_tx(safe_tx, self.safe_details.threshold)
        safe_tx_data.confirmations.extend(
            SafeTxConfirmation(
                owner=signer,
                submissionDate=datetime.now(timezone.utc),
                signature=sig.encode_rsv(),
                signatureType=SignatureType.EOA,
            )
            for signer, sig in signatures.items()
        )
        tx_id = cast(SafeTxID, HexBytes(safe_tx_data.safe_tx_hash).hex())
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
            tx_id = cast(SafeTxID, HexBytes(safe_tx_id).hex())
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
