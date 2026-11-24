import json
from unittest.mock import Mock

import pytest
from ape.types import MessageSignature
from ape.utils import ZERO_ADDRESS
from eip712.common import create_safe_tx_def
from eth_account._utils.encode_typed_data.encoding_and_hashing import hash_struct
from eth_utils import keccak, to_checksum_address, to_hex
from requests import Response

from ape_safe import client as client_module
from ape_safe.client import ExecutedTxData, SafeClient
from ape_safe.exceptions import ClientResponseError, SafeClientException
from ape_safe.utils import get_safe_tx_hash

SAFE = to_checksum_address("0x" + "ab" * 20)
OWNER = to_checksum_address("0x" + "cd" * 20)
OTHER_OWNER = to_checksum_address("0x" + "ef" * 20)
DELEGATE = to_checksum_address("0x" + "ac" * 20)
SIGNATURE = MessageSignature(v=27, r=b"\x01" * 32, s=b"\x02" * 32)
OTHER_SIGNATURE = MessageSignature(v=28, r=b"\x03" * 32, s=b"\x04" * 32)
DATE = "2026-11-20T00:00:00Z"
QUEUE = "https://api.safe.global/queue/api/v1"
INDEX = "https://api.safe.global/tx-service/eth/api"


@pytest.fixture
def queue_client(monkeypatch):
    monkeypatch.setattr(client_module, "GATEWAY_API_KEY", "test-key")
    client = SafeClient(SAFE, chain_id=1)
    details = Mock(nonce=5, threshold=2, owners=[OWNER, OTHER_OWNER])
    monkeypatch.setattr(SafeClient, "safe_details", property(lambda _: details))
    http = Mock()
    monkeypatch.setattr(client.session, "request", http)
    return client, http


def response(status, payload=None):
    value = Response()
    value.status_code = status
    value._content = json.dumps(payload).encode()
    return value


def confirmation(owner=OWNER):
    return {
        "owner": owner.lower(),
        "signature": to_hex(SIGNATURE.encode_rsv()),
        "signatureType": "EOA",
        "created": DATE,
    }


def queue_tx(nonce, safe_tx_hash=None, confirmations=None):
    return {
        "chainId": "1",
        "safe": SAFE.lower(),
        "to": None,
        "gasToken": None,
        "refundReceiver": None,
        "nonce": str(nonce),
        "value": "0",
        "operation": 0,
        "safeTxGas": "11",
        "baseGas": "22",
        "gasPrice": "0",
        "safeTxHash": safe_tx_hash or "0x" + "ab" * 32,
        "created": DATE,
        "modified": DATE,
        "txHash": None,
        "confirmations": confirmations if confirmations is not None else [confirmation()],
    }


def test_pending_list_pages_in_descending_nonce_order(queue_client):
    client, http = queue_client
    endpoint = f"{QUEUE}/multisig-transactions/queue"
    next_page = f"{endpoint}?safes={SAFE}:1&nonceOrder=desc&offset=1"
    http.side_effect = [
        response(200, {"results": [queue_tx(8)], "next": next_page}),
        response(200, {"results": [queue_tx(6)], "next": None}),
    ]

    transactions = list(
        client.get_transactions(confirmed=False, filter_by_missing_signers={OTHER_OWNER})
    )

    assert [txn.nonce for txn in transactions] == [8, 6]
    txn = transactions[0]
    assert txn.safe == SAFE
    assert txn.to == txn.gas_token == txn.refund_receiver == ZERO_ADDRESS
    assert txn.confirmations[0].owner == OWNER
    assert txn.confirmations_required == 2
    assert txn.as_safe_tx("1.4.1", chain_id=1).baseGas == 22
    assert txn.as_safe_tx("1.1.1").dataGas == 22
    first, second = http.call_args_list
    assert first.args == ("GET", endpoint)
    assert first.kwargs["params"] == {"safes": f"{SAFE}:1", "nonceOrder": "desc"}
    assert first.kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert second.args == ("GET", endpoint)
    assert second.kwargs["params"] == {**first.kwargs["params"], "offset": 1}


