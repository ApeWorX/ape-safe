import json
import tempfile
from pathlib import Path

import pytest
from ape.contracts import ContractContainer
from ethpm_types import ContractType
from packaging.version import Version

from ape_safe import MultiSend
from ape_safe.accounts import SafeAccount
from ape_safe.factory import SafeFactory

contracts_directory = Path(__file__).parent / "contracts"


@pytest.fixture(
    scope="session",
    # TODO: Test more versions.
    params=(
        "1.4.1",
        "1.3.0",
        "1.1.1",
    ),
)
def VERSION(request):
    return Version(request.param)


@pytest.fixture(scope="session")
def deployer(OWNERS):
    return OWNERS[-1]


@pytest.fixture(scope="session")
def safe_factory(VERSION, deployer):
    SafeFactory.inject(VERSION, deployer)
    return SafeFactory()


@pytest.fixture(scope="session")
def receiver(accounts):
    return accounts[9]


@pytest.fixture(scope="session")
def delegate(accounts):
    return accounts[8]


@pytest.fixture(scope="session", params=["1/1", "1/2", "2/2", "2/3", "3/3"])
def MULTISIG_TYPE(request):
    # Param is `M/N`, but encoded as a string for repr in pytest
    return request.param.split("/")


@pytest.fixture(scope="session")
def THRESHOLD(MULTISIG_TYPE):
    M, _ = MULTISIG_TYPE
    return int(M)


@pytest.fixture(scope="session")
def OWNERS(accounts, MULTISIG_TYPE):
    _, N = MULTISIG_TYPE
    return accounts[: int(N)]


@pytest.fixture
def safe_contract(safe_factory, deployer, OWNERS, THRESHOLD):
    return safe_factory.create(OWNERS, THRESHOLD, sender=deployer)


@pytest.fixture
def safe_data_file(chain, safe_contract):
    with tempfile.NamedTemporaryFile() as fp:
        file = Path(str(fp.name))
        file.write_text(
            json.dumps(
                {
                    "address": safe_contract.address,
                    "deployed_chain_ids": [chain.provider.chain_id],
                }
            )
        )
        yield file


@pytest.fixture
def safe(safe_data_file):
    return SafeAccount(account_file_path=safe_data_file)


@pytest.fixture
def token(deployer: SafeAccount):
    text = (contracts_directory / "Token.json").read_text()
    contract = ContractType.model_validate_json(text)
    return deployer.deploy(ContractContainer(contract))


@pytest.fixture
def vault(deployer: SafeAccount, token):
    text = (contracts_directory / "VyperVault.json").read_text()
    vault = ContractContainer(ContractType.model_validate_json(text))
    return deployer.deploy(vault, token)


@pytest.fixture
def new_multisend(VERSION):
    MultiSend.inject(VERSION)

    def new_multisend():
        return MultiSend(VERSION)

    return new_multisend
