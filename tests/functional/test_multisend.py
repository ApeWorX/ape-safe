import pytest

from ape_safe.multisend import MultiSend


@pytest.fixture(scope="module", autouse=True)
def new_multisend(VERSION):
    MultiSend.inject(VERSION)


def test_default_operation(safe, deployer, token, vault, mode):
    amount = 100
    token.DEBUG_mint(safe, amount, sender=deployer)

    assert vault.asset() == token
    batch = safe.create_batch()
    batch.add(token.approve, vault, amount)
    batch.add(vault.deposit, amount, safe)

    if mode == "api":
        safe_tx_id = batch.propose(safe, submitter=deployer)
        if safe.confirmations_required > 1:
            safe.add_signatures(safe_tx_id)
        receipt = safe.submit_safe_tx(safe_tx_id, submitter=deployer)

    else:
        receipt = batch(sender=safe, impersonate=(mode == "impersonate"), safeTxGas=300_000)

    assert receipt.txn_hash


def test_decode_multisend(VERSION):
    calldata = bytes.fromhex(
        "8d80ff0a0000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000016b00527e80008d212e2891c737ba8a2768a7337d7fd200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000024f0080878000000000000000000000000584bffc5f51ccae39ad69f1c399743620e619c2b00da18f789a1d9ad33e891253660fcf1332d236b2900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000024e74b981b000000000000000000000000584bffc5f51ccae39ad69f1c399743620e619c2b0027b5739e22ad9033bcbf192059122d163b60349d000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000247a55036500000000000000000000000000000000000000000000000000002a1b324b8f68000000000000000000000000000000000000000000"  # noqa: E501
    )
    ms = MultiSend(version=VERSION)
    ms.add_from_calldata(calldata)
    assert ms.handler.encode_input(b"".join(ms.encoded_calls)) == calldata