def test_all_transactions_keeps_executed_history_on_transaction_service(queue_client):
    client, http = queue_client
    executed = {
        **queue_tx(4, confirmations=[]),
        "safe": SAFE,
        "to": OWNER,
        "gasToken": ZERO_ADDRESS,
        "refundReceiver": ZERO_ADDRESS,
        "submissionDate": DATE,
        "executionDate": DATE,
        "blockNumber": 100,
        "transactionHash": "0x" + "ef" * 32,
        "executor": OWNER,
        "isExecuted": True,
        "isSuccessful": True,
        "ethGasPrice": 1,
        "gasUsed": 2000,
        "fee": 2000,
        "origin": "",
        "confirmationsRequired": 2,
    }
    http.side_effect = [
        response(200, {"results": [queue_tx(5)], "next": None}),
        response(200, {"results": [executed], "next": None}),
    ]

    pending, history = client.get_transactions()

    assert pending.nonce == 5
    assert isinstance(history, ExecutedTxData)
    assert history.nonce == 4
    assert http.call_args.args == ("GET", f"{INDEX}/v2/safes/{SAFE}/multisig-transactions")
    assert http.call_args.kwargs["params"] == {"executed": "true", "ordering": "-nonce"}


def test_repeat_proposal_adds_only_missing_owner_signatures(queue_client):
    client, http = queue_client
    tx = create_safe_tx_def("1.4.1", SAFE, 1)(to=OWNER, nonce=5, baseGas=22)
    tx_hash = get_safe_tx_hash(tx)
    http.side_effect = [response(409), response(200, queue_tx(5, tx_hash)), response(201, [])]

    client.post_transaction(
        tx, {OWNER: SIGNATURE, OTHER_OWNER: OTHER_SIGNATURE}, sender=OTHER_OWNER
    )

    proposal, lookup, approval = http.call_args_list
    assert proposal.args == ("POST", f"{QUEUE}/multisig-transactions")
    payload = proposal.kwargs["json"]
    assert payload["signatures"] == [
        to_hex(OTHER_SIGNATURE.encode_rsv()),
        to_hex(SIGNATURE.encode_rsv()),
    ]
    assert (payload["chainId"], payload["safe"], payload["baseGas"]) == (1, SAFE, 22)
    assert "contractTransactionHash" not in payload
    assert lookup.args == ("GET", f"{QUEUE}/multisig-transactions/{tx_hash}")
    assert approval.args == ("POST", f"{QUEUE}/multisig-transactions/{tx_hash}/signatures")
    assert approval.kwargs["json"] == {"signatures": [to_hex(OTHER_SIGNATURE.encode_rsv())]}


def test_delegate_proposes_alone_then_stores_owner_confirmation(queue_client):
    client, http = queue_client
    tx = create_safe_tx_def("1.4.1", SAFE, 1)(to=OWNER, nonce=5)
    tx_hash = get_safe_tx_hash(tx)
    http.side_effect = [response(201, queue_tx(5, tx_hash, confirmations=[])), response(201, [])]

    client.post_transaction(tx, {DELEGATE: OTHER_SIGNATURE, OWNER: SIGNATURE}, sender=DELEGATE)

    proposal, approval = http.call_args_list
    assert proposal.kwargs["json"]["signatures"] == [to_hex(OTHER_SIGNATURE.encode_rsv())]
    assert approval.kwargs["json"]["signatures"] == [to_hex(SIGNATURE.encode_rsv())]


def test_proposal_with_a_different_chain_is_rejected_before_posting(queue_client):
    client, http = queue_client
    tx = create_safe_tx_def("1.4.1", SAFE, 10)(to=OWNER, nonce=5)

    with pytest.raises(SafeClientException, match="different Safe or chain"):
        client.post_transaction(tx, {OWNER: SIGNATURE})

    http.assert_not_called()


def test_lookup_does_not_treat_unavailable_queue_as_missing(queue_client):
    client, http = queue_client
    http.return_value = response(503)

    with pytest.raises(ClientResponseError):
        client.get_safe_tx("0x" + "cd" * 32)

    assert http.call_count == 1


