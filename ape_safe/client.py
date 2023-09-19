from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from functools import reduce
from typing import Dict, Iterator, List, NewType, Optional, Set, Union

import requests  # type: ignore
from ape.contracts import ContractInstance
from ape.types import AddressType, HexBytes, MessageSignature
from ape.utils import ZERO_ADDRESS, ManagerAccessMixin
from eip712.common import SafeTxV1, SafeTxV2
from eip712.messages import hash_eip712_message
from eth_utils import keccak
from pydantic import BaseModel

from .exceptions import ClientResponseError, ClientUnsupportedChainError
from .utils import order_by_signer

SafeTx = Union[SafeTxV1, SafeTxV2]
SafeTxID = NewType("SafeTxID", str)

TRANSACTION_SERVICE_URL = {
    1: "https://safe-transaction-mainnet.safe.global",
    5: "https://safe-transaction-goerli.safe.global",
    10: "https://safe-transaction-optimism.safe.global",
    56: "https://safe-transaction-bsc.safe.global",
    100: "https://safe-transaction-gnosis-chain.safe.global",
    137: "https://safe-transaction-polygon.safe.global",
    250: "https://safe-txservice.fantom.network",
    288: "https://safe-transaction.mainnet.boba.network",
    # NOTE: Not supported yet
    # 8453: "https://safe-transaction-base.safe.global/",
    42161: "https://safe-transaction-arbitrum.safe.global",
    43114: "https://safe-transaction-avalanche.safe.global",
    84531: "https://safe-transaction-base-testnet.safe.global/",
}


class SafeDetails(BaseModel):
    address: AddressType
    nonce: int
    threshold: int
    owners: List[AddressType]
    masterCopy: AddressType
    modules: List[AddressType]
    fallbackHandler: AddressType
    guard: AddressType
    version: str


class SignatureType(str, Enum):
    APPROVED_HASH = "APPROVED_HASH"
    EOA = "EOA"
    ETH_SIGN = "ETH_SIGN"


class SafeTxConfirmation(BaseModel):
    owner: AddressType
    submissionDate: datetime
    transactionHash: Optional[HexBytes] = None
    signature: HexBytes
    signatureType: SignatureType


class OperationType(int, Enum):
    CALL = 0
    DELEGATECALL = 1


class UnexecutedTxData(BaseModel):
    safe: AddressType
    to: AddressType
    value: int
    data: Optional[HexBytes] = None
    operation: OperationType
    gasToken: AddressType
    safeTxGas: int
    baseGas: int
    gasPrice: int
    refundReceiver: AddressType
    nonce: int
    submissionDate: datetime
    modified: datetime
    safeTxHash: SafeTxID
    confirmationsRequired: int
    confirmations: List[SafeTxConfirmation] = []
    trusted: bool = True
    signatures: Optional[HexBytes] = None

    @classmethod
    def from_safe_tx(cls, safe_tx: SafeTx, confirmations_required: int) -> "UnexecutedTxData":
        return cls(  # type: ignore[arg-type]
            safe=safe_tx._verifyingContract_,
            submissionDate=datetime.now(),
            modified=datetime.now(),
            confirmationsRequired=confirmations_required,
            safeTxHash=hash_eip712_message(safe_tx).hex(),
            **safe_tx._body_["message"],
        )

    def __str__(self) -> str:
        # TODO: Decode data
        data_hex = self.data.hex() if self.data else ""
        if len(data_hex) > 40:
            data_hex = f"{data_hex[:18]}....{data_hex[-18:]}"

        # TODO: Handle MultiSend contract differently
        return f"""Tx ID {self.nonce}
   type: {self.operation._name_}
   from: {self.safe}
     to: {self.to}
  value: {self.value / 1e18} ether
   data: 0x{data_hex}
"""


class ExecutedTxData(UnexecutedTxData):
    executionDate: datetime
    blockNumber: int
    transactionHash: HexBytes
    executor: AddressType
    isExecuted: bool
    isSuccessful: bool
    ethGasPrice: int
    maxFeePerGas: Optional[int] = None
    maxPriorityFeePerGas: Optional[int] = None
    gasUsed: int
    fee: int
    origin: str
    dataDecoded: Optional[dict] = None


SafeApiTxData = Union[ExecutedTxData, UnexecutedTxData]


