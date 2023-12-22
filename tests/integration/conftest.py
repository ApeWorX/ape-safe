import shutil

import pytest
from click.testing import CliRunner

from ape_safe._cli import cli as CLI


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cli():
    return CLI


@pytest.fixture
def no_safes(data_folder):
    shutil.rmtree(data_folder, ignore_errors=True)


@pytest.fixture
def one_safe(data_folder, safes, safe):
    shutil.rmtree(data_folder)
    safes.save_account(safe.alias, safe.address)
    return safes.load_account(safe.alias)
