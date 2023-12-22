from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, NewType, Optional, Union, cast

from ape.types import AddressType, HexBytes
from eip712.common import SafeTxV1, SafeTxV2
from eth_typing import HexStr
from eth_utils import add_0x_prefix
from pydantic import BaseModel, Field

from ape_safe.utils import get_safe_tx_hash

SafeTx = Union[SafeTxV1, SafeTxV2]
SafeTxID = NewType("SafeTxID", str)


class SafeDetails(BaseModel):
    address: AddressType
    nonce: int
    threshold: int
    owners: List[AddressType]
    master_copy: AddressType = Field(alias="masterCopy")
    modules: List[AddressType]
    fallback_handler: AddressType = Field(alias="fallbackHandler")
    guard: AddressType
    version: str


class SignatureType(str, Enum):
    APPROVED_HASH = "APPROVED_HASH"
    EOA = "EOA"
    ETH_SIGN = "ETH_SIGN"


class SafeTxConfirmation(BaseModel):
    owner: AddressType
    submission_date: datetime = Field(alias="submissionDate")
    transaction_hash: Optional[HexBytes] = Field(None, alias="transactionHash")
    signature: HexBytes
    signature_type: Optional[SignatureType] = Field(None, alias="signatureType")


class OperationType(int, Enum):
    CALL = 0
    DELEGATECALL = 1


class UnexecutedTxData(BaseModel):
    safe: AddressType
    to: AddressType
    value: int
    data: Optional[HexBytes] = None
    operation: OperationType
    gas_token: AddressType = Field(alias="gasToken")
    safe_tx_gas: int = Field(alias="safeTxGas")
    base_gas: int = Field(alias="baseGas")
    gas_price: int = Field(alias="gasPrice")
    refund_receiver: AddressType = Field(alias="refundReceiver")
    nonce: int
    submission_date: datetime = Field(alias="submissionDate")
    modified: datetime
    safe_tx_hash: SafeTxID = Field(alias="safeTxHash")
    confirmations_required: int = Field(alias="confirmationsRequired")
    confirmations: List[SafeTxConfirmation] = []
    trusted: bool = True
    signatures: Optional[HexBytes] = None

    @classmethod
    def from_safe_tx(cls, safe_tx: SafeTx, confirmations_required: int) -> "UnexecutedTxData":
        return cls(
            safe=safe_tx._verifyingContract_,
            submissionDate=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
            confirmationsRequired=confirmations_required,
            safeTxHash=get_safe_tx_hash(safe_tx),
            **safe_tx._body_["message"],
        )

    @property
    def base_tx_dict(self) -> Dict:
        return {
            "to": self.to,
            "value": self.value,
            "data": self.data,
            "operation": self.operation,
            "safeTxGas": self.safe_tx_gas,
            "baseGas": self.base_gas,
            "gasPrice": self.gas_price,
            "gasToken": self.gas_token,
            "refundReceiver": self.refund_receiver,
            "nonce": self.nonce,
        }

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
   data: {add_0x_prefix(cast(HexStr, data_hex))}
"""


class ExecutedTxData(UnexecutedTxData):
    execution_date: datetime = Field(alias="executionDate")
    block_number: int = Field(alias="blockNumber")
    transaction_hash: HexBytes = Field(alias="transactionHash")
    executor: AddressType
    is_executed: bool = Field(alias="isExecuted")
    is_successful: bool = Field(alias="isSuccessful")
    eth_gas_price: int = Field(alias="ethGasPrice")
    max_fee_per_gas: Optional[int] = Field(alias="maxFeePerGas")
    max_priority_fee_per_gas: Optional[int] = Field(alias="maxPriorityFeePerGas")
    gas_used: int = Field(alias="gasUsed")
    fee: int
    origin: str
    data_decoded: Optional[dict] = Field(alias="dataDecoded")


SafeApiTxData = Union[ExecutedTxData, UnexecutedTxData]
