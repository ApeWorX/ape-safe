import pytest

from ape_safe.exceptions import SafeClientException


def test_manage_delegates(safe, delegate, OWNERS):
    owner = OWNERS[0]
    assert owner.address not in safe.client.get_delegates()

    safe.client.add_delegate(delegate.address, "pepito", owner)
    assert delegate.address in safe.client.get_delegates()[owner.address]
    assert delegate.address in safe.all_delegates()
    # NOTE: Only in MockSafeClient
    assert safe.client.delegator_for_delegate(delegate.address) == owner.address

    safe.client.remove_delegate(delegate.address, owner)
    assert owner.address not in safe.client.get_delegates()

    with pytest.raises(SafeClientException):
        # Only signers can create a delegate
        safe.client.add_delegate(owner, "root privledges", delegate)


def test_delegate_can_propose_safe_tx(safe, delegate, OWNERS):
    owner = OWNERS[0]

    safe_tx = safe.create_safe_tx(
        safe.contract.addOwnerWithThreshold.as_transaction(delegate, safe.confirmations_required)
    )

    with pytest.raises(SafeClientException):
        # Not a delegate or signer
        safe.propose_safe_tx(safe_tx, submitter=delegate)

    safe.client.add_delegate(delegate.address, "pepito", owner)
    safe.propose_safe_tx(safe_tx, submitter=delegate)

    assert len(safe.get_api_confirmations(safe_tx)) == 0
    assert list(
        (safe_tx.signable_message, confs) for safe_tx, confs in safe.pending_transactions()
    ) == [(safe_tx.signable_message, [])]
