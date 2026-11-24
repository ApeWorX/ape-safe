import pytest
from ape.api import AccountAPI
from ape.types import AddressType
from eip712.common import create_safe_tx_def

from ape_safe import client as client_module
from ape_safe.client import UnexecutedTxData
from ape_safe.exceptions import SafeClientException


def test_init(safe, OWNERS, THRESHOLD, safe_contract):
    assert safe.contract == safe_contract
    assert safe.confirmations_required == THRESHOLD
    assert safe.signers == [o.address for o in OWNERS]
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

    # NOTE: SafeL2 contracts have extra event
    assert receipt.events[-3:] == [
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

    # NOTE: SafeL2 contracts have extra event
    assert receipt.events[-2:] == [
        safe.contract.AddedOwner(owner=new_owner),
        safe.contract.ExecutionSuccess(),
    ]

    assert new_owner.address in safe.signers


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
    # NOTE: SafeL2 contracts have extra event
    assert receipt.events[-len(expected_events) :] == expected_events

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


def test_get_client(safe, monkeypatch):
    """
    Test getting a client for a specific chain ID.
    """
    monkeypatch.setattr(client_module, "GATEWAY_API_KEY", "test-key")
    # Create a test deployed_chain_ids list
    safe_data = safe.account_data
    safe_data.deployed_chain_ids = [1, 10, 100]
    safe.account_file_path.write_text(safe_data.model_dump_json())

    # Should work for a specified chain ID
    client = safe.get_client(chain_id=1)
    assert "/eth/" in client.base_url


def test_submit_upstream_hash_with_local_impersonation(safe, deployer, receiver, monkeypatch):
    upstream_chain_id = 1 if safe.provider.chain_id != 1 else 10
    nonce = safe.next_nonce
    safe_tx = create_safe_tx_def(str(safe.version), safe.address, upstream_chain_id)(
        to=receiver.address, nonce=nonce
    )
    txn = UnexecutedTxData.from_safe_tx(safe_tx, safe.confirmations_required).model_copy(
        update={"queue_chain_id": upstream_chain_id}
    )
    monkeypatch.setattr(safe.client, "get_safe_tx", lambda _: txn)

    with pytest.raises(SafeClientException, match="does not match its signed fields"):
        safe.submit_safe_tx(txn.safe_tx_hash, submitter=deployer)

    safe.submit_safe_tx(txn.safe_tx_hash, impersonate=True, submitter=deployer)
    assert safe.next_nonce == nonce + 1
