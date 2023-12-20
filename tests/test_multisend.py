import pytest

from ape_safe.exceptions import SafeLogicError


def test_asset(vault, token):
    assert vault.asset() == token


def test_default_operation(safe, token, vault, multisend):
    amount = token.balanceOf(safe)
    multisend.add(token.approve, vault, 123)
    multisend.add(vault.transfer, safe, amount)
    receipt = multisend(sender=safe)
    assert receipt.txn_hash


def test_no_operation(safe, token, vault, multisend):
    amount = token.balanceOf(safe)
    multisend.add(token.approve, vault, 123)
    multisend.add(vault.transfer, safe, amount)
    with pytest.raises(SafeLogicError, match="Safe transaction failed"):
        multisend(sender=safe, operation=0)
