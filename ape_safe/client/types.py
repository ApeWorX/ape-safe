from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, NewType, Optional, Union, cast

from ape.types import AddressType, HexBytes
from eip712.common import SafeTxV1, SafeTxV2, create_safe_tx_def
from eth_pydantic_types import HexStr
from eth_utils import add_0x_prefix, to_hex
from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, field_validator

from ape_safe.utils import get_safe_tx_hash

SafeTx = Union[SafeTxV1, SafeTxV2]
SafeTxID = NewType("SafeTxID", str)


def clean_api_address(data: Union[AddressType, dict]) -> AddressType:
    # NOTE: Safe API returns `{'value':'<addr>', ...}` object
    if isinstance(data, dict):
        return data["value"]
    return data


def remove_null_params(data):
    if isinstance(data, dict):
        return {
            k: (remove_null_params(v) if isinstance(v, (dict, list, tuple)) else v)
            for k, v in data.items()
            if v is not None
        }

    elif isinstance(data, list):
        return [
            remove_null_params(v) if isinstance(v, (dict, list, tuple)) else v
            for v in data
            if v is not None
        ]

    elif isinstance(data, tuple):
        return tuple(
            remove_null_params(v) if isinstance(v, (dict, list, tuple)) else v
            for v in data
            if v is not None
        )

    else:
        raise ValueError("Can only supply dict, list, or tuple type")


Address = Annotated[AddressType, BeforeValidator(clean_api_address)]


class SafeDetails(BaseModel):
    address: Address
    nonce: int
    threshold: int
    owners: list[Address]
    master_copy: Address = Field(
        alias="masterCopy",
        validation_alias=AliasChoices("masterCopy", "implementation"),
    )
    modules: list[Address] = []
    fallback_handler: Address = Field(alias="fallbackHandler")
    guard: AddressType
    version: str

    @field_validator("modules", mode="before")
    def convert_none_to_empty_list(cls, value):
        if not value:
            return []
        return value


class SignatureType(str, Enum):
    APPROVED_HASH = "APPROVED_HASH"
    EOA = "EOA"
    ETH_SIGN = "ETH_SIGN"


class SafeTxConfirmation(BaseModel):
    owner: AddressType
    submission_date: datetime = Field(alias="submissionDate")
    transaction_hash: Optional[HexBytes] = Field(default=None, alias="transactionHash")
    signature: HexBytes
    signature_type: Optional[SignatureType] = Field(default=None, alias="signatureType")


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
    base_gas: int = Field(alias="baseGas", default=0)
    gas_price: int = Field(alias="gasPrice")
    refund_receiver: AddressType = Field(alias="refundReceiver")
    nonce: int
    submission_date: datetime = Field(alias="submissionDate")
    modified: datetime
    safe_tx_hash: SafeTxID = Field(alias="safeTxHash")
    confirmations_required: int = Field(alias="confirmationsRequired")
    confirmations: list[SafeTxConfirmation] = []
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

    def as_safe_tx(self, version: str, chain_id: Optional[int] = None) -> SafeTx:
        tx_def = create_safe_tx_def(
            version=version,
            contract_address=self.safe,
            chain_id=chain_id,
        )

        # NOTE: Safe pre-v1.3.0 did not have `baseGas` parameter
        if not hasattr(tx_def, "baseGas"):
            return tx_def(  # type: ignore[call-arg]
                to=self.to,
                value=self.value,
                data=self.data,
                operation=self.operation,
                gasToken=self.gas_token,
                safeTxGas=self.safe_tx_gas,
                gasPrice=self.gas_price,
                refundReceiver=self.refund_receiver,
                nonce=self.nonce,
            )

        return tx_def(  # type: ignore[call-arg]
            to=self.to,
            value=self.value,
            data=self.data,
            operation=self.operation,
            gasToken=self.gas_token,
            safeTxGas=self.safe_tx_gas,
            baseGas=self.base_gas,
            gasPrice=self.gas_price,
            refundReceiver=self.refund_receiver,
            nonce=self.nonce,
        )

    @property
    def base_tx_dict(self) -> dict:
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
        data_hex = to_hex(self.data) if self.data else ""
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
    max_fee_per_gas: Optional[int] = Field(default=None, alias="maxFeePerGas")
    max_priority_fee_per_gas: Optional[int] = Field(default=None, alias="maxPriorityFeePerGas")
    gas_used: int = Field(alias="gasUsed")
    fee: int
    origin: str
    data_decoded: Optional[dict] = Field(default=None, alias="dataDecoded")


SafeApiTxData = Union[ExecutedTxData, UnexecutedTxData]


class DelegateInfo(BaseModel):
    safe: AddressType
    delegate: AddressType
    delegator: AddressType
    label: str = ""
