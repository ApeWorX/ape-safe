import pytest
from ape import networks

from ape_safe import MultiSend
from ape_safe.exceptions import SafeLogicError


def test_asset(vault, token):
    assert vault.asset() == token


def test_default_operation(safe, token, vault):
    with networks.ethereum.local.use_provider("foundry"):
        ms = MultiSend()
        ms.inject()
        amount = token.balanceOf(safe)
        ms.add(token.approve, vault, safe)
        ms.add(vault.transfer, safe, amount)
        receipt = ms(sender=safe)
        assert receipt.txn_hash


def test_no_operation(safe, token, vault):
    with networks.ethereum.local.use_provider("foundry"):
        ms = MultiSend()
        ms.inject()
        amount = token.balanceOf(safe)
        ms.add(token.approve, vault, safe)
        ms.add(vault.transfer, safe, amount)
        with pytest.raises(SafeLogicError, match="Safe transaction failed"):
            ms(sender=safe, operation=0)
