def test_add_guard(safe, guard, exec_transaction):
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
