def test_add_guard(safe, guard, exec_transaction):
    assert safe.guard is None

    receipt = exec_transaction(
        safe.contract.setGuard,
        guard,
    )

    assert safe.guard == guard

    # NOTE: SafeL2 contracts have extra event
    assert receipt.events[-2:] == [
        safe.contract.ChangedGuard(guard),
        safe.contract.ExecutionSuccess(),
    ]
