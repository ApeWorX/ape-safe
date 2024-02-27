from pathlib import Path

import pytest
from ape.api import AccountAPI
from ape.exceptions import SignatureError
from ape.types import AddressType
from eth_utils import add_0x_prefix


def test_data_folder(safes, config):
    assert Path.home() not in safes.data_folder.parents
    assert safes.data_folder == config.DATA_FOLDER / "safe"


def test_init(safe, OWNERS, THRESHOLD, safe_contract):
    assert safe.contract == safe_contract
    assert safe.confirmations_required == THRESHOLD
    assert safe.signers == list(o.address for o in OWNERS)
    assert safe.next_nonce == 0


@pytest.mark.parametrize("mode", ("impersonate", "api", "sign"))
def test_swap_owner(safe, accounts, OWNERS, mode):
    impersonate = mode == "impersonate"
    submit = mode != "api"

    old_owner = safe.signers[0]
    new_owner = accounts[len(OWNERS)]  # replace owner 1 with account N + 1
    assert new_owner.address not in safe.signers
    # NOTE: Since the signers are processed in order, we replace the last account

    prev_owner = safe.compute_prev_signer(old_owner)

    def exec_transaction():
        return safe.contract.swapOwner(
            prev_owner,
            old_owner,
            new_owner,
            sender=safe,
            impersonate=impersonate,
            submit=submit,
        )

    if submit:
        receipt = exec_transaction()

    else:
        # Attempting to execute should raise `SignatureError` and push `safe_tx` to mock client
        size = len(list(safe.client.get_transactions(confirmed=False)))
        assert size == 0

        with pytest.raises(SignatureError):
            exec_transaction()

        pending_txns = list(safe.client.get_transactions(confirmed=False))
        assert len(pending_txns) == 1
        assert len(pending_txns[0].confirmations) >= 1
        safe_tx_hash = add_0x_prefix(f"{pending_txns[0].safe_tx_hash}")

        safe_tx_data = pending_txns[0]
        safe_tx = safe.create_safe_tx(**safe_tx_data.model_dump(by_alias=True, mode="json"))

        # Ensure client confirmations works
        client_confs = list(safe.client.get_confirmations(safe_tx_hash))
        assert len(client_confs) >= 1

        # Ensure API confirmations work
        api_confs = safe.get_api_confirmations(safe_tx)
        assert len(api_confs) >= 1

        # `safe_tx` is in mock client, extract it and execute it successfully this time
        receipt = safe.submit_safe_tx(safe_tx)

    assert receipt.events == [
        safe.contract.RemovedOwner(owner=old_owner),
        safe.contract.AddedOwner(owner=new_owner),
        safe.contract.ExecutionSuccess(),
    ]

    assert old_owner not in safe.signers
    assert new_owner.address in safe.signers


@pytest.mark.parametrize("mode", ("impersonate", "api", "sign"))
def test_add_owner(safe, accounts, OWNERS, mode):
    impersonate = mode == "impersonate"
    submit = mode != "api"

    new_owner = accounts[len(OWNERS)]  # replace owner 1 with account N + 1
    assert new_owner.address not in safe.signers

    def exec_transaction():
        return safe.contract.addOwnerWithThreshold(
            new_owner,
            safe.confirmations_required,
            sender=safe,
            impersonate=impersonate,
            submit=submit,
        )

    if submit:
        receipt = exec_transaction()

    else:
        # Attempting to execute should emit a `SignatureError` and push `safe_tx` to mock client
        assert len(list(safe.client.get_transactions(confirmed=False))) == 0
        with pytest.raises(SignatureError):
            exec_transaction()

        assert len(list(safe.client.get_transactions(confirmed=False))) == 1

        # `safe_tx` is in mock client, extract it and execute it successfully this time
        safe_tx_data = next(safe.client.get_transactions(confirmed=False))
        safe_tx = safe.create_safe_tx(**safe_tx_data.model_dump(by_alias=True, mode="json"))
        receipt = safe.submit_safe_tx(safe_tx)

    assert receipt.events == [
        safe.contract.AddedOwner(owner=new_owner),
        safe.contract.ExecutionSuccess(),
    ]

    assert new_owner.address in safe.signers


@pytest.mark.parametrize("mode", ["impersonate", "api", "sign"])
def test_remove_owner(safe, OWNERS, mode):
    impersonate = mode == "impersonate"
    submit = mode != "api"
    if len(OWNERS) == 1:
        pytest.skip("Can't remove the only owner")

    old_owner = safe.signers[0]
    new_threshold = max(len(OWNERS) - 1, safe.confirmations_required - 1)
    threshold_changed = new_threshold != safe.confirmations_required

    prev_owner = safe.compute_prev_signer(old_owner)

    def exec_transaction():
        return safe.contract.removeOwner(
            prev_owner,
            old_owner,
            # Can't set the threshold to zero or more than the number of owners after removal
            new_threshold,
            sender=safe,
            impersonate=impersonate,
            submit=submit,
        )

    if submit:
        receipt = exec_transaction()

    else:
        # Attempting to execute should emit a `SignatureError` and push `safe_tx` to mock client
        assert len(list(safe.client.get_transactions(confirmed=False))) == 0
        with pytest.raises(SignatureError):
            exec_transaction()

        assert len(list(safe.client.get_transactions(confirmed=False))) == 1

        # `safe_tx` is in mock client, extract it and execute it successfully this time
        safe_tx_data = next(safe.client.get_transactions(confirmed=False))
        safe_tx = safe.create_safe_tx(**safe_tx_data.model_dump(by_alias=True, mode="json"))
        receipt = safe.submit_safe_tx(safe_tx)

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
