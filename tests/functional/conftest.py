from typing import TYPE_CHECKING

import pytest
from ape.exceptions import SignatureError
from eth_utils import add_0x_prefix

if TYPE_CHECKING:
    from ape.contracts import ContractTransactionHandler


@pytest.fixture(params=("sign", "api", "impersonate"))
def mode(request):
    return request.param


@pytest.fixture
def exec_transaction(mode, safe):
    impersonate = mode == "impersonate"
    submit = mode != "api"

    def exec_transaction(handler: "ContractTransactionHandler", *args):
        if submit:
            return handler(
                *args,
                sender=safe,
                impersonate=impersonate,
                submit=submit,
            )

        else:
            # Attempting to execute should raise `SignatureError` and push `safe_tx` to mock client
            size = len(list(safe.client.get_transactions(confirmed=False)))
            assert size == 0

            with pytest.raises(SignatureError):
                handler(
                    *args,
                    sender=safe,
                    impersonate=impersonate,
                    submit=submit,
                )

            pending_txns = list(safe.client.get_transactions(confirmed=False))
            assert len(pending_txns) == 1
            assert len(pending_txns[0].confirmations) >= 1
            safe_tx_hash = add_0x_prefix(pending_txns[0].safe_tx_hash)

            safe_tx_data = pending_txns[0]
            safe_tx = safe.create_safe_tx(**safe_tx_data.model_dump(by_alias=True, mode="json"))

            # Ensure client confirmations works
            client_confs = list(safe.client.get_confirmations(safe_tx_hash))
            assert len(client_confs) >= 1

            # Ensure API confirmations work
            api_confs = safe.get_api_confirmations(safe_tx)
            assert len(api_confs) >= 1

            # `safe_tx` is in mock client, extract it and execute it successfully this time
            return safe.submit_safe_tx(safe_tx)

    return exec_transaction


@pytest.fixture(scope="session")
def guard(project, deployer):
    return project.Guard.deploy(sender=deployer)
