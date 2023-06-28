import pytest


def test_init(safe, OWNERS, THRESHOLD, safe_contract):
    assert safe.contract == safe_contract
    assert safe.confirmations_required == THRESHOLD
    assert safe.signers == list(o.address for o in OWNERS)
    assert safe.next_nonce == 0


@pytest.mark.parametrize("mode", ["impersonate", "sign"])
def test_swap_owner(safe, accounts, OWNERS, mode):
    impersonate = mode == "impersonate"
    old_owner = safe.signers[0]
    new_owner = accounts[len(OWNERS)]  # replace owner 1 with account N + 1
    assert new_owner.address not in safe.signers
    # NOTE: Since the signers are processed in order, we replace the last account

    prev_owner = safe.compute_prev_signer(old_owner)

    # TODO: Remove `gas_limit` by allowing forking to compute gas limit
    receipt = safe.contract.swapOwner(
        prev_owner,
        old_owner,
        new_owner,
        sender=safe,
        impersonate=impersonate,
    )

    assert receipt.events == [
        safe.contract.RemovedOwner(owner=old_owner),
        safe.contract.AddedOwner(owner=new_owner),
        safe.contract.ExecutionSuccess(),
    ]

    assert old_owner not in safe.signers
    assert new_owner.address in safe.signers


@pytest.mark.parametrize("mode", ["impersonate", "sign"])
def test_add_owner(safe, accounts, OWNERS, mode):
    impersonate = mode == "impersonate"
    new_owner = accounts[len(OWNERS)]  # replace owner 1 with account N + 1
    assert new_owner.address not in safe.signers

    # TODO: Remove `gas_limit` by allowing forking to compute gas limit
    receipt = safe.contract.addOwnerWithThreshold(
        new_owner,
        safe.confirmations_required,
        sender=safe,
        impersonate=impersonate,
    )

    assert receipt.events == [
        safe.contract.AddedOwner(owner=new_owner),
        safe.contract.ExecutionSuccess(),
    ]

    assert new_owner.address in safe.signers


@pytest.mark.parametrize("mode", ["impersonate", "sign"])
def test_remove_owner(safe, OWNERS, mode):
    impersonate = mode == "impersonate"
    if len(OWNERS) == 1:
        pytest.skip("Can't remove the only owner")

    old_owner = safe.signers[0]
    new_threshold = max(len(OWNERS) - 1, safe.confirmations_required - 1)
    threshold_changed = new_threshold != safe.confirmations_required

    prev_owner = safe.compute_prev_signer(old_owner)
    receipt = safe.contract.removeOwner(
        prev_owner,
        old_owner,
        # Can't set the threshold to zero or more than the number of owners after removal
        new_threshold,
        sender=safe,
        impersonate=impersonate,
    )

    expected_events = [
        safe.contract.RemovedOwner(owner=old_owner),
        safe.contract.ExecutionSuccess(),
    ]
    if threshold_changed:
        expected_events.insert(1, safe.contract.ChangedThreshold(threshold=new_threshold))
    assert receipt.events == expected_events

    assert old_owner not in safe.signers
