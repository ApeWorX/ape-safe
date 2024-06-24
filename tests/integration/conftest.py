import shutil
from contextlib import contextmanager

import pytest
from ape.utils import create_tempdir
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
    with _remove_safes(data_folder):
        yield


@pytest.fixture
def one_safe(data_folder, safes, safe):
    with _remove_safes(data_folder):
        safes.save_account(safe.alias, safe.address)
        yield safes.load_account(safe.alias)


@contextmanager
def _remove_safes(data_folder):
    with create_tempdir() as temp_dir:
        dest = temp_dir / "dest"
        shutil.move(data_folder, dest)
        yield
        shutil.move(dest, data_folder)
