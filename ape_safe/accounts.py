import json
import os
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Union, cast

from ape.api import AccountAPI, AccountContainerAPI, ReceiptAPI, TransactionAPI
from ape.api.networks import ForkedNetworkAPI
from ape.cli import select_account
from ape.contracts import ContractCall
from ape.exceptions import ContractNotFoundError, ProviderNotConnectedError
from ape.logging import logger
from ape.managers.accounts import AccountManager, TestAccountManager
from ape.types import AddressType, HexBytes, MessageSignature
from ape.utils import ZERO_ADDRESS, cached_property
from ape_ethereum.proxies import ProxyInfo, ProxyType
from ape_ethereum.transactions import TransactionType
from eip712.common import SafeTxV1, SafeTxV2, create_safe_tx_def
from eth_utils import keccak, to_bytes, to_int
from ethpm_types import ContractType
from ethpm_types.abi import ABIType, MethodABI
from packaging.version import Version

from .client import BaseSafeClient, MockSafeClient, SafeClient, SafeTx, SafeTxConfirmation, SafeTxID
from .config import SafeConfig
from .exceptions import (
    ApeSafeError,
    NoLocalSigners,
    NotASigner,
    NotEnoughSignatures,
    SafeClientException,
    handle_safe_logic_error,
)
from .factory import SafeFactory
from .packages import PackageType
from .types import SafeCacheData
from .utils import get_safe_tx_hash, order_by_signer

if TYPE_CHECKING:
    from ape.api.address import BaseAddress
    from ape.contracts import ContractInstance


class SafeContainer(AccountContainerAPI):
    _accounts: dict[str, "SafeAccount"] = {}

    @property
    def config(self) -> SafeConfig:
        return cast(SafeConfig, self.config_manager["safe"])

    @property
    def _account_files(self) -> Iterator[Path]:
        account_files = list(self.data_folder.glob("*.json"))

        # NOTE: Make sure these Safes exist in our local cache
        for required_safe, safe_cache_data in self.config.require.items():
            # NOTE: If alias `required_safe` already exists, skip overwriting it
            if required_safe not in map(lambda p: p.stem, account_files):
                safe_cache_file = self.data_folder / f"{required_safe}.json"
                safe_cache_file.write_text(safe_cache_data.model_dump_json(), encoding="utf-8")
                account_files.append(safe_cache_file)

        yield from account_files

    @property
    def aliases(self) -> Iterator[str]:
        for p in self._account_files:
            yield p.stem

    @property
    def addresses(self) -> Iterator[str]:
        for safe in self.accounts:
            yield safe.address

    @property
    def accounts(self) -> Iterator[AccountAPI]:
        for account_file in self._account_files:
            if account_file.stem in self._accounts:
                yield self._accounts[account_file.stem]

            else:
                # Cache the accounts so their local state is maintained
                # throughout the current Python session.
                acct = SafeAccount(account_file_path=account_file)
                self._accounts[account_file.stem] = acct
                yield acct

    def __len__(self) -> int:
        return len([*self._account_files])

    def __setitem__(self, alias: str, address: str):  # type: ignore[override]
        self.save_account(alias, address)

    def __delitem__(self, alias: str):
        self.delete_account(alias)

    def __iter__(self) -> Iterator["SafeAccount"]:  # type: ignore[override]
        # NOTE: We know our accounts are SafeAccounts, hence the type ignore.s
        safe_accounts = cast(Iterator["SafeAccount"], self.accounts)
        yield from safe_accounts

    def __contains__(self, item: Union[str, "SafeAccount"]) -> bool:
        if item is None:
            return False

        if isinstance(item, str):
            return item in self.aliases or item in self.addresses

        # Is account object
        for account in self.accounts:
            if account.address == item.address:
                return True

        return False

    def save_account(self, alias: str, address: str):
        """
        Save a new Safe to your ape configuration.

        Raises:
            :class:`~ape_safe.exceptions.ApeSafeError`: When the alias
              already exists.

        Args:
            alias (str): The alias to save the Safe under.
            address (str): The address of the Safe account.
        """
        chain_id = self.provider.chain_id
        account_data = {"address": address, "deployed_chain_ids": [chain_id]}
        path = self._get_path(alias)
        if path.is_file():
            raise ApeSafeError(f"Safe with alias '{alias}' already exists.")

        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(json.dumps(account_data))

    def load_account(self, alias: str) -> "SafeAccount":
        """
        Load the Safe account.

        Raises:
            :class:`~ape_safe.exceptions.ApeSafeError`: When the alias does
              not exist.

        Args:
            alias (str): The alias the Safe account is saved under.

        Returns:
            :class:`~ape_safe.accounts.SafeAccount`: The Safe account loaded.
        """
        if alias in self._accounts:
            return self._accounts[alias]

        account_path = self._get_path(alias)
        if not account_path.is_file():
            raise ApeSafeError(f"Safe with '{alias}' does not exist")

        acct = SafeAccount(account_file_path=account_path)
        self._accounts[alias] = acct
        return acct

    def delete_account(self, alias: str):
        """
        Delete the local Safe account.
        **NOTE**: If the account does not exist, nothing happens.

        Args:
            alias (str): The alias the Safe account is saved under.
        """
        self._get_path(alias).unlink(missing_ok=True)

    def _get_path(self, alias: str) -> Path:
        return self.data_folder.joinpath(f"{alias}.json")


