from io import BytesIO
from typing import TYPE_CHECKING, Optional, Union

from ape import convert
from ape.types import AddressType, HexBytes
from ape.utils import ManagerAccessMixin, cached_property
from eth_abi.packed import encode_packed
from packaging.version import Version

from ape_safe.client.types import OperationType, SafeTxID

from .accounts import SafeAccount, get_signatures
from .exceptions import UnsupportedChainError, ValueRequired
from .packages import MANIFESTS_BY_VERSION, PackageType, get_multisend

if TYPE_CHECKING:
    from ape.api import ReceiptAPI, TransactionAPI
    from ape.contracts.base import ContractInstance, ContractTransactionHandler
    from eip712.common import SafeTx


class MultiSend(ManagerAccessMixin):
    """
    Create a sequence of calls to execute at once using ``eth_sendTransaction``
    via the MultiSend contract.

    Usage example::

        from ape_safe import multisend
        from ape import accounts

        # load the safe
        me = account.load("my-alias")
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
        receipt = txn(submitter=me)
    """

    def __init__(
        self,
        safe: Optional[SafeAccount] = None,
        version: Union[Version, str, None] = None,
    ) -> None:
        """
        Initialize a new MultiSend session object. By default, there are no calls to make.

        Args:
            safe (Optional[:class:`~ape_safe.accounts.SafeAccount`]):
              The Safe account to use for executing this batch.
              If not provided, then is required for other methods below.
            version (Union[:class:`~packaging.version.Version`, str, None]):
              The version of ``MultiSend``/``MultiSendCallOnly`` contract to use from SDK.
              Defaults to auto-detection if ``safe`` arg is present, or uses max available.
        """
        self.safe = safe
        if version is None:
            if safe:
                self.version = safe.version
            else:
                self.version = max(MANIFESTS_BY_VERSION)

        else:
            self.version = Version(version) if not isinstance(version, Version) else version

        self.calls: list[dict] = []

    @classmethod
    def inject(cls, version: Union[Version, str, None] = None):
        """
        Create the multisend module contract on-chain, so we can use it.
        Must use a provider that supports ``debug_setCode``.

        Args:
            version (Union[:class:`~versioning.Version`, str, None]):
              The version of ``MultiSend``/``MultiSendCallOnly`` contract to use from SDK.
              Defaults to max available from SDK.

        Usage example::

            from ape_safe.multisend import MultiSend


            @pytest.fixture(scope="session")
            def multisend():
                MultiSend.inject()
                return MultiSend()
        """
        version = version or max(MANIFESTS_BY_VERSION)
        active_provider = cls.network_manager.active_provider
        assert active_provider, "Must be connected to an active network to deploy"
        MultiSend = PackageType.MULTISEND(version)

        active_provider.set_code(
            "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D",
            MultiSend.contract_type.get_runtime_bytecode(),
        )

    @cached_property
    def contract(self) -> "ContractInstance":
        chain_id = self.network_manager.active_provider.chain_id
        try:
            return get_multisend(chain_id, self.version)

        except KeyError:
            try:
                return PackageType.MULTISEND(self.version).at(
                    "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D"
                )

            except Exception as e:
                raise UnsupportedChainError() from e

    @property
    def handler(self) -> "ContractTransactionHandler":
        return self.contract.multiSend

    def add(
        self,
        call,
        *args,
        value: int = 0,
    ) -> "MultiSend":
        """
        Append a call to the MultiSend session object.

        Raises:
            :class:`InvalidOption`: If one of the kwarg modifiers is not able to be used.

        Args:
            call: :class:`ContractMethodHandler` The method to call.
            *args: The arguments to invoke the method with.
            value: int The amount of ether to forward with the call. Defaults to 0.
        """
        if value < 0:
            raise ValueError("`value=` must be positive.")

        self.calls.append(
            {
                "target": call.contract.address,
                "value": value,
                "callData": call.encode_input(*args),
            }
        )
        return self

    def add_from_receipt(self, receipt: "ReceiptAPI") -> "MultiSend":
        """
        Append a call to the MultiSend session object from a receipt.
        Especially useful for more complex simulations.

        Usage::

            with networks.fork():
                receipt = contract.method(*args, sender=safe.address)
                assert contract.viewMethod() == ...
                batch.add_from_receipt(receipt)

            batch(...)

        Args:
            receipt: :class:`~ape.api.ReceiptAPI` The receipt object to pull information from for the call to add.
        """
        self.calls.append(
            {
                "target": receipt.receiver,
                "value": receipt.value,
                "callData": receipt.data,
            }
        )
        return self

    def _validate_safe_tx(self, safe_tx: "SafeTx") -> None:
        required_value = sum(call["value"] for call in self.calls)
        if required_value > safe_tx.value:
            raise ValueRequired(required_value)

    @property
    def encoded_calls(self):
        return [
            encode_packed(
                ["uint8", "address", "uint256", "uint256", "bytes"],
                [
                    # NOTE: Only allow doing CALL because of `MultiSendCallOnly`
                    int(OperationType.CALL),
                    call["target"],
                    call["value"],
                    len(call["callData"]),
                    call["callData"],
                ],
            )
            for call in self.calls
        ]

    def as_safe_tx(self, safe: Optional[SafeAccount] = None, **safe_tx_kwargs) -> "SafeTx":
        if not (safe or (safe := self.safe)):
            raise ValueError("Must provide `safe=` to call this function")

        elif not isinstance(safe, SafeAccount):
            raise ValueError("`safe=` must be a SafeAccount to use Multisend")

        return safe.create_safe_tx(
            self.handler.as_transaction(b"".join(self.encoded_calls)),
            operation=OperationType.DELEGATECALL,
            **safe_tx_kwargs,
        )

    def propose(
        self,
        safe: Optional[SafeAccount] = None,
        **safe_tx_kwargs,
    ) -> SafeTxID:
        if not (safe or (safe := self.safe)):
            raise ValueError("Must provide `safe=` to call this function")

        elif not isinstance(safe, SafeAccount):
            raise ValueError("`safe=` must be a SafeAccount to use Multisend")

        submitter = safe_tx_kwargs.pop("submitter", None)
        sigs_by_signer = safe_tx_kwargs.pop("sigs_by_signer", None)
        safe_tx = self.as_safe_tx(safe, **safe_tx_kwargs)
        self._validate_safe_tx(safe_tx)
        return safe.propose_safe_tx(
            safe_tx,
            submitter=submitter,
            sigs_by_signer=sigs_by_signer,
        )

    def as_transaction(
        self,
        safe: Optional[SafeAccount] = None,
        impersonate: bool = False,
        **txn_kwargs,
    ) -> "TransactionAPI":
        """
        Encode the MultiSend transaction as a ``TransactionAPI`` object, but do not execute it.

        Args:
            safe (Optional[:class:`~ape_safe.accounts.SafeAccount`]):
              The Safe account to use for executing this batch.
              If not provided, then it uses value provided to
              :func:`~ape_safe.multisend.MultiSend.__init__`.
            impersonate (bool): Whether to mock approvals for executing this transaction.
            **txn_kwargs: the kwargs to pass through to the transaction handler.

        Returns:
            :class:`~ape.api.transactions.TransactionAPI`
        """
        if not (safe or (safe := self.safe)):
            raise ValueError("Must provide `safe=` to call this function")

        elif not isinstance(safe, SafeAccount):
            raise ValueError("`safe=` must be a SafeAccount to use Multisend")

        safe_tx_kwargs = {}
        for field in safe.safe_tx_def.__annotations__:
            if field in txn_kwargs:
                safe_tx_kwargs[field] = txn_kwargs.pop(field)

        safe_tx = self.as_safe_tx(safe, **safe_tx_kwargs)
        signatures = {} if impersonate else get_signatures(safe_tx, safe.local_signers)
        return safe.create_execute_transaction(
            safe_tx,
            signatures=signatures,
            impersonate=impersonate,
            **txn_kwargs,
        )

    def __call__(
        self,
        safe: Optional[SafeAccount] = None,
        **txn_kwargs,
    ) -> "ReceiptAPI":
        """
        Execute the MultiSend transaction. The transaction will broadcast again every time
        the ``Transaction`` object is called.

        Raises:
            :class:`UnsupportedChain`: If there is not an instance of MultiSend deployed
              on the current chain at the expected address.

        Args:
            safe (Optional[:class:`~ape_safe.accounts.SafeAccount`]):
              The Safe account to use for executing this batch.
              If not provided, then it uses value provided to
              :func:`~ape_safe.multisend.MultiSend.__init__`.
            **txn_kwargs: the kwargs to pass through to the transaction handler.

        Returns:
            :class:`~ape.api.transactions.ReceiptAPI`
        """
        return self.provider.send_transaction(self.as_transaction(safe=safe, **txn_kwargs))

    def add_from_calldata(self, calldata: bytes) -> "MultiSend":
        """
        Decode all calls from a multisend calldata and add them to this MultiSend.

        Args:
            calldata: Calldata encoding the ``MultiSend.multiSend`` call.
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

        return self
