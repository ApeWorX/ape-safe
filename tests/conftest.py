import json
import tempfile
from pathlib import Path

import ape
import pytest
from ape.contracts import ContractContainer
from ape.utils import ZERO_ADDRESS
from ethpm_types import ContractType

from ape_safe import MultiSend
from ape_safe.accounts import SafeAccount

contracts_directory = Path(__file__).parent / "contracts"
TESTS_DIR = Path(__file__).parent.absolute()
DATA_FOLDER = Path(tempfile.mkdtemp()).resolve()
ape.config.DATA_FOLDER = DATA_FOLDER


@pytest.fixture(scope="session")
def config():
    return ape.config


@pytest.fixture
def data_folder(config):
    return config.DATA_FOLDER / "safe"


@pytest.fixture(scope="session")
def deployer(OWNERS):
    return OWNERS[-1]


@pytest.fixture(scope="session")
def receiver(accounts):
    return accounts[9]


@pytest.fixture(scope="session", params=["1.3.0"])  # TODO: Test more versions later?
def VERSION(request):
    return request.param


@pytest.fixture(scope="session")
def SafeSingleton(project, VERSION):
    return project.dependencies["safe-contracts"][VERSION]["GnosisSafe"]


@pytest.fixture
def singleton(deployer: SafeAccount, SafeSingleton):
    return deployer.deploy(SafeSingleton)


@pytest.fixture(scope="session")
def SafeProxy(project, SafeSingleton, VERSION):
    Proxy = project.dependencies["safe-contracts"][VERSION]["GnosisSafeProxy"]
    IProxy = project.dependencies["safe-contracts"][VERSION]["IProxy"]
    # NOTE: Proxy only has a constructor, so we add the rest of it's ABI here for simplified use
    Proxy.contract_type.abi += [IProxy.contract_type.abi[0], *SafeSingleton.contract_type.abi]
    return Proxy


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
def safe_contract(singleton, SafeProxy, OWNERS, THRESHOLD):
    deployer = OWNERS[0]
    safe = deployer.deploy(SafeProxy, singleton)
    safe.setup(
        OWNERS,
        THRESHOLD,
        # no modules
        ZERO_ADDRESS,
        b"",
        # no fallback
        ZERO_ADDRESS,
        # no payment
        ZERO_ADDRESS,
        0,
        ZERO_ADDRESS,
        sender=deployer,
    )
    return safe


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
def safes():
    return ape.accounts.containers["safe"]


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
def foundry(networks):
    with networks.ethereum.local.use_provider("foundry") as provider:
        yield provider


@pytest.fixture
def multisend():
    MultiSend.inject()
    return MultiSend()
