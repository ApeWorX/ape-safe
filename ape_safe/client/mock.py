from datetime import datetime, timezone
from typing import Dict, Iterator, List, Union

from ape.contracts import ContractInstance
from ape.types import AddressType, MessageSignature
from ape.utils import ZERO_ADDRESS, ManagerAccessMixin
from eth_utils import keccak

from ape_safe.client.base import BaseSafeClient
from ape_safe.client.models import (
    SafeApiTxData,
    SafeDetails,
    SafeTx,
    SafeTxConfirmation,
    SafeTxID,
    SignatureType,
    UnexecutedTxData,
)


class MockSafeClient(BaseSafeClient, ManagerAccessMixin):
    def __init__(self, contract: ContractInstance):
        self.contract = contract
        self.transactions: Dict[Union[SafeTx, SafeTxID], SafeApiTxData] = {}
        self.transactions_by_nonce: Dict[int, List[SafeTxID]] = {}

    @property
    def safe_details(self) -> SafeDetails:
        slot = keccak(text="fallback_manager.handler.address")
        value = self.provider.get_storage_at(self.contract.address, slot)
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
    def guard(self) -> AddressType:
        return (
            self.contract.getGuard() if "getGuard" in self.contract._view_methods_ else ZERO_ADDRESS
        )

    @property
    def modules(self) -> List[AddressType]:
        return self.contract.getModules() if "getModules" in self.contract._view_methods_ else []

    def get_next_nonce(self) -> int:
        return self.contract._view_methods_["nonce"]()

    def _all_transactions(
        self,
    ) -> Iterator[SafeApiTxData]:
        for nonce in sorted(self.transactions_by_nonce.keys(), reverse=True):
            yield from map(self.transactions.get, self.transactions_by_nonce[nonce])

    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]:
        if safe_tx_data := self.transactions.get(safe_tx_hash):
            yield from safe_tx_data.confirmations

    def post_transaction(self, safe_tx: SafeTx, sigs: Dict[AddressType, MessageSignature]):
        safe_tx_data = UnexecutedTxData.from_safe_tx(safe_tx, self.safe_details.threshold)
        safe_tx_data.confirmations.extend(
            SafeTxConfirmation(
                owner=signer,
                submissionDate=datetime.now(timezone.utc),
                signature=sig.encode_rsv(),
                signatureType=SignatureType.EOA,
            )
            for signer, sig in sigs.items()
        )
        self.transactions[safe_tx_data.safe_tx_hash] = safe_tx_data

        if safe_tx_data.nonce in self.transactions_by_nonce:
            self.transactions_by_nonce[safe_tx_data.nonce].append(safe_tx_data.safe_tx_hash)
        else:
            self.transactions_by_nonce[safe_tx_data.nonce] = [safe_tx_data.safe_tx_hash]

    def post_signature(
        self,
        safe_tx_or_hash: Union[SafeTx, SafeTxID],
        signer: AddressType,
        signature: MessageSignature,
    ):
        self.transactions[safe_tx_or_hash].confirmations.append(
            SafeTxConfirmation(
                owner=signer,
                submissionDate=datetime.now(timezone.utc),
                signature=signature.encode_rsv(),
                signatureType=SignatureType.EOA,
            )
        )
