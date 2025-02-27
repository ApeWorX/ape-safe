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


with resources.as_file(resources.files(__package__).joinpath("manifests")) as manifest_folder:
    MANIFESTS_BY_VERSION = {
        Version(m.stem.lstrip("safe-v")): m for m in manifest_folder.glob("safe-v*.json")
    }


@cache
def get_manifest(version: Version) -> ProjectManager:
    if not (manifest_path := MANIFESTS_BY_VERSION.get(version)):
        raise KeyError(f"Unknown version 'v{version}'.")

    return ProjectManager.from_manifest(manifest_path)


class PackageType(str, Enum):
    SINGLETON = "SafeSingleton"
    PROXY = "SafeProxy"
    PROXY_FACTORY = "SafeProxyFactory"
    MULTISEND = "MultiSend"

    def __call__(self, version: Union[Version, str]) -> "ContractContainer":
        if not isinstance(version, Version):
            version = Version(version.lstrip("v"))

        package = get_manifest(version)

        if self is PackageType.MULTISEND:
            if version == Version("1.1.1"):
                return package.MultiSend

            # NOTE: Always use `MultiSendCallOnly` to prevent against delegatecall issues
            return package.MultiSendCallOnly

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


def get_deployment_artifact(
    package_type: PackageType, chain_id: int, version: Union[Version, str]
) -> "ContractInstance":
    if not isinstance(version, Version):
        version = Version(version.lstrip("v"))

    if package_type is PackageType.SINGLETON:
        deployment_filename = "gnosis_safe.json" if version <= Version("1.3.0") else "/safe.json"

    elif package_type is PackageType.PROXY_FACTORY:
        deployment_filename = (
            "proxy_factory.json" if version <= Version("1.3.0") else "/safe_proxy_factory.json"
        )

    elif package_type is PackageType.MULTISEND:
        deployment_filename = "multi_send.json"

    else:
        raise

    # TODO: Cache this to disk?
    response = requests.get(BASE_ASSETS_URL + f"v{version}/{deployment_filename}")
    deployment_asset = DeploymentAsset.model_validate(response.json())

    if not (deployment_type := deployment_asset.networkAddresses.get(chain_id)):
        raise KeyError(f"Chain ID '{chain_id}' does not have a known deployment")

    deployment_info = deployment_asset.deployments[
        deployment_type[0] if isinstance(deployment_type, list) else deployment_type
    ]

    return package_type(version).at(deployment_info.address)  # type: ignore[misc]


def get_singleton(chain_id: int, version: Union[Version, str]) -> "ContractInstance":
    return get_deployment_artifact(PackageType.SINGLETON, chain_id, version)


def get_factory(chain_id: int, version: Union[Version, str]) -> "ContractInstance":
    return get_deployment_artifact(PackageType.PROXY_FACTORY, chain_id, version)


def get_multisend(chain_id: int, version: Union[Version, str]) -> "ContractInstance":
    return get_deployment_artifact(PackageType.MULTISEND, chain_id, version)
