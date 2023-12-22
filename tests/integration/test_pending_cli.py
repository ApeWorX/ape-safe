def test_help(runner, cli):
    result = runner.invoke(cli, ["pending", "--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_propose(runner, cli, one_safe, receiver):
    nonce_at_start = one_safe.next_nonce
    cmd = (
        "pending",
        "propose",
        "--to",
        receiver.address,
        "--value",
        "1",
    )

    # Sender is required by the API even for initial proposal,
    # so it prompts the user.
    sender_input = f"{one_safe.alias}\n"

    result = runner.invoke(cli, cmd, catch_exceptions=False, input=sender_input)
    assert result.exit_code == 0
    assert "Proposed transaction" in result.output
    safe_tx_hash = result.output.split("Proposed transaction '")[-1].split("'")[0].strip()

    # Verify the transaction is in the service.
    assert safe_tx_hash in one_safe.client.transactions

    # The nonce is the same because we did not execute.
    assert one_safe.next_nonce == nonce_at_start


def test_propose_with_gas_price(runner, cli, one_safe, receiver, chain):
    cmd = (
        "pending",
        "propose",
        "--to",
        receiver.address,
        "--value",
        "1",
        "--gas-price",
        chain.provider.gas_price,
    )
    result = runner.invoke(cli, cmd, catch_exceptions=False, input=f"{one_safe.alias}\n")
    assert result.exit_code == 0
    safe_tx_hash = result.output.split("Proposed transaction '")[-1].split("'")[0].strip()

    # Verify gas price was used.
    tx = one_safe.client.transactions[safe_tx_hash]
    assert tx.gas_price > 0


def test_propose_with_sender(runner, cli, one_safe, receiver):
    # First, fund the safe so the tx does not fail.
    receiver.transfer(one_safe, "1 ETH")

    nonce_at_start = one_safe.next_nonce
    cmd = (
        "pending",
        "propose",
        "--to",
        receiver.address,
        "--value",
        "1",
        "--sender",
        receiver.address,
    )
    result = runner.invoke(cli, cmd, catch_exceptions=False)
    assert result.exit_code == 0, result.output

    # The nonce is the same because we did not execute.
    assert one_safe.next_nonce == nonce_at_start


def test_propose_with_execute(runner, cli, one_safe, receiver):
    # First, fund the safe so the tx does not fail.
    receiver.transfer(one_safe, "1 ETH")

    nonce_at_start = one_safe.next_nonce
    cmd = (
        "pending",
        "propose",
        "--to",
        receiver.address,
        "--value",
        "1",
        "--sender",
        receiver.address,
        "--execute",
    )
    result = runner.invoke(cli, cmd, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert one_safe.next_nonce == nonce_at_start + 1


def test_list_no_safes(runner, cli, no_safes):
    result = runner.invoke(cli, ["pending", "list"])
    assert result.exit_code != 0, result.output
    assert "First, add a safe account using command" in result.output
    assert "ape safe add" in result.output


def test_list_no_txns(runner, cli, one_safe):
    result = runner.invoke(cli, ["pending", "list"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "There are no pending transactions" in result.output
