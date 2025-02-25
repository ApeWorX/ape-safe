import secrets
from functools import cache
from typing import TYPE_CHECKING, Iterable, Optional, Union

from ape.types import AddressType
from ape.utils import ZERO_ADDRESS, ManagerAccessMixin
from packaging.version import Version

from ape_safe.packages import MANIFESTS_BY_VERSION, PackageType, get_factory, get_singleton

if TYPE_CHECKING:
    from ape.api import AccountAPI, BaseAddress
    from ape.contracts import ContractInstance


class SafeFactory(ManagerAccessMixin):
    _singleton: dict[Version, "ContractInstance"] = {}
    _factory: dict[Version, "ContractInstance"] = {}

    @classmethod
    def inject(cls, version: Version, deployer: "AccountAPI"):
        cls._singleton[version] = deployer.deploy(PackageType.SINGLETON(version))
        cls._factory[version] = deployer.deploy(PackageType.PROXY_FACTORY(version))

    @cache
    def get_factory(self, version: Version) -> "ContractInstance":
        if injected_factory := self._factory.get(version):
            return injected_factory

        return get_factory(self.chain_manager.chain_id, version)

    @property
    def contract(self) -> "ContractInstance":
        return self.get_factory(max(MANIFESTS_BY_VERSION))

    @cache
    def get_singleton(self, version: Version) -> "ContractInstance":
        if injected_singleton := self._singleton.get(version):
            return injected_singleton

        return get_singleton(self.chain_manager.chain_id, version)

    def create(
        self,
        owners: Iterable[Union["BaseAddress", "AddressType", str]],
        threshold: int,
        callback_address: Union["BaseAddress", "AddressType", str] = ZERO_ADDRESS,
        callback_calldata: Optional[bytes] = None,
        fallback_handler: Union["BaseAddress", "AddressType", str] = ZERO_ADDRESS,
        payment_token: Union["BaseAddress", "AddressType", str] = ZERO_ADDRESS,
        payment_amount: Union[str, int] = 0,
        payment_receiver: Union["BaseAddress", "AddressType", str] = ZERO_ADDRESS,
        salt: Optional[int] = None,
        version: Union[Version, str, None] = None,
        **txn_kwargs,
    ) -> "ContractInstance":
        if not (owners := [self.conversion_manager.convert(a, AddressType) for a in owners]):
            raise ValueError("Cannot make a Safe with 0 owners.")

        elif not (1 <= threshold <= len(owners)):
            raise ValueError(f"Threshold must be between '1' and '{len(owners)}'")

        if callback_address != ZERO_ADDRESS:
            callback_address = self.conversion_manager.convert(callback_address, AddressType)

        if fallback_handler != ZERO_ADDRESS:
            fallback_handler = self.conversion_manager.convert(fallback_handler, AddressType)

        if (payment_amount := self.conversion_manager.convert(payment_amount, int)) > 0 and (
            payment_token == ZERO_ADDRESS or payment_receiver == ZERO_ADDRESS
        ):
            raise ValueError(
                "If sending payments, must include both `payment_token` and `payment_receiver`"
            )

        else:  # Both are not empty
            payment_token = self.conversion_manager.convert(payment_token, AddressType)
            payment_receiver = self.conversion_manager.convert(payment_receiver, AddressType)

        if not salt:
            salt = secrets.randbits(256)

        if not version:
            version = max(MANIFESTS_BY_VERSION)

        elif not isinstance(version, Version):
            version = Version(version.lstrip("v"))

        Proxy = PackageType.PROXY(version)

        proxy_setup_abi = next(abi for abi in Proxy.abi if getattr(abi, "name", None) == "setup")
        args = self.conversion_manager.convert_method_args(
            proxy_setup_abi,
            [
                owners,
                threshold,
                callback_address,
                callback_calldata or b"",
                fallback_handler,
                payment_token,
                payment_amount,
                payment_receiver,
            ],
        )
        encoded_args = self.provider.network.ecosystem.encode_calldata(proxy_setup_abi, *args)
        method_id = self.provider.network.ecosystem.get_method_selector(proxy_setup_abi)
        initializer_calldata = method_id + encoded_args

        factory_contract = self.get_factory(version)
        singleton = self.get_singleton(version)
        tx = factory_contract.createProxyWithNonce(
            singleton, initializer_calldata, salt, **txn_kwargs
        )

        # NOTE: Use log decoding because it is more available than `.return_value`
        proxy_address = tx.decode_logs(factory_contract.ProxyCreation)[0].proxy
        return Proxy.at(proxy_address)
