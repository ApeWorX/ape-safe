import ape
import pytest
from ape.utils import create_tempdir
from click.testing import CliRunner

from ape_safe._cli import cli as ape_safe_cli


@pytest.fixture
def safe_container():
    return ape.accounts.containers["safe"]


# NOTE: Every test gets a different data folder
@pytest.fixture(scope="function", autouse=True)
def patch_data_folder(monkeypatch, safe_container):
    with create_tempdir() as data_folder_override:
        monkeypatch.setattr(safe_container, "data_folder", data_folder_override)
        yield


@pytest.fixture
def runner():
    yield CliRunner(mix_stderr=True)


@pytest.fixture
def cli():
    return ape_safe_cli


@pytest.fixture
def safe_account(safe_container, safe):
    safe_container.save_account(safe.alias, safe.address)

    yield safe_container.load_account(safe.alias)

    if safe.alias in safe_container.aliases:
        safe_container.delete_account(safe.alias)
