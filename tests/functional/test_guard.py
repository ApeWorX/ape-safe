import pytest
from packaging.version import Version


def test_add_guard(safe, guard, exec_transaction):
    if safe.version < Version("1.3.0"):
        pytest.skip(reason="Guard does not exist prior to v1.3.0")

    assert safe.guard is None

    receipt = exec_transaction(
        safe.contract.setGuard,
        guard,
    )

    assert safe.guard == guard
    assert receipt.events == [
        safe.contract.ChangedGuard(guard),
        safe.contract.ExecutionSuccess(),
    ]
