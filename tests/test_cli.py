import pytest
from click.testing import CliRunner

from ape_safe._cli import cli as CLI


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def cli():
    return CLI


def test_list_pending_transactions(runner, cli):
    command = ["pending", "list"]
    result = runner.invoke(cli, command)
    assert result.exit_code == 0