def get_signatures(
    safe_tx: SafeTx,
    signers: Iterable[AccountAPI],
) -> dict[AddressType, MessageSignature]:
    signatures: dict[AddressType, MessageSignature] = {}
    for signer in signers:
        signature = signer.sign_message(safe_tx)
        if signature:
            signatures[signer.address] = signature

    return signatures


def _safe_tx_exec_args(safe_tx: SafeTx) -> list:
    return list(safe_tx._body_["message"].values())


class SafeAccount(AccountAPI):
    account_file_path: Path  # NOTE: Cache any relevant data here
    _factory: ClassVar[SafeFactory] = SafeFactory()

    @property
    def alias(self) -> str:
        return self.account_file_path.stem

    @property
    def account_data(self) -> SafeCacheData:
        return SafeCacheData.model_validate_json(self.account_file_path.read_text(encoding="utf-8"))

    @property
    def deployed_chain_ids(self) -> list[int]:
        return self.account_data.deployed_chain_ids

    @cached_property
    def address(self) -> AddressType:
        try:
            ecosystem = self.provider.network.ecosystem
        except ProviderNotConnectedError:
            ecosystem = self.network_manager.ethereum

        return ecosystem.decode_address(self.account_data.address)

    @cached_property
    def contract(self) -> "ContractInstance":
        version = self.version
        safe_contract = PackageType.PROXY(version).at(
            self.address,
            proxy_info=ProxyInfo(
                target=self._factory.get_singleton(version=version),
                type=ProxyType.GnosisSafe,
            ),
        )
        if self.fallback_handler:
            contract_signatures = {x.signature for x in safe_contract.contract_type.abi}
            fallback_signatures = {x.signature for x in self.fallback_handler.contract_type.abi}
            if fallback_signatures < contract_signatures:
                return safe_contract  # for some reason this never gets hit

            contract_type = safe_contract.contract_type.model_dump(by_alias=True, mode="json")
            fallback_type = self.fallback_handler.contract_type.model_dump(
                by_alias=True, mode="json"
            )
            contract_type["abi"].extend(fallback_type["abi"])
            return self.chain_manager.contracts.instance_at(
                self.address, contract_type=ContractType.model_validate(contract_type)
            )

        else:
            return safe_contract

    @cached_property
    def fallback_handler(self) -> Optional["ContractInstance"]:
        slot = keccak(text="fallback_manager.handler.address")
        value = self.provider.get_storage(self.address, slot)
        address = self.network_manager.ecosystem.decode_address(value[-20:])
        return (
            self.chain_manager.contracts.instance_at(address) if address != ZERO_ADDRESS else None
        )

    @property
    def guard(self) -> Optional["ContractInstance"]:
        slot = keccak(text="guard_manager.guard.address")
        value = self.provider.get_storage(self.address, slot)
        address = self.network_manager.ecosystem.decode_address(value[-20:])
        return (
            self.chain_manager.contracts.instance_at(address) if address != ZERO_ADDRESS else None
        )

    def set_guard(
        self,
        new_guard: Union[str, AddressType, "BaseAddress"] = ZERO_ADDRESS,
        **tx_args,
    ) -> ReceiptAPI:
        if "sender" not in tx_args:
            tx_args["sender"] = self

        return self.contract.setGuard(new_guard, **tx_args)

    def get_client(
        self, chain_id: Optional[int] = None, override_url: Optional[str] = None
    ) -> BaseSafeClient:
        if chain_id is None:
            chain_id = self.provider.chain_id

        if override_url is None:
            env_override = os.environ.get("SAFE_TRANSACTION_SERVICE_URL")
            if env_override:
                override_url = env_override

        if chain_id == 0 or (self.provider.network.is_local and self.provider.chain_id == chain_id):
            return MockSafeClient(contract=self.contract)

        return SafeClient(address=self.address, chain_id=chain_id, override_url=override_url)

    @cached_property
    def client(self) -> BaseSafeClient:
        if (
            self.provider.network.name.endswith("-fork")
            and isinstance(self.provider.network, ForkedNetworkAPI)
            and self.provider.network.upstream_chain_id in self.deployed_chain_ids
        ):
            return self.get_client(chain_id=self.provider.network.upstream_chain_id)

        return self.get_client()

    @property
    def version(self) -> Version:
        # NOTE: We want to make a direct call, so we can use this for loading
        #       the proper verison of the Safe protocol w/ `.contract`
        VERSION_ABI = MethodABI(
            name="VERSION",
            type="function",
            stateMutability="view",
            outputs=[ABIType(type="string")],
        )

        if isinstance(version := ContractCall(VERSION_ABI, address=self.address)(), str):
            return Version(version)

        # NOTE: If `eth_call` returns nothing, it will be rendered as randomly
        raise ContractNotFoundError(
            self.address,
            bool(self.provider.network.explorer),
            self.provider.network_choice,
        )

    @property
    def signers(self) -> list[AddressType]:
        # NOTE: Signers are in order because of `Set`
        try:
            return self.client.safe_details.owners
        except Exception:
            return self.contract.getOwners()

    @property
    def confirmations_required(self) -> int:
        try:
            return self.client.safe_details.threshold
        except Exception:
            return self.contract.getThreshold()

    @property
    def next_nonce(self) -> int:
        """
        The next nonce for on-chain. If you have multiple transactions
        are in the queue but not published on chain, the next nonce
        refers to the earliest nonce in that queue.
        """
        try:
            return self.client.get_next_nonce()
        except Exception:
            # NOTE: `.nonce` conflicts with `AccountAPI.nonce`, so use `._view_methods_`
            return self.contract._view_methods_["nonce"]()

    @property
    def new_nonce(self):
        """
        The next unused nonce in the system. This is different
        than ``.next_nonce`` because it includes all nonces the
        transaction service is aware of and not just the next
        on-chain nonce.
        """

        # NOTE: Transaction and returned greatest nonce first.
        if latest_tx := next(self.client.get_transactions(confirmed=False), None):
            return latest_tx.nonce + 1

        # No pending transactions. Use next on-chain nonce.
        return self.next_nonce

    def sign_message(self, msg: Any, **signer_options) -> Optional[MessageSignature]:
        # TODO: Support signing via https://eips.ethereum.org/EIPS/eip-1271 in Ape
        raise NotImplementedError("Safe accounts do not support message signing!")

    @property
    def safe_tx_def(self) -> type[SafeTx]:
        return create_safe_tx_def(
            version=str(self.version),
            contract_address=self.address,
            chain_id=self.provider.chain_id,
        )

    def create_safe_tx(self, txn: Optional[TransactionAPI] = None, **safe_tx_kwargs) -> SafeTx:
        """
        Create the Safe transaction.

        Args:
            txn (Optional[``TransactionAPI``]): The transaction
            **safe_tx_kwargs: The safe transactions specifications, such as ``submitter``.

        Returns:
            :class:`~ape_safe.client.SafeTx`: The Safe Transaction to be used.
        """
        safe_tx = {
            "to": txn.receiver if txn else self.address,  # Self-call, e.g. rejection
            "value": txn.value if txn else 0,
            "data": (txn.data or b"") if txn else b"",
            "nonce": self.new_nonce if txn is None or txn.nonce is None else txn.nonce,
            "operation": 0,
            "safeTxGas": 0,
            "gasPrice": 0,
            "gasToken": ZERO_ADDRESS,
            "refundReceiver": ZERO_ADDRESS,
        }
        safe_tx = {
            **safe_tx,
            **{k: v for k, v in safe_tx_kwargs.items() if k in safe_tx and v is not None},
        }
        return self.safe_tx_def(**safe_tx)

    def all_delegates(self) -> Iterator[AddressType]:
        for delegates in self.client.get_delegates().values():
            yield from delegates

    def propose_safe_tx(
        self,
        safe_tx: SafeTx,
        submitter: Union[AccountAPI, AddressType, str, None] = None,
        sigs_by_signer: Optional[dict[AddressType, MessageSignature]] = None,
        contractTransactionHash: Optional[SafeTxID] = None,
    ) -> SafeTxID:
        """
        Propose a safe_tx to the Safe API client
        """
        if not contractTransactionHash:
            contractTransactionHash = get_safe_tx_hash(safe_tx)

        if not sigs_by_signer:
            sigs_by_signer = {}

        if submitter is not None and not isinstance(submitter, AccountAPI):
            submitter = self.load_submitter(submitter)
            assert isinstance(submitter, AccountAPI)  # NOTE: mypy happy

        if (
            submitter is not None
            and submitter.address not in sigs_by_signer
            and len(sigs_by_signer) < self.confirmations_required
            and (submitter.address in self.signers or submitter.address in self.all_delegates())
        ):
            if sig := submitter.sign_message(safe_tx):
                sigs_by_signer[submitter.address] = sig

        # NOTE: Signatures don't have to be in order for Safe API post
        self.client.post_transaction(
            safe_tx,
            sigs_by_signer,
            sender=submitter.address if submitter else None,
            contractTransactionHash=contractTransactionHash,
        )

        return contractTransactionHash

    def propose(
        self,
        txn: Optional[TransactionAPI] = None,
        submitter: Union[AccountAPI, AddressType, str, None] = None,
        **safe_tx_kwargs,
    ) -> SafeTxID:
        """
        Propose a transaction to the Safe API client
        """
        safe_tx = self.create_safe_tx(txn=txn, **safe_tx_kwargs)
        return self.propose_safe_tx(safe_tx, submitter=submitter)

    def pending_transactions(self) -> Iterator[tuple[SafeTx, list[SafeTxConfirmation]]]:
        for executed_tx in self.client.get_transactions(confirmed=False):
            yield self.create_safe_tx(
                **executed_tx.model_dump(mode="json", by_alias=True)
            ), executed_tx.confirmations

    @property
    def local_signers(self) -> list[AccountAPI]:
        # NOTE: Is not ordered by signing order
        # TODO: Skip per user config
        # TODO: Order per user config
        container: Union[AccountManager, TestAccountManager]
        if self.network_manager.active_provider and self.provider.network.is_dev:
            container = self.account_manager.test_accounts
        else:
            container = self.account_manager

        # Ensure the contract is available before continuing.
        # Else, return an empty list
        try:
            _ = self.contract
        except ContractNotFoundError:
            return []

        return list(container[address] for address in self.signers if address in container)

    @handle_safe_logic_error()
    def create_execute_transaction(
        self,
        safe_tx: SafeTx,
        signatures: Mapping[AddressType, MessageSignature],
        **txn_options,
    ) -> TransactionAPI:
        exec_args = list(safe_tx._body_["message"].values())[:-1]  # NOTE: Skip `nonce`
        encoded_signatures = HexBytes(
            b"".join(
                sig.encode_rsv() if isinstance(sig, MessageSignature) else sig
                for sig in order_by_signer(signatures)
            )
        )

        # NOTE: executes a `ProviderAPI.prepare_transaction`, which may produce `ContractLogicError`
        return self.contract.execTransaction.as_transaction(
            *exec_args, encoded_signatures, **txn_options
        )

    def compute_prev_signer(self, signer: Union[str, AddressType, "BaseAddress"]) -> AddressType:
        """
        Sometimes it's handy to have "previous owner" for ownership change operations,
        this function makes it easy to calculate.
        """
        signer_address: AddressType = self.conversion_manager.convert(signer, AddressType)
        signers = self.contract.getOwners()  # NOTE: Use contract version to ensure correctness
        if signer_address not in signers:
            raise NotASigner(signer_address)

        index = signers.index(signer_address)
        if index > 0:
            return signers[index - 1]

        # NOTE: SENTINEL_OWNERS is the "previous" address to index 0
        return cast(AddressType, "0x0000000000000000000000000000000000000001")

    def load_submitter(
        self,
        submitter: Union[AddressType, str, None] = None,
    ) -> AccountAPI:
        if submitter is None:
            if len(self.local_signers) == 0:
                raise NoLocalSigners()

            return self.local_signers[0]

        elif (
            submitter_address := self.conversion_manager.convert(submitter, AddressType)
            in self.account_manager
        ):
            return self.account_manager[submitter_address]

        elif isinstance(submitter, str) and submitter in self.account_manager.aliases:
            return self.account_manager.load(submitter)

        else:
            raise ValueError(f"Cannot handle {submitter}={type(submitter)}")

    def prepare_transaction(self, txn: TransactionAPI) -> TransactionAPI:
        # NOTE: Need to override `AccountAPI` behavior for balance checks
        if txn.gas_limit is None:
            txn.gas_limit = self.estimate_gas_cost(txn=txn)

        return self.provider.prepare_transaction(txn)

    def estimate_gas_cost(self, **kwargs) -> int:
        operation = kwargs.pop("operation", 0)
        txn = kwargs.pop("txn", self.as_transaction(**kwargs))
        return (
            self.client.estimate_gas_cost(
                txn.receiver or ZERO_ADDRESS, txn.value, txn.data, operation=operation
            )
            or 0
        )

    def _preapproved_signature(
        self, signer: Union[AddressType, "BaseAddress", str]
    ) -> MessageSignature:
        # Get the Safe-style "preapproval" signature type, which is a sentinel value used to denote
        # when a signer approved via some other method, such as `approveHash` or being `msg.sender`
        # TODO: Link documentation for this
        return MessageSignature(
            v=1,  # Approved hash (e.g. submitter is approved)
            r=b"\x00" * 12 + to_bytes(hexstr=self.conversion_manager.convert(signer, AddressType)),
            s=b"\x00" * 32,
        )

    @handle_safe_logic_error()
    def _impersonated_call(self, txn: TransactionAPI, **safe_tx_and_call_kwargs) -> ReceiptAPI:
        safe_tx = self.create_safe_tx(txn, **safe_tx_and_call_kwargs)
        safe_tx_exec_args = _safe_tx_exec_args(safe_tx)
        signatures = {}

        # Bypass signature collection logic and attempt to submit by impersonation
        # NOTE: Only works for fork and local network providers that support `set_storage`
        safe_tx_hash = self.contract.getTransactionHash(*safe_tx_exec_args)
        signer_address = None
        for signer_address in self.signers[: self.confirmations_required]:
            # NOTE: `approvedHashes` is `address => safe_tx_hash => num_confs` @ slot 8
            # TODO: Use native ape slot indexing, once available
            address_bytes32 = to_bytes(hexstr=signer_address)
            address_bytes32 = b"\x00" * (32 - len(address_bytes32)) + address_bytes32
            key_hash = keccak(address_bytes32 + b"\x00" * 31 + to_bytes(8))
            slot = to_int(keccak(safe_tx_hash + key_hash))
            self.provider.set_storage(self.address, slot, to_bytes(1))

            signatures[signer_address] = self._preapproved_signature(signer_address)

        # NOTE: Could raise a `SafeContractError`
        safe_tx_and_call_kwargs["sender"] = safe_tx_and_call_kwargs.get(
            "submitter",
            # NOTE: Use whatever the last signer was if no `submitter`
            self.account_manager.test_accounts[signer_address],
        )
        return self.contract.execTransaction(
            *safe_tx_exec_args[:-1],  # NOTE: Skip nonce
            HexBytes(
                b"".join(
                    sig.encode_rsv() if isinstance(sig, MessageSignature) else sig
                    for sig in order_by_signer(signatures)
                )
            ),
            **safe_tx_and_call_kwargs,
        )

    @handle_safe_logic_error()
    def call(  # type: ignore[override]
        self,
        txn: TransactionAPI,
        impersonate: bool = False,
        **call_kwargs,
    ) -> ReceiptAPI:
        # NOTE: This handles if given `submit=None'.
        default_submit = not impersonate
        submit = (
            call_kwargs.pop("submit_transaction", call_kwargs.pop("submit", default_submit))
            or not default_submit
        )
        call_kwargs["submit"] = submit
        if impersonate:
            return self._impersonated_call(txn, **call_kwargs)

        return super().call(txn, **call_kwargs)

    def get_api_confirmations(
        self,
        safe_tx: Union[SafeTx, SafeTxID],
    ) -> dict[AddressType, MessageSignature]:
        if isinstance(safe_tx, (SafeTxV1, SafeTxV2)):
            safe_tx_id = get_safe_tx_hash(safe_tx)

        else:
            safe_tx_id = safe_tx

        try:
            client_confirmations = self.client.get_confirmations(safe_tx_id)
        except SafeClientException as err:
            logger.error(str(err))
            return {}

        return {
            conf.owner: MessageSignature(
                r=conf.signature[:32], s=conf.signature[32:64], v=conf.signature[64]
            )
            for conf in client_confirmations
        }

    def _contract_approvals(self, safe_tx: SafeTx) -> Mapping[AddressType, MessageSignature]:
        safe_tx_exec_args = _safe_tx_exec_args(safe_tx)
        safe_tx_hash = self.contract.getTransactionHash(*safe_tx_exec_args)

        return {
            signer: self._preapproved_signature(signer)
            for signer in self.signers
            if self.contract.approvedHashes(signer, safe_tx_hash) > 0
        }

    def _all_approvals(self, safe_tx: SafeTx) -> dict[AddressType, MessageSignature]:
        approvals = self.get_api_confirmations(safe_tx)

        # NOTE: Do this last because it should take precedence
        approvals.update(self._contract_approvals(safe_tx))
        return approvals

    def submit_safe_tx(
        self,
        safe_tx: Union[SafeTx, SafeTxID],
        submitter: Union[AccountAPI, AddressType, str, None] = None,
        **txn_options,
    ) -> ReceiptAPI:
        """
        Submit the safe transaction using the submitter after all signatures have been collected.

        Args:
            safe_tx (``SafeTX``): The safe transaction to submit.
            submitter (Union[``AccountAPI``, ``AddressType``, str, ``None``]):
                The submitter to use for the transaction. Defaults to ``None``.

        Returns:
            ``ReceiptAPI``
        """
        if not isinstance(safe_tx, (SafeTxV1, SafeTxV2)):
            safe_tx_id = safe_tx
            safe_tx = self.client.get_safe_tx(safe_tx_id).as_safe_tx(
                version=str(self.version), chain_id=self.chain_manager.chain_id
            )

        else:
            safe_tx_id = get_safe_tx_hash(safe_tx)

        assert isinstance(safe_tx, (SafeTxV1, SafeTxV2))
        signatures = self._all_approvals(safe_tx)
        txn = self.create_execute_transaction(safe_tx, signatures, **txn_options)

        if not isinstance(submitter, AccountAPI):
            submitter = self.load_submitter(submitter)
            assert isinstance(submitter, AccountAPI)  # NOTE: mypy happy

        return submitter.call(txn)

    def sign_transaction(
        self,
        txn: TransactionAPI,
        submit: bool = True,
        submitter: Union[AccountAPI, AddressType, str, None] = None,
        skip: Optional[list[Union[AccountAPI, AddressType, str]]] = None,
        signatures_required: Optional[int] = None,  # NOTE: Required if increasing threshold
        **signer_options,
    ) -> Optional[TransactionAPI]:
        """
        Sign the created safe transaction for the safe client to post.
        **NOTE** ``signatures_required`` is required if the transaction is increasting the
        threshold.

        Args:
            txn (``TransactionAPI``): The contract transaction.
            submit (bool): The option to submit the transaction. Defaults to ``True``.
            submitter (Union[``AccountAPI``, ``AddressType``, str, None]):
                Determine who is submitting the transaction. Defaults to ``None``.
            skip (Optional[list[Union[``AccountAPI, `AddressType``, str]]]):
                Allow bypassing any specified signer. Defaults to ``None``.
            signatures_required (Optional[int]):
                The amount of signers required to confirm the transaction. Defaults to ``None``.
            **signer_options: Other signer options.

        Returns:
            Optional[``TransactionAPI``]: Returns ``None`` if the transaction is successful.
        """

        if not submit and submitter:
            raise ValueError("Cannot specify a submitter if not submitting.")

        safe_tx = self.create_safe_tx(txn, **signer_options)

        # Determine who is submitting the transaction (if enough signatures are gathered)
        # NOTE: This is needed even if not submitting right now.
        submitter_account: AccountAPI = (
            self.load_submitter(submitter)
            if submitter is None or not isinstance(submitter, AccountAPI)
            else submitter
        )

        # Garner either M or M - 1 signatures, depending on if we are submitting
        # and whether the submitter is also a signer (both must be true to submit M - 1).
        # NOTE: Will skip or reorder signers based on config
        available_signers = iter(self.local_signers)

        # If number of signatures required not specified, figure out how many are needed
        if not signatures_required:
            if submit and submitter_account.address in self.signers:
                # Sender doesn't have to sign
                signatures_required = self.confirmations_required - 1
                # NOTE: Adjust signers to sign with by skipping submitter
                available_signers = filter(lambda s: s != submitter_account, available_signers)

            else:
                # Not submitting, or submitter isn't a signer, so we need all confirmations
                signatures_required = self.confirmations_required

        # Allow bypassing any specified signers (above and beyond user config)
        if skip:
            skip_addresses = [self.conversion_manager.convert(a, AddressType) for a in skip]

            def skip_signer(signer: AccountAPI):
                return signer.address not in skip_addresses

            available_signers = filter(skip_signer, available_signers)

        # Check if transaction has existing tracked signatures
        sigs_by_signer = self._all_approvals(safe_tx)
        safe_tx_hash = get_safe_tx_hash(safe_tx)

        # Attempt to fetch just enough signatures to satisfy the amount we need
        # NOTE: It is okay to have less signatures, but it never should fetch more than needed
        signers = [x for x in available_signers if x.address not in sigs_by_signer]
        if signers:
            new_signatures = get_signatures(safe_tx, signers)
            sigs_by_signer = {**sigs_by_signer, **new_signatures}

        if (
            submit
            # We have enough signatures to commit the transaction,
            # and a non-signer will submit it as their own transaction
            and len(sigs_by_signer) >= signatures_required
        ):
            # We need to encode the submitter's address for Safe to decode
            if submitter_account.address in self.signers:
                sigs_by_signer[submitter_account.address] = self._preapproved_signature(
                    submitter_account
                )

            # Inherit gas args from safe_tx, if set
            gas_args = {"gas_limit": txn.gas_limit}

            if txn.type == TransactionType.STATIC:
                gas_args["gas_price"] = txn.gas_price

            else:
                gas_args["max_fee"] = txn.max_fee
                gas_args["max_priority_fee"] = txn.max_priority_fee

            exec_transaction = self.create_execute_transaction(
                safe_tx,
                sigs_by_signer,
                **gas_args,
                nonce=submitter_account.nonce,
            )
            txn = submitter_account.sign_transaction(exec_transaction, **signer_options)
            # NOTE: Because of `ape_ethereum.transactions.BaseTransaction.serialize_transaction`
            #       doing a recovered signer check, and we gotta make sure the address matches
            #       the recovered address of the signed transaction.
            txn.sender = submitter_account.address
            return txn

        elif submit:
            # NOTE: User wanted to submit transaction, but we can't, so don't publish to API
            raise NotEnoughSignatures(signatures_required, len(sigs_by_signer))

        # NOTE: Not enough signatures were obtained to publish on-chain
        logger.info(
            f"Collected {len(sigs_by_signer)}/{self.confirmations_required} signatures "
            f"for Safe {self.address}#{safe_tx.nonce}"  # TODO: put URI
        )

        self.propose_safe_tx(
            safe_tx,
            submitter=submitter_account,
            sigs_by_signer=sigs_by_signer,
            contractTransactionHash=safe_tx_hash,
        )

        # Return None so that Ape does not try to submit the transaction.
        return None

    def add_signatures(
        self,
        safe_tx: Union[SafeTx, SafeTxID],
        confirmations: Optional[list[SafeTxConfirmation]] = None,
    ) -> dict[AddressType, MessageSignature]:
        if not isinstance(safe_tx, (SafeTxV1, SafeTxV2)):
            safe_tx_id = safe_tx
            safe_tx = self.client.get_safe_tx(safe_tx_id).as_safe_tx(
                version=str(self.version), chain_id=self.chain_manager.chain_id
            )

        else:
            safe_tx_id = get_safe_tx_hash(safe_tx)

        assert isinstance(safe_tx, (SafeTxV1, SafeTxV2))
        confirmations = confirmations or list(self.client.get_confirmations(safe_tx_id))
        if (confirmations_needed := self.confirmations_required - len(confirmations)) <= 0:
            raise ApeSafeError("Transaction has enough confirmations.")

        elif not (
            available_signers := [
                acc
                for acc in self.local_signers
                if acc.address not in set(c.owner for c in confirmations)
            ]
        ):
            raise ApeSafeError("No local signers available to sign.")

        new_signatures = {}
        for acc in available_signers:
            if signature := acc.sign_message(safe_tx):
                new_signatures[acc.address] = signature
                confirmations_needed -= 1
                if confirmations_needed <= 0:
                    break

            # else: didn't want to sign

        if new_signatures:
            self.client.post_signatures(safe_tx_id, new_signatures)

        # NOTE: Return all signatures, both new and existing
        return {**{c.owner: c.signature for c in confirmations}, **new_signatures}

    def select_signer(self, for_: str = "submitter") -> AccountAPI:
        return select_account(prompt_message=f"Select a {for_}", key=self.local_signers)
