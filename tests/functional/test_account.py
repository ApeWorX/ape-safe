import pytest
from ape.api import AccountAPI
from ape.types import AddressType


def test_init(safe, OWNERS, THRESHOLD, safe_contract):
    assert safe.contract == safe_contract
    assert safe.confirmations_required == THRESHOLD
    assert safe.signers == list(o.address for o in OWNERS)
    assert safe.next_nonce == 0


def test_swap_owner(safe, accounts, OWNERS, exec_transaction):
    old_owner = safe.signers[0]
    new_owner = accounts[len(OWNERS)]  # replace owner 1 with account N + 1
    assert new_owner.address not in safe.signers
    # NOTE: Since the signers are processed in order, we replace the last account

    prev_owner = safe.compute_prev_signer(old_owner)

    receipt = exec_transaction(
        safe.contract.swapOwner,
        prev_owner,
        old_owner,
        new_owner,
    )

    assert receipt.events == [
        safe.contract.RemovedOwner(owner=old_owner),
        safe.contract.AddedOwner(owner=new_owner),
        safe.contract.ExecutionSuccess(),
    ]

    assert old_owner not in safe.signers
    assert new_owner.address in safe.signers


def test_add_owner(safe, accounts, OWNERS, exec_transaction):
    new_owner = accounts[len(OWNERS)]  # replace owner 1 with account N + 1
    assert new_owner.address not in safe.signers

    receipt = exec_transaction(
        safe.contract.addOwnerWithThreshold,
        new_owner,
        safe.confirmations_required,
    )

    assert receipt.events == [
        safe.contract.AddedOwner(owner=new_owner),
        safe.contract.ExecutionSuccess(),
    ]

    assert new_owner.address in safe.signers


@pytest.mark.parametrize("mode", ["impersonate", "api", "sign"])
def test_remove_owner(safe, OWNERS, exec_transaction):
    if len(OWNERS) == 1:
        pytest.skip("Can't remove the only owner")

    old_owner = safe.signers[0]
    new_threshold = max(len(OWNERS) - 1, safe.confirmations_required - 1)
    threshold_changed = new_threshold != safe.confirmations_required

    prev_owner = safe.compute_prev_signer(old_owner)

    receipt = exec_transaction(
        safe.contract.removeOwner,
        prev_owner,
        old_owner,
        # Can't set the threshold to zero or more than the number of owners after removal
        new_threshold,
    )

    expected_events = [
        safe.contract.RemovedOwner(owner=old_owner),
        safe.contract.ExecutionSuccess(),
    ]
    if threshold_changed:
        expected_events.insert(1, safe.contract.ChangedThreshold(threshold=new_threshold))
    assert receipt.events == expected_events

    assert old_owner not in safe.signers


def test_account_type(safe):
    actual = type(safe)
    assert issubclass(actual, AccountAPI)


def test_safe_account_convert(safe):
    """
    We had a bug where converting safe accounts to AddressType
    would fail.
    """
    convert = safe.conversion_manager.convert
    actual = convert(safe, AddressType)
    assert actual == safe.address


def test_get_client(safe):
    """
    Test getting a client for a specific chain ID.
    """
    # Create a test deployed_chain_ids list
    safe_data = safe.account_data
    safe_data.deployed_chain_ids = [1, 10, 100]
    safe.account_file_path.write_text(safe_data.model_dump_json())

    # Should work for a specified chain ID
    client = safe.get_client(chain_id=1)
    assert "/eth/" in client.base_url