class BaseSafeClient(ABC):
    @property
    @abstractmethod
    def safe_details(self) -> SafeDetails:
        ...

    @abstractmethod
    def get_next_nonce(self) -> int:
        ...

    @abstractmethod
    def _all_transactions(self) -> Iterator[SafeApiTxData]:
        ...

    def get_transactions(
        self,
        confirmed: Optional[bool] = None,
        starting_nonce: int = 0,
        filter_by_ids: Optional[Set[SafeTxID]] = None,
        filter_by_missing_signers: Optional[Set[AddressType]] = None,
    ) -> Iterator[SafeApiTxData]:
        """
        confirmed: Confirmed if True, not confirmed if False, both if None
        """
        next_nonce = self.get_next_nonce()

        for txn in self._all_transactions():
            if txn.nonce < starting_nonce:
                break  # NOTE: order is largest nonce to smallest, so safe to break here

            is_confirmed = len(txn.confirmations) >= txn.confirmationsRequired

            if confirmed is not None:
                if not confirmed and isinstance(txn, ExecutedTxData):
                    break  # NOTE: Break at the first executed transaction

                elif confirmed and not is_confirmed:
                    continue  # NOTE: Skip not confirmed transactions

            if txn.nonce < next_nonce and isinstance(txn, UnexecutedTxData):
                continue  # NOTE: Skip orphaned transactions

            if filter_by_ids and txn.safeTxHash not in filter_by_ids:
                continue  # NOTE: Skip transactions not in the filter

            if filter_by_missing_signers and filter_by_missing_signers.issubset(
                set(conf.owner for conf in txn.confirmations)
            ):
                # NOTE: Skip if all signers from `filter_by_missing_signers`
                #       are in `txn.confirmations`
                continue

            yield txn

    @abstractmethod
    def get_confirmations(self, safe_tx_hash: SafeTxID) -> Iterator[SafeTxConfirmation]:
        ...

    @abstractmethod
    def post_transaction(self, safe_tx: SafeTx, sigs: Dict[AddressType, MessageSignature]):
        ...

    @abstractmethod
    def post_signature(
        self, safe_tx_hash: SafeTxID, signer: AddressType, signature: MessageSignature
    ):
        ...


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

            for txn in data["results"]:
                if "isExecuted" in txn and txn["isExecuted"]:
                    yield ExecutedTxData.parse_obj(txn)

                else:
                    yield UnexecutedTxData.parse_obj(txn)

            url = data["next"]

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
            yield from map(SafeTxConfirmation.parse_obj, data["results"])
            url = data["next"]

    def post_transaction(self, safe_tx: SafeTx, sigs: Dict[AddressType, MessageSignature]):
        tx_data = UnexecutedTxData.from_safe_tx(safe_tx, self.safe_details.threshold)
        tx_data.signatures = HexBytes(
            reduce(
                lambda raw_sig, next_sig: raw_sig + next_sig.encode_rsv(),
                order_by_signer(sigs),
                b"",
            )
        )

        url = f"{self.transaction_service_url}/api/v1/multisig-transactions"
        response = requests.post(url, json={"origin": "ApeWorX/ape-safe", **tx_data.dict()})

        if not response.ok:
            raise ClientResponseError(url, response)

    def post_signature(
        self, safe_tx_hash: SafeTxID, signer: AddressType, signature: MessageSignature
    ):
        url = (
            f"{self.transaction_service_url}/api"
            f"/v1/multisig-transactions/{str(safe_tx_hash)}/confirmations"
        )
        response = requests.post(
            url, json={"origin": "ApeWorX/ape-safe", "signature": signature.encode_rsv().hex()}
        )

        if not response.ok:
            raise ClientResponseError(url, response)


class MockSafeClient(BaseSafeClient, ManagerAccessMixin):
    def __init__(self, contract: ContractInstance):
        self.contract = contract
        self.transactions: Dict[SafeTxID, SafeApiTxData] = {}
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
            modules=self.contract.getModules() if hasattr(self.contract, "getModules") else [],
            # TODO: Add fallback handler getter
            fallbackHandler=fallback_address,
            guard=self.contract.getGuard() if hasattr(self.contract, "getGuard") else ZERO_ADDRESS,
            version=self.contract.VERSION(),
        )

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
                submissionDate=datetime.now(),
                signature=sig.encode_rsv(),
                signatureType=SignatureType.EOA,
            )
            for signer, sig in sigs.items()
        )
        self.transactions[safe_tx_data.safeTxHash] = safe_tx_data

        if safe_tx_data.nonce in self.transactions_by_nonce:
            self.transactions_by_nonce[safe_tx_data.nonce].append(safe_tx_data.safeTxHash)
        else:
            self.transactions_by_nonce[safe_tx_data.nonce] = [safe_tx_data.safeTxHash]

    def post_signature(
        self, safe_tx_hash: SafeTxID, signer: AddressType, signature: MessageSignature
    ):
        self.transactions[safe_tx_hash].confirmations.append(
            SafeTxConfirmation(
                owner=signer,
                submissionDate=datetime.now(),
                signature=signature.encode_rsv(),
                signatureType=SignatureType.EOA,
            )
        )