def test_confirmation_conflict_retries_only_missing_signatures(queue_client):
    client, http = queue_client
    tx_hash = "0x" + "ab" * 32
    http.side_effect = [response(409), response(200, queue_tx(5, tx_hash)), response(201, [])]

    client.post_signatures(tx_hash, {OWNER: SIGNATURE, OTHER_OWNER: OTHER_SIGNATURE})

    first, lookup, retry = http.call_args_list
    assert (
        first.args == retry.args == ("POST", f"{QUEUE}/multisig-transactions/{tx_hash}/signatures")
    )
    assert lookup.args == ("GET", f"{QUEUE}/multisig-transactions/{tx_hash}")
    assert retry.kwargs["json"] == {"signatures": [to_hex(OTHER_SIGNATURE.encode_rsv())]}


def test_delegates_use_the_active_chain_or_a_chain_wide_scope(queue_client):
    client, http = queue_client
    entry = {"delegate": DELEGATE.lower(), "delegator": OWNER.lower()}
    http.return_value = response(
        200,
        {
            "results": [
                {**entry, "chainId": "1"},
                {**entry, "chainId": None},
                {**entry, "chainId": "10", "delegator": OTHER_OWNER.lower()},
            ],
            "next": None,
        },
    )

    assert client.get_delegates() == {OWNER: [DELEGATE]}
    assert http.call_args.args == ("GET", f"{QUEUE}/delegates")
    assert http.call_args.kwargs["params"] == {"safe": SAFE}


def test_explicit_transaction_service_keeps_legacy_requests(monkeypatch):
    client = SafeClient(SAFE, override_url="https://self-hosted.example/api")
    http = Mock(return_value=response(200, {"results": [], "next": None}))
    monkeypatch.setattr(client.session, "request", http)
    monkeypatch.setattr(client, "get_next_nonce", lambda: 5)

    assert list(client.get_transactions(confirmed=False)) == []
    assert http.call_args.args == (
        "GET",
        f"https://self-hosted.example/api/v1/safes/{SAFE}/multisig-transactions",
    )


def test_delegate_writes_sign_the_action_and_scope(queue_client, monkeypatch):
    client, http = queue_client
    monkeypatch.setattr(client_module.time, "time", lambda: 123 * 3600)
    signer = Mock(address=OWNER)
    signer.sign_raw_msghash.return_value = SIGNATURE
    http.side_effect = [response(409), response(200), response(204)]

    client.add_delegate(DELEGATE, "New label", signer)
    client.remove_delegate(DELEGATE, signer)

    assert [call.args for call in http.call_args_list] == [
        ("POST", f"{QUEUE}/delegates"),
        ("PATCH", f"{QUEUE}/delegates"),
        ("DELETE", f"{QUEUE}/delegates"),
    ]
    domain_hash = hash_struct(
        "EIP712Domain",
        {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "safe", "type": "address"},
            ]
        },
        {"name": "Safe Queue Service", "version": "1.0", "chainId": 1, "safe": SAFE},
    )
    for action, request, signed in zip(
        ("add", "edit", "delete"),
        http.call_args_list,
        signer.sign_raw_msghash.call_args_list,
        strict=True,
    ):
        body = request.kwargs["json"]
        assert (body["chainId"], body["safe"], body["delegate"], body["delegator"]) == (
            1,
            SAFE,
            DELEGATE,
            OWNER,
        )
        message_hash = hash_struct(
            "Delegate",
            {
                "Delegate": [
                    {"name": "delegateAddress", "type": "address"},
                    {"name": "totp", "type": "uint256"},
                    {"name": "action", "type": "string"},
                ]
            },
            {"delegateAddress": DELEGATE, "totp": 123, "action": action},
        )
        assert signed.args[0] == keccak(b"\x19\x01" + domain_hash + message_hash)


def test_remove_delegate_refuses_a_bulk_delete(queue_client):
    client, http = queue_client

    with pytest.raises(SafeClientException, match="specific delegate"):
        client.remove_delegate(ZERO_ADDRESS, Mock(address=OWNER))

    http.assert_not_called()
