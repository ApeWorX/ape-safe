from datetime import datetime
from enum import Enum
from functools import reduce
from typing import Iterator, List, NewType, Optional, Set, Union

import requests  # type: ignore
from ape.types import AddressType, HexBytes, MessageSignature
from eip712.common import SafeTxV1, SafeTxV2
from pydantic import BaseModel

from .exceptions import ClientResponseError, ClientUnsupportedChainError

SafeTx = Union[SafeTxV1, SafeTxV2]
SafeTxID = NewType("SafeTxID", HexBytes)

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
    confirmations: List[SafeTxConfirmation]
    trusted: bool
    signatures: Optional[HexBytes] = None

    @classmethod
    def from_safe_tx(cls, safe_tx: SafeTx) -> "UnexecutedTxData":
        return cls(  # type: ignore[arg-type]
            safe=safe_tx._verifyingContract_,
            **safe_tx,
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


class SafeClient:
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

    def _all_transactions(self) -> Iterator[dict]:
        """
        confirmed: Confirmed if True, not confirmed if False, both if None
        """

        url = f"{self.transaction_service_url}/api/v1/safes/{self.address}/transactions"
        while url:
            response = requests.get(url)
            if not response.ok:
                raise ClientResponseError(url, response)

            data = response.json()
            yield from data["results"]
            url = data["next"]

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
            if txn["nonce"] < starting_nonce:
                break  # NOTE: order is largest nonce to smallest, so safe to break here

            isConfirmed = len(txn["confirmations"]) >= txn["confirmationsRequired"]
            isExecuted = "isExecuted" in txn and txn["isExecuted"]

            if confirmed is not None:
                if not confirmed and isExecuted:
                    break  # NOTE: Break at the first executed transaction

                elif confirmed and not isConfirmed:
                    continue  # NOTE: Skip not confirmed transactions

            if txn["nonce"] < next_nonce and not isExecuted:
                continue  # NOTE: Skip orphaned transactions

            if filter_by_ids and txn["safeTxHash"] not in filter_by_ids:
                continue  # NOTE: Skip transactions not in the filter

            if filter_by_missing_signers and filter_by_missing_signers.issubset(
                set(conf["owner"] for conf in txn["confirmations"])
            ):
                # NOTE: Skip if all signers from `filter_by_missing_signers`
                #       are in `txn.confirmations`
                continue

            yield ExecutedTxData.parse_obj(txn) if isExecuted else UnexecutedTxData.parse_obj(txn)

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

    def post_transaction(self, safe_tx: SafeTx, sigs: Optional[List[MessageSignature]] = None):
        tx_data = UnexecutedTxData.from_safe_tx(safe_tx)
        if sigs:
            tx_data.signatures = HexBytes(
                reduce(lambda raw_sig, next_sig: raw_sig + next_sig.encode_vrs(), sigs, b"")
            )

        url = f"{self.transaction_service_url}/api/v1/multisig-transactions"
        response = requests.post(url, json=tx_data.dict())

        if not response.ok:
            raise ClientResponseError(url, response)

    def post_signature(self, safe_tx_hash: SafeTxID, signature: MessageSignature):
        url = (
            f"{self.transaction_service_url}/api"
            f"/v1/multisig-transactions/{str(safe_tx_hash)}/confirmations"
        )
        response = requests.post(url, json={"signature": signature.encode_vrs().hex()})

        if not response.ok:
            raise ClientResponseError(url, response)
