from io import BytesIO

from ape import convert
from ape.api import ReceiptAPI, TransactionAPI
from ape.contracts.base import ContractInstance, ContractTransactionHandler
from ape.types import AddressType, ContractType, HexBytes
from ape.utils import ManagerAccessMixin, cached_property
from eth_abi.packed import encode_packed

from ape_safe.exceptions import UnsupportedChainError, ValueRequired


MULTISEND_CALL_ONLY_ADDRESSES = (
    "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D",  # MultiSend Call Only v1.3.0
    "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B",  # MultiSend Call Only v1.3.0 (EIP-155)
)
MULTISEND_CALL_ONLY_CODE = HexBytes(
    "0x60806040526004361061001e5760003560e01c80638d80ff0a14610023575b600080fd5b6100dc6004803603602081101561003957600080fd5b810190808035906020019064010000000081111561005657600080fd5b82018360208201111561006857600080fd5b8035906020019184600183028401116401000000008311171561008a57600080fd5b91908080601f016020809104026020016040519081016040528093929190818152602001838380828437600081840152601f19601f8201169050808301925050505050505091929192905050506100de565b005b805160205b8181101561015f578083015160f81c6001820184015160601c60158301850151603584018601516055850187016000856000811461012857600181146101385761013d565b6000808585888a5af1915061013d565b600080fd5b50600081141561014c57600080fd5b82605501870196505050505050506100e3565b50505056fea264697066735822122035246402746c96964495cae5b36461fd44dfb89f8e6cf6f6b8d60c0aa89f414864736f6c63430007060033"
)
MULTISEND_CALL_ONLY_CONTRACT_TYPE = ContractType.model_validate_json(
    '{"abi":[{"inputs":[{"internalType":"bytes","name":"transactions","type":"bytes"}],"name":"multiSend","outputs":[],"stateMutability":"payable","type":"function"}],"contractName":"MultiSendCallOnly","methodIdentifiers":{"multiSend(bytes)":"0x8d80ff0a"}}'
)


