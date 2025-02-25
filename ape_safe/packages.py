from enum import Enum
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING, Union

import requests
from ape.managers.project import ProjectManager
from packaging.version import Version
from pydantic import BaseModel

if TYPE_CHECKING:
    from ape.contracts import ContractContainer, ContractInstance


class PackageType(str, Enum):
    SINGLETON = "SafeSingleton"
    PROXY = "SafeProxy"
    PROXY_FACTORY = "SafeProxyFactory"
    MULTISEND = "Multisend"

    @cache
    def get_manifest(self, version: Version) -> ProjectManager:
        with resources.as_file(
            resources.files(__package__).joinpath("manifests")
        ) as manifest_folder:
            if not (manifest_path := manifest_folder / f"safe-v{version}.json").exists():
                raise KeyError(f"Unknown version 'v{version}'.")

        return ProjectManager.from_manifest(manifest_path)

    def __call__(self, version: Union[Version, str]) -> "ContractContainer":
        if not isinstance(version, Version):
            version = Version(version.lstrip("v"))

        package = self.get_manifest(version)

        if self is PackageType.MULTISEND:
            return package.MultiSend

        elif self is PackageType.PROXY_FACTORY:
            if version == Version("1.1.1"):
                return package.ProxyFactory

            elif version <= Version("1.3.0"):
                return package.GnosisSafeProxyFactory

            else:
                return package.SafeProxyFactory

        elif version > Version("1.3.0"):
            SafeSingleton = package.Safe

        else:
            SafeSingleton = package.GnosisSafe

        if self is PackageType.SINGLETON:
            return SafeSingleton

        # NOTE: SafeProxy has `masterCopy() -> address` in it, vs. `SafeSingleton`
        SafeSingleton.contract_type.abi.append(package.IProxy.contract_type.abi[0])
        return SafeSingleton


class DeploymentType(str, Enum):
    CANONICAL = "canonical"
    EIP155 = "eip155"
    ZKSYNC = "zksync"


class DeploymentInfo(BaseModel):
    address: str
    codeHash: str


class DeploymentAsset(BaseModel):
    released: bool
    contractName: str
    version: str
    deployments: dict[DeploymentType, DeploymentInfo]
    # ChainID => DeploymentType
    networkAddresses: dict[int, Union[DeploymentType, list[DeploymentType]]]


BASE_ASSETS_URL = (
    "https://raw.githubusercontent.com/safe-global/safe-deployments/refs/heads/main/src/assets/"
)


def get_singleton(chain_id: int, version: Union[Version, str]) -> "ContractInstance":
    if not isinstance(version, Version):
        version = Version(version.lstrip("v"))

    # TODO: Cache this to disk?
    response = requests.get(
        BASE_ASSETS_URL
        + f"v{version}/"
        + ("gnosis_safe.json" if version <= Version("1.3.0") else "/safe.json")
    )
    deployment_asset = DeploymentAsset.model_validate(response.json())

    if not (deployment_type := deployment_asset.networkAddresses.get(chain_id)):
        raise KeyError(f"Chain ID '{chain_id}' does not have a known deployment")

    deployment_info = deployment_asset.deployments[
        deployment_type[0] if isinstance(deployment_type, list) else deployment_type
    ]

    Singleton = PackageType.SINGLETON(version)
    return Singleton.at(deployment_info.address)


def get_factory(chain_id: int, version: Union[Version, str]) -> "ContractInstance":
    if not isinstance(version, Version):
        version = Version(version.lstrip("v"))

    # TODO: Cache this to disk?
    response = requests.get(
        BASE_ASSETS_URL
        + f"v{version}/"
        + ("proxy_factory.json" if version <= Version("1.3.0") else "/safe_proxy_factory.json")
    )
    deployment_asset = DeploymentAsset.model_validate(response.json())

    if not (deployment_type := deployment_asset.networkAddresses.get(chain_id)):
        raise KeyError(f"Chain ID '{chain_id}' does not have a known deployment")

    deployment_info = deployment_asset.deployments[
        deployment_type[0] if isinstance(deployment_type, list) else deployment_type
    ]

    ProxyFactory = PackageType.PROXY_FACTORY(version)
    return ProxyFactory.at(deployment_info.address)
