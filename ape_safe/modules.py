from typing import TYPE_CHECKING, Optional, Union

from ape.types import AddressType
from ape.utils import ZERO_ADDRESS, ManagerAccessMixin
from cchecksum import to_checksum_address

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ape.api import AccountAPI, ReceiptAPI
    from ape.contracts import ContractInstance

    from ape_safe.accounts import SafeAccount
    from ape_safe.client import SafeTxID


class SafeModuleManager(ManagerAccessMixin):
    SENTINEL: AddressType = "0x0000000000000000000000000000000000000001"
    PAGE_SIZE: int = 100

    def __init__(self, safe: "SafeAccount"):
        self._safe = safe

    def __repr__(self) -> str:
        return f"<{self.__class__.__qualname__} safe={self._safe.address}"

    def __contains__(self, module: Union[str, AddressType, "ContractInstance"]) -> bool:
        return self._safe.contract.isModuleEnabled(module)

    def enable(
        self,
        module: Union[str, AddressType, "ContractInstance"],
        submitter: Union["AccountAPI", AddressType, str, None] = None,
        propose: bool = False,
        **txn_kwargs,
    ) -> Union["ReceiptAPI", "SafeTxID"]:
        if propose:
            txn = self._safe.contract.enableModule.as_transaction(module, **txn_kwargs)
            return self._safe.propose(txn=txn, submitter=submitter)

        else:
            return self._safe.contract.enableModule(
                module,
                sender=self._safe,
                submitter=submitter,
                **txn_kwargs,
            )

    def __iter__(self) -> "Iterator[ContractInstance]":
        start_module = self.SENTINEL
        while True:
            page, start_module = self._safe.contract.getModulesPaginated(
                start_module, self.PAGE_SIZE
            )
            yield from map(self.chain_manager.contracts.instance_at, page)

            if start_module == self.SENTINEL:
                break

    def _get_previous_module(
        self, module: Union[str, AddressType, "ContractInstance"]
    ) -> "AddressType":
        prev_module = self.SENTINEL

        for next_module in self:
            if next_module == module:
                return prev_module

            prev_module = next_module

        raise AssertionError(f"Module {module} not in Safe modules for {self._safe}")

    def disable(
        self,
        module: Union[str, AddressType, "ContractInstance"],
        submitter: Union["AccountAPI", AddressType, str, None] = None,
        propose: bool = False,
        **txn_kwargs,
    ) -> Union["ReceiptAPI", "SafeTxID"]:
        if propose:
            txn = self._safe.contract.disableModule.as_transaction(
                self._get_previous_module(module),
                module,
                **txn_kwargs,
            )
            return self._safe.propose(txn=txn, submitter=submitter)

        else:
            return self._safe.contract.disableModule(
                self._get_previous_module(module),
                module,
                sender=self._safe,
                **txn_kwargs,
            )

    @property
    def guard(self) -> Optional["ContractInstance"]:
        if (
            module_guard_address := to_checksum_address(
                self.provider.get_storage(
                    self._safe.contract.address,
                    # NOTE: `keccak256("module_manager.module_guard.address")`
                    "0xb104e0b93118902c651344349b610029d694cfdec91c589c91ebafbcd0289947",
                )[12:]
            )
        ) == ZERO_ADDRESS:
            return None

        return self.chain_manager.contracts.instance_at(module_guard_address)

    def set_guard(
        self,
        guard: Union[str, AddressType, "ContractInstance"],
        submitter: Union["AccountAPI", AddressType, str, None] = None,
        propose: bool = False,
        **txn_kwargs,
    ) -> Union["ReceiptAPI", "SafeTxID"]:
        if propose:
            txn = self._safe.contract.setModuleGuard.as_transaction(guard, **txn_kwargs)
            return self._safe.propose(txn=txn, submitter=submitter)

        else:
            return self._safe.contract.setModuleGuard(guard, sender=self._safe, **txn_kwargs)

    def remove_guard(self, **txn_kwargs) -> Union["ReceiptAPI", "SafeTxID"]:
        return self.set_guard(ZERO_ADDRESS, **txn_kwargs)