class MultiSend(ManagerAccessMixin):
    """
    Create a sequence of calls to execute at once using ``eth_sendTransaction``
    via the MultiSend contract.

    Usage example::

        from ape_safe import multisend
        from ape import accounts

        # load the safe
        safe = accounts.load("my-safe")

        txn = multisend.MultiSend()
        txn.add(contract.myMethod, *call_args)
        txn.add(contract.myMethod, *call_args)
        ...  # Add as many calls as desired to execute
        txn.add(contract.myMethod, *call_args)
        # or, using a builder pattern:
        txn = multisend.MultiSend()
            .add(contract.myMethod, *call_args)
            .add(contract.myMethod, *call_args)
            ...  # Add as many calls as desired to execute
            .add(contract.myMethod, *call_args)

        # Stage the transaction to publish on-chain
        # NOTE: if not enough signers are available, publish to Safe API instead
        receipt = txn(sender=safe,gas=0)
    """

    def __init__(self) -> None:
        """
        Initialize a new MultiSend session object. By default, there are no calls to make.
        """
        self.calls: list[dict] = []

    @classmethod
    def inject(cls):
        """
        Create the multisend module contract on-chain, so we can use it.
        Must use a provider that supports ``debug_setCode``.

        Usage example::

            from ape_safe.multisend import MultiSend

            @pytest.fixture(scope="session")
            def multisend():
                MultiSend.inject()
                return MultiSend()
        """
        active_provider = cls.network_manager.active_provider
        assert active_provider, "Must be connected to an active network to deploy"

        active_provider.set_code(
            MULTISEND_CALL_ONLY_ADDRESSES[0], MULTISEND_CALL_ONLY_CODE
        )

    @cached_property
    def contract(self) -> ContractInstance:
        for address in MULTISEND_CALL_ONLY_ADDRESSES:
            if self.provider.get_code(address) == MULTISEND_CALL_ONLY_CODE:
                return self.chain_manager.contracts.instance_at(
                    address, contract_type=MULTISEND_CALL_ONLY_CONTRACT_TYPE
                )

        raise UnsupportedChainError()

    @property
    def handler(self) -> ContractTransactionHandler:
        return self.contract.multiSend

    def add(
        self,
        call,
        *args,
        delegatecall=False,
        value=0,
    ) -> "MultiSend":
        """
        Append a call to the MultiSend session object.

        Raises:
            :class:`InvalidOption`: If one of the kwarg modifiers is not able to be used.

        Args:
            call: :class:`ContractMethodHandler` The method to call.
            *args: The arguments to invoke the method with.
            delegatecall: bool Whether the call should be processed using delegatecall.
            value: int The amount of ether to forward with the call.
        """
        self.calls.append(
            {
                "operation": int(delegatecall),
                "target": call.contract.address,
                "value": value or 0,
                "callData": call.encode_input(*args),
            }
        )
        return self

    def _validate_calls(self, **txn_kwargs) -> None:
        required_value = sum(call["value"] for call in self.calls)
        if required_value > 0:
            if "value" not in txn_kwargs:
                raise ValueRequired(required_value)

            value = self.conversion_manager.convert(txn_kwargs["value"], int)

            if required_value < value:
                raise ValueRequired(required_value)

        # NOTE: Won't fail if `value` is provided otherwise (won't do anything either)

    @property
    def encoded_calls(self):
        return [
            encode_packed(
                ["uint8", "address", "uint256", "uint256", "bytes"],
                [
                    call["operation"],
                    call["target"],
                    call["value"],
                    len(call["callData"]),
                    call["callData"],
                ],
            )
            for call in self.calls
        ]

    def __call__(self, **txn_kwargs) -> ReceiptAPI:
        """
        Execute the MultiSend transaction. The transaction will broadcast again every time
        the ``Transaction`` object is called.

        Raises:
            :class:`UnsupportedChain`: If there is not an instance of MultiSend deployed
              on the current chain at the expected address.

        Args:
            **txn_kwargs: the kwargs to pass through to the transaction handler.

        Returns:
            :class:`~ape.api.transactions.ReceiptAPI`
        """
        self._validate_calls(**txn_kwargs)
        if "operation" not in txn_kwargs and not txn_kwargs.get("impersonate", False):
            txn_kwargs["operation"] = 1
        return self.handler(b"".join(self.encoded_calls), **txn_kwargs)

    def as_transaction(self, **txn_kwargs) -> TransactionAPI:
        """
        Encode the MultiSend transaction as a ``TransactionAPI`` object, but do not execute it.

        Returns:
            :class:`~ape.api.transactions.TransactionAPI`
        """
        self._validate_calls(**txn_kwargs)
        # NOTE: Will fail using `self.handler.as_transaction` because handler
        #       expects to be called only via delegatecall
        if "operation" not in txn_kwargs and not txn_kwargs.get("impersonate", False):
            txn_kwargs["operation"] = 1
        return self.network_manager.ecosystem.create_transaction(
            receiver=self.handler.contract.address,
            data=self.handler.encode_input(b"".join(self.encoded_calls)),
            **txn_kwargs,
        )

    def add_from_calldata(self, calldata: bytes):
        """
        Decode all calls from a multisend calldata and add them to this MultiSend.

        Args:
            calldata: Calldata encoding the MultiSend.multiSend call
        """
        _, args = self.contract.decode_input(calldata)
        buffer = BytesIO(args["transactions"])
        while buffer.tell() < len(args["transactions"]):
            operation = int.from_bytes(buffer.read(1), "big")
            target = convert(buffer.read(20), AddressType)
            value = int.from_bytes(buffer.read(32), "big")
            length = int.from_bytes(buffer.read(32), "big")
            data = HexBytes(buffer.read(length))
            self.calls.append(
                {
                    "operation": operation,
                    "target": target,
                    "value": value,
                    "callData": data,
                }
            )
