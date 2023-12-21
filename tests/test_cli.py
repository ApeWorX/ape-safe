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


def test_list_no_safes(runner, cli, no_safes):
    result = runner.invoke(cli, ["list"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "No Safes found" in result.output


def test_list_one_safe(runner, cli, one_safe):
    result = runner.invoke(cli, ["list"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "Found 1 Safe" in result.output
    assert "0x5FbDB2315678afecb367f032d93F642f64180aa3" in result.output
